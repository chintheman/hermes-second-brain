#!/usr/bin/env python3
"""check_writers.py — assert every vault commit since the cutover is attributable.

BRAIN.md §0.2 allows exactly two writers of schema'd pages. In practice many
processes commit to the vault, and a census on 2026-09-11 found 22 distinct commit
prefixes plus a class carrying none at all. Since every commit shares one git
author, the subject prefix is the only attribution signal available.

This asserts that every commit made AFTER the declared cutover carries either a §8
prefix or a prefix declared in <vault>/_system/writers.yaml. History before the
cutover is immutable (§8 forbids rewriting it) and is deliberately out of scope —
a check that judges unfixable history can never pass, and a check that can never
pass gets ignored, which is the failure mode this whole exercise exists to fix.

Usage:
  check_writers.py [--vault ~/wiki] [--since ISO8601]   # default: registry cutover
  check_writers.py --negative-control                    # must FAIL, proving it can

Exit: 0 conformant, 1 violations found, 2 usage/config error.
"""
import argparse
import os
import re
import subprocess
import sys

SANCTIONED = ("deposit", "dream", "lint", "capture")  # BRAIN.md §8


def load_registry(vault):
    path = os.path.join(vault, "_system", "writers.yaml")
    if not os.path.exists(path):
        print(f"ERROR: no writer registry at {path}", file=sys.stderr)
        sys.exit(2)
    try:
        import yaml
        data = yaml.safe_load(open(path, encoding="utf-8")) or {}
    except Exception as exc:
        print(f"ERROR: registry unreadable: {exc}", file=sys.stderr)
        sys.exit(2)
    if not isinstance(data, dict):
        print(f"ERROR: registry is not a mapping: {path}", file=sys.stderr)
        sys.exit(2)
    writers = data.get("writers") or []
    if not isinstance(writers, list):
        print(f"ERROR: registry `writers` is not a list: {path}", file=sys.stderr)
        sys.exit(2)
    prefixes = [(str(w["prefix"]), str(w.get("delimiter", "colon")))
                for w in writers if isinstance(w, dict) and w.get("prefix")]
    if not prefixes:
        print(f"ERROR: registry declares no writers: {path}", file=sys.stderr)
        sys.exit(2)
    return prefixes, data.get("cutover")


def git(vault, *args):
    return subprocess.run(["git", "-C", vault, *args],
                          capture_output=True, text=True).stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=os.path.expanduser("~/wiki"))
    ap.add_argument("--since")
    ap.add_argument("--negative-control", action="store_true",
                    help="run against a date before the cutover; must report violations")
    args = ap.parse_args()

    prefixes, cutover = load_registry(args.vault)
    since = args.since or ("2026-07-13" if args.negative_control else cutover)
    if not since:
        print("ERROR: registry has no cutover and --since not given", file=sys.stderr)
        sys.exit(2)

    # A declared prefix matches only with its declared delimiter. Colon is the
    # default; a bare space is opt-in, because matching any prefix followed by a
    # space would let ordinary prose ("fix the index by hand") pass as declared.
    decl = list(prefixes) + [(p, "colon") for p in SANCTIONED]
    alts = []
    for name, delim in sorted(set(decl), key=lambda x: -len(x[0])):
        esc = re.escape(name)
        alts.append(esc + r"(\([^)]*\))?: " if delim != "space" else esc + r" \S")
    pat = re.compile("^(" + "|".join(alts) + ")")

    # --since filters by author date, which a backdated commit at HEAD can use to
    # prune the entire range (observed: six post-cutover commits vanished, exit 2
    # "nothing proved"). Prefer a topological walk from the cutover commit.
    base = git(args.vault, "rev-list", "-1", f"--before={since}", "HEAD").strip()
    if base:
        log = git(args.vault, "log", f"{base}..HEAD", "--pretty=format:%h %s")
    else:
        log = git(args.vault, "log", f"--since={since}", "--pretty=format:%h %s")
    lines = [l for l in log.splitlines() if l.strip()]
    if not lines:
        print(f"FAIL: no commits since {since} — nothing proved")
        sys.exit(2)

    bad = [l for l in lines if not pat.match(l.split(" ", 1)[1] if " " in l else "")]

    if args.negative_control:
        if bad:
            print(f"negative control OK: {len(bad)} undeclared of {len(lines)} "
                  f"since {since} — the check can fail")
            for l in bad[:5]:
                print(f"  {l}")
            sys.exit(0)
        print("negative control FAILED: nothing flagged before the cutover, "
              "so this check proves nothing")
        sys.exit(1)

    if bad:
        print(f"FAIL: {len(bad)} of {len(lines)} commits since {since} "
              f"carry no declared prefix:")
        for l in bad:
            print(f"  {l}")
        sys.exit(1)
    print(f"PASS: {len(lines)} commits since {since}, every one declared")


if __name__ == "__main__":
    main()
