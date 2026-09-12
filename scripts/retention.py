#!/usr/bin/env python3
"""retention.py — govern the ungoverned directories beside the curated vault.

THE PROBLEM THIS SOLVES
The curated vault is schema-checked, indexed, linted and gated. The directory
sitting next to it is not: ~951 markdown files across 19 directories, written by
four crons and several skills, indexed by nothing, retained by nothing. Its own
README documents a retention column that no code enforces. That is the same
shape as the 69 curated pages that sat unreachable for three months — a rule
written down and never executed.

WHAT THIS IS NOT
It is not a cleanup script with a delete flag bolted on. Deleting by age is the
wrong instrument for most of this tree: the two directories audited on
2026-09-12 both came back with "an age rule frees almost nothing and destroys
the founding week". So the default and the point of this tool is the REPORT —
what a rule would do, and what it would cost — and deletion is the narrow,
guarded exception for files proven dead.

THREE SAFETY PROPERTIES, IN ORDER OF IMPORTANCE
1. DRY RUN IS THE DEFAULT. Without --apply it never writes. --apply alone is
   still not enough: every rule carries `mode`, and a rule whose mode is
   `report` is never executed even with --apply. Turning a rule from report to
   delete is an edit to the policy file, reviewed like any other change.
2. IT ONLY DELETES WHAT IS ALREADY PUSHED. Before removing anything it asserts
   the vault's HEAD equals its upstream and the target paths are clean. A file
   removed with `git rm` from a pushed tree is recoverable forever from the
   remote; one removed from an unpushed tree is gone. This is the single guard
   that makes the whole thing reversible, so it cannot be skipped by a flag.
3. NEVER_DELETE IS CHECKED LAST AND OUT LOUD. A path matching a never_delete
   pattern is reported as protected on every run, so the exemption list is
   visible rather than silently doing its job.

THREE OUTCOMES, NEVER TWO
  exit 0  the report ran (or --apply removed exactly what the report said)
  exit 1  a guard tripped — nothing was deleted and the reason is printed
  exit 2  could not run: no policy file, not a git repo, unreadable target
Exit 2 is not "nothing to do". A directory the tool could not read is unknown,
not clean.

USAGE
  retention.py                          report every rule (dry run)
  retention.py --dir learnings          report one rule
  retention.py --apply                  execute rules whose mode is `delete`
  retention.py --policy <path>          override the policy location

Policy lives with the vault, not here: ~/wiki/_system/retention.yaml. This repo
is public; which directories a particular vault keeps and for how long is that
vault's business. See lint/lint_config.py for the same split.
"""

import argparse
import datetime
import fnmatch
import os
import re
import subprocess
import sys

try:
    import yaml
except ImportError:
    print("retention: FATAL — PyYAML not available", file=sys.stderr)
    sys.exit(2)

DEFAULT_VAULT = os.path.expanduser("~/wiki")
DEFAULT_POLICY = "_system/retention.yaml"
DATE_RE = re.compile(r"(20\d{2})-(\d{2})-(\d{2})")


def git(vault, *args):
    return subprocess.run(["git", "-C", vault, *args],
                          capture_output=True, text=True)


def file_date(path):
    """Date the file claims, from its NAME. mtime is rewritten by any checkout,
    so it cannot be trusted to say when content was written. A file with no
    date in its name returns None and is treated as undated — never as old."""
    m = DATE_RE.search(os.path.basename(path))
    if not m:
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def matches_any(name, patterns):
    return any(fnmatch.fnmatch(name, p) for p in (patterns or []))


def scan(vault, rule, today):
    """Classify every file under one rule's directory.

    Returns (keep, delete, protected, undated, unreadable) as lists of relpaths.
    A file is deleted only if it matches `match`, is older than `keep_days` (by
    filename date), is outside `keep_newest`, and matches no `never_delete`.

    `unconditional: true` is the one rule kind that ignores dates, because some
    classes of file are dead by TYPE rather than by age: a one-shot
    `commit-<timestamp>.sh` a cron generated because it could not run git is
    exhaust on the day it is written, and an age rule cannot express that. It
    also cannot even see most of them — their timestamps are `20260706`, not
    `2026-07-06`, so the date parser correctly reports them as undated and an
    age rule keeps them forever. Marking the CLASS dead is the honest model.
    """
    rel = rule["dir"].strip("/")
    root = os.path.join(vault, rel)
    if not os.path.isdir(root):
        return None

    try:
        names = sorted(os.listdir(root))
    except OSError:
        return None

    keep, delete, protected, undated, unreadable = [], [], [], [], []
    dated = []
    for n in names:
        full = os.path.join(root, n)
        if not os.path.isfile(full):
            continue
        p = f"{rel}/{n}"
        if not os.access(full, os.R_OK):
            unreadable.append(p)
            continue
        if not matches_any(n, rule.get("match", ["*"])):
            keep.append(p)
            continue
        if matches_any(n, rule.get("never_delete")):
            protected.append(p)
            continue
        if rule.get("unconditional"):
            delete.append(p)
            continue
        d = file_date(full)
        if d is None:
            # Undated is UNKNOWN, not old. It is never deleted by an age rule;
            # it is reported so the writer can be fixed.
            undated.append(p)
            keep.append(p)
            continue
        dated.append((d, p))

    dated.sort(reverse=True)
    newest = int(rule.get("keep_newest", 0) or 0)
    keep_days = rule.get("keep_days")
    for i, (d, p) in enumerate(dated):
        if i < newest:
            keep.append(p)
        elif keep_days is not None and (today - d).days <= int(keep_days):
            keep.append(p)
        elif keep_days is None and newest:
            delete.append(p)
        elif keep_days is not None:
            delete.append(p)
        else:
            keep.append(p)
    return keep, delete, protected, undated, unreadable


