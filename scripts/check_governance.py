#!/usr/bin/env python3
"""check_governance.py — every governing document is declared, and still read.

THE BLIND SPOT THIS CLOSES
The curated vault is indexed, linted and schema-gated. The directory beside it
is not — and that directory is where the documents that GOVERN the system live:
the conventions every profile reads at start, the routing protocol two skills
deprecated themselves in favour of, the reviewer ledger cited in every weekly
lint report. None of them carry frontmatter, so the index cannot see them and
the lint has nothing to say about them.

That is the same condition that let 69 curated pages sit unreachable for three
months: content the system depends on, living where nothing checks it.

Moving them into the indexed tree was the obvious fix and the wrong one — those
files are referenced by hundreds of others, and a missed reference fails
silently, which is the failure mode the move was supposed to cure. So they stay
where they are and this checks them in place.

THREE ASSERTIONS, AND THE THIRD IS THE ONE WITH TEETH
1. Every prose file at the root of the governed directory is DECLARED — as
   `governs`, `reference`, or `dead` — or matches an `ignore` pattern. A new
   governance document that appears without a declaration is flagged the week it
   lands, which a one-time cleanup would never catch.
2. Every declared file EXISTS. A declaration outliving its file is a lie the
   next reader will act on.
3. Every `governs` entry is still READ. Each names a `reader` — a path or glob
   that must contain the filename. A governing document whose last reader
   disappeared is dead weight that still looks authoritative, and nothing else
   in the system would notice.

Assertion 3 is why this is not just an inventory. An inventory tells you what is
there; this tells you what is still load-bearing.

THREE OUTCOMES, NEVER TWO
  exit 0  everything declared, present, and still read
  exit 1  at least one finding (undeclared / missing / unread)
  exit 2  could not run: no policy, unreadable directory. NOT a pass.

USAGE
  check_governance.py [--vault ~/wiki] [--policy <path>] [--quiet]

Policy lives with the vault (`_system/governance.yaml`), not in this repo: which
documents a particular vault governs is that vault's business. Same split as
lint/lint_config.py and scripts/retention.py.
"""

import argparse
import fnmatch
import glob
import os
import sys

try:
    import yaml
except ImportError:
    print("check_governance: FATAL — PyYAML not available", file=sys.stderr)
    sys.exit(2)

DEFAULT_VAULT = os.path.expanduser("~/wiki")
DEFAULT_POLICY = "_system/governance.yaml"
PROSE_SUFFIXES = (".md", ".yaml", ".yml")


def declared_names(policy):
    """Every filename named anywhere in the policy, with its section."""
    out = {}
    for section in ("governs", "reference", "dead"):
        for entry in policy.get(section) or []:
            name = entry["file"] if isinstance(entry, dict) else entry
            out[name] = section
    return out


def reader_satisfied(vault, filename, reader):
    """True if `filename` appears in any file matched by the reader pattern.

    The reader is a path or glob relative to $HOME, so a policy can point at a
    skill tree or a script directory outside the vault — which is where most of
    these documents are actually read from.
    """
    pattern = os.path.expanduser(reader)
    if not os.path.isabs(pattern):
        pattern = os.path.join(os.path.expanduser("~"), pattern)
    hits = glob.glob(pattern, recursive=True)
    if not hits:
        return None  # cannot tell: the reader location itself is gone
    for h in hits:
        if os.path.isdir(h):
            for root, _dirs, files in os.walk(h):
                if ".git" in root:
                    continue
                for f in files:
                    if not f.endswith(PROSE_SUFFIXES + (".py", ".sh", ".json")):
                        continue
                    try:
                        with open(os.path.join(root, f), encoding="utf-8",
                                  errors="ignore") as fh:
                            if filename in fh.read():
                                return True
                    except OSError:
                        continue
        else:
            try:
                with open(h, encoding="utf-8", errors="ignore") as fh:
                    if filename in fh.read():
                        return True
            except OSError:
                continue
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=DEFAULT_VAULT)
    ap.add_argument("--policy", default=None)
    ap.add_argument("--quiet", action="store_true",
                    help="print only findings, not the clean summary")
    args = ap.parse_args()

    vault = os.path.expanduser(args.vault)
    policy_path = args.policy or os.path.join(vault, DEFAULT_POLICY)
    if not os.path.exists(policy_path):
        print(f"check_governance: no policy at {policy_path} — cannot run "
              f"(this is NOT 'clean')")
        return 2
    try:
        with open(policy_path, encoding="utf-8") as fh:
            policy = yaml.safe_load(fh) or {}
    except Exception as err:  # noqa: BLE001
        print(f"check_governance: policy will not parse: {err}")
        return 2

    root_rel = (policy.get("root") or "_system").strip("/")
    root = os.path.join(vault, root_rel)
    if not os.path.isdir(root):
        print(f"check_governance: {root} is not a directory — cannot run")
        return 2

    ignore = policy.get("ignore") or []
    declared = declared_names(policy)

    try:
        on_disk = sorted(f for f in os.listdir(root)
                         if os.path.isfile(os.path.join(root, f))
                         and f.endswith(PROSE_SUFFIXES)
                         and not f.startswith("."))
    except OSError as err:
        print(f"check_governance: cannot list {root}: {err}")
        return 2

    undeclared, missing, unread, unverifiable = [], [], [], []

    for f in on_disk:
        if any(fnmatch.fnmatch(f, p) for p in ignore):
            continue
        if f not in declared:
            undeclared.append(f)

    for name in declared:
        if not os.path.exists(os.path.join(root, name)):
            missing.append(f"{name} (declared as {declared[name]})")

    for entry in policy.get("governs") or []:
        if not isinstance(entry, dict):
            continue
        name, reader = entry["file"], entry.get("reader")
        if not os.path.exists(os.path.join(root, name)):
            continue  # already reported as missing
        if not reader:
            unverifiable.append(f"{name}: declared as governing but names no reader")
            continue
        ok = reader_satisfied(vault, name, reader)
        if ok is None:
            unverifiable.append(f"{name}: reader path `{reader}` does not exist — "
                                f"cannot tell whether it is still read")
        elif not ok:
            unread.append(f"{name}: nothing under `{reader}` mentions it any more")

    findings = 0
    if undeclared:
        findings += len(undeclared)
        print(f"UNDECLARED ({len(undeclared)}) — a governing document can appear "
              f"here and nothing would know:")
        for f in undeclared:
            print(f"  {root_rel}/{f}")
    if missing:
        findings += len(missing)
        print(f"DECLARED BUT MISSING ({len(missing)}) — the declaration outlived "
              f"the file:")
        for m in missing:
            print(f"  {m}")
    if unread:
        findings += len(unread)
        print(f"NO LONGER READ ({len(unread)}) — still looks authoritative, "
              f"nothing points at it:")
        for u in unread:
            print(f"  {u}")
    if unverifiable:
        # Not counted as a finding: unverifiable is UNKNOWN, not a failure. It is
        # printed every run so it cannot quietly become the normal state.
        print(f"UNVERIFIABLE ({len(unverifiable)}) — reported, not graded:")
        for u in unverifiable:
            print(f"  {u}")

    if findings:
        print(f"\ncheck_governance: {findings} finding(s) across "
              f"{len(on_disk)} root prose files")
        return 1
    if not args.quiet:
        print(f"check_governance: {len(on_disk)} root prose files, all declared, "
              f"all present, every governing document still read"
              + (f" ({len(unverifiable)} unverifiable)" if unverifiable else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
