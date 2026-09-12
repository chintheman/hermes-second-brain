#!/usr/bin/env python3
"""check_inbox.py — an inbox that nothing drains is not an inbox.

THE FAILURE THIS PREVENTS
A capture directory works from day one: things land in it. The promotion path is
the half that silently never gets built. By the time anyone looks, the directory
holds months of material — some of it live work nobody is tracking, some of it
long since shipped — and the only way to tell them apart is to read all of it.

That happened here: 40 of 98 files at the root of the capture inbox had zero
mention anywhere in the task registry, spread evenly across the whole life of the
vault. Not one bad week — a path that never existed. Two reviewers and about an
hour of machine time were needed to sort 40 files that would each have taken ten
seconds to sort on the day they landed.

Draining it once fixes nothing. This is what stops it refilling.

WHAT IT ASSERTS
Every file at the inbox root is either named in the registry, or younger than the
grace period. That is the whole rule, and it is deliberately weak: it does not
care whether the linked task is open or closed, or whether the file is any good.
It asks one question — does anything in the system know this file exists? — and a
file old enough to have been triaged, that nothing references, is the finding.

The grace period is the point of the design. A file captured this morning SHOULD
be unlinked; triage is not instantaneous. A file unlinked after two weeks was
never triaged at all.

THREE OUTCOMES, NEVER TWO
  exit 0  every aged file is linked (or the inbox is empty)
  exit 1  aged files nobody has triaged — listed oldest first
  exit 2  could not run: no registry, no inbox, unreadable. NOT a pass.

USAGE
  check_inbox.py [--vault ~/wiki] [--inbox _system/pending]
                 [--registry _system/task-registry.yaml] [--grace-days 14]
"""

import argparse
import os
import subprocess
import sys
import datetime


def last_commit_date(vault, rel):
    r = subprocess.run(["git", "-C", vault, "log", "-1", "--format=%ad",
                        "--date=short", "--", rel],
                       capture_output=True, text=True)
    out = r.stdout.strip()
    if not out:
        return None
    try:
        return datetime.date.fromisoformat(out)
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=os.path.expanduser("~/wiki"))
    ap.add_argument("--inbox", default="_system/pending")
    ap.add_argument("--registry", default="_system/task-registry.yaml")
    ap.add_argument("--grace-days", type=int, default=14)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    vault = os.path.expanduser(args.vault)

    def resolve(p):
        """Vault-relative by default; an absolute path wins. `.strip("/")` on a
        path the caller gave as absolute turned it into a relative one and
        silently rebased it under the vault — which made the negative control
        exit 2 instead of 1, i.e. the test could not fail correctly."""
        p = os.path.expanduser(p)
        return p if os.path.isabs(p) else os.path.join(vault, p.strip("/"))

    inbox = resolve(args.inbox)
    registry = resolve(args.registry)

    if not os.path.isdir(inbox):
        print(f"check_inbox: no inbox at {inbox} — cannot run (NOT 'clean')")
        return 2
    if not os.path.exists(registry):
        print(f"check_inbox: no registry at {registry} — cannot run (NOT 'clean')")
        return 2
    try:
        with open(registry, encoding="utf-8") as fh:
            blob = fh.read()
    except OSError as err:
        print(f"check_inbox: cannot read the registry: {err}")
        return 2

    # Matched as raw text, not parsed YAML, on purpose: a file may be named in a
    # task id, a source, a notes field, a summary or a log line, and all of those
    # count as "something knows this exists".
    try:
        files = sorted(f for f in os.listdir(inbox)
                       if os.path.isfile(os.path.join(inbox, f))
                       and f.endswith(".md") and not f.startswith("."))
    except OSError as err:
        print(f"check_inbox: cannot list the inbox: {err}")
        return 2

    today = datetime.date.today()
    stale, undated = [], []
    for f in files:
        if f[:-3] in blob or f in blob:
            continue
        # Age from git, never mtime: a checkout rewrites mtime and would make
        # every file look new, which would turn this check into a no-op.
        d = last_commit_date(vault, os.path.join(args.inbox.strip("/"), f))
        if d is None:
            undated.append(f)
            continue
        age = (today - d).days
        if age > args.grace_days:
            stale.append((age, f))

    stale.sort(reverse=True)

    if stale:
        print(f"UNTRIAGED ({len(stale)} of {len(files)}) — in the inbox longer "
              f"than {args.grace_days} days and named nowhere in the registry:")
        for age, f in stale:
            print(f"  {age:>4}d  {args.inbox.strip('/')}/{f}")
        print("\nEach one is a live task nobody is tracking, or spent work nobody "
              "cleared. Link it, delete it, or move it out of the inbox — three "
              "outcomes, and 'leave it' is not one of them.")
    if undated:
        # Untracked by git: reported, never graded. It has no age, so the grace
        # period cannot apply and calling it stale would be a guess.
        print(f"\nNOT IN GIT ({len(undated)}) — reported, not graded:")
        for f in undated:
            print(f"  {args.inbox.strip('/')}/{f}")

    if stale:
        return 1
    if not args.quiet:
        print(f"check_inbox: {len(files)} file(s) in {args.inbox.strip('/')}/, "
              f"every one older than {args.grace_days}d is linked to the registry"
              + (f" ({len(undated)} not in git, ungraded)" if undated else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