def size_of(vault, paths):
    total = 0
    for p in paths:
        try:
            total += os.path.getsize(os.path.join(vault, p))
        except OSError:
            pass
    return total


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def recoverability_guard(vault, paths):
    """Return an error string if deleting `paths` would not be recoverable.

    `git rm` from a tree whose HEAD is pushed is undoable forever: the blobs
    live on the remote. From an unpushed tree it is not. This is the guard that
    makes --apply safe, so it runs before every deletion and has no override.
    """
    if not os.path.isdir(os.path.join(vault, ".git")):
        return f"{vault} is not a git repository — deletion would be permanent"
    head = git(vault, "rev-parse", "HEAD").stdout.strip()
    up = git(vault, "rev-parse", "@{u}")
    if up.returncode != 0:
        return "no upstream branch — nothing to recover a deleted file from"
    if head != up.stdout.strip():
        return ("HEAD is not pushed (HEAD != upstream). Push first; a file "
                "removed from an unpushed tree cannot be recovered from the remote")
    untracked = []
    for p in paths:
        r = git(vault, "ls-files", "--error-unmatch", p)
        if r.returncode != 0:
            untracked.append(p)
    if untracked:
        return (f"{len(untracked)} target file(s) are not tracked by git, so "
                f"removing them is permanent: {', '.join(untracked[:3])}"
                + (" ..." if len(untracked) > 3 else ""))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=DEFAULT_VAULT)
    ap.add_argument("--policy", default=None)
    ap.add_argument("--dir", default=None, help="report only the rule for this directory")
    ap.add_argument("--apply", action="store_true",
                    help="execute rules whose policy mode is `delete` (git rm)")
    args = ap.parse_args()

    vault = os.path.expanduser(args.vault)
    policy_path = args.policy or os.path.join(vault, DEFAULT_POLICY)
    if not os.path.exists(policy_path):
        print(f"retention: no policy at {policy_path} — cannot run (this is not 'clean')")
        return 2
    try:
        with open(policy_path, encoding="utf-8") as fh:
            policy = yaml.safe_load(fh) or {}
    except Exception as err:  # noqa: BLE001
        print(f"retention: policy will not parse: {err}")
        return 2

    rules = policy.get("rules") or []
    if args.dir:
        rules = [r for r in rules if r.get("dir", "").strip("/") == args.dir.strip("/")]
        if not rules:
            print(f"retention: no rule for directory {args.dir}")
            return 2

    today = datetime.date.today()
    print(f"retention report — {vault}  ({today})")
    print(f"policy: {policy_path}\n")

    to_delete, unrunnable, notes = [], [], []
    for rule in rules:
        res = scan(vault, rule, today)
        name = rule.get("dir", "?")
        if res is None:
            unrunnable.append(name)
            print(f"  {name:22} UNRUNNABLE — directory missing or unreadable")
            continue
        keep, delete, protected, undated, unreadable = res
        mode = rule.get("mode", "report")
        oldest_kept = min((file_date(k) for k in keep if file_date(k)), default=None)
        print(f"  {name:22} scan {len(keep)+len(delete)+len(protected):>4}  "
              f"keep {len(keep)+len(protected):>4}  drop {len(delete):>4}  "
              f"frees {human(size_of(vault, delete)):>7}  "
              f"oldest kept {oldest_kept or '-'}  [{mode}]")
        if protected:
            print(f"      protected by never_delete: {len(protected)} "
                  f"({', '.join(os.path.basename(p) for p in protected[:3])}"
                  f"{' ...' if len(protected) > 3 else ''})")
        if undated:
            notes.append(f"{name}: {len(undated)} file(s) carry no date in the "
                         f"filename — reported as unknown, never deleted by age "
                         f"({', '.join(os.path.basename(p) for p in undated[:3])}"
                         f"{' ...' if len(undated) > 3 else ''})")
        if unreadable:
            unrunnable.append(f"{name} ({len(unreadable)} unreadable)")
        if rule.get("why"):
            print(f"      why: {rule['why']}")
        if mode == "delete":
            to_delete.extend(delete)

    if notes:
        print()
        for n in notes:
            print(f"  note: {n}")

    if unrunnable:
        print(f"\nUNRUNNABLE: {', '.join(unrunnable)}")
        print("A directory this tool could not read is UNKNOWN, not clean.")
        return 2

    if not args.apply:
        print(f"\ndry run — nothing written. {len(to_delete)} file(s) sit under a "
              f"rule whose mode is `delete`; re-run with --apply to remove them.")
        return 0

    if not to_delete:
        print("\n--apply: no rule is in `delete` mode, so nothing was removed.")
        return 0

    err = recoverability_guard(vault, to_delete)
    if err:
        print(f"\nREFUSING TO DELETE: {err}")
        return 1

    r = git(vault, "rm", "--quiet", "--", *to_delete)
    if r.returncode != 0:
        print(f"\ngit rm failed: {r.stderr.strip()[:300]}")
        return 1
    print(f"\nremoved {len(to_delete)} file(s) with git rm. Nothing is committed "
          f"yet — review `git -C {vault} status`, then commit. Every removed file "
          f"is recoverable from the remote via `git log --diff-filter=D`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
