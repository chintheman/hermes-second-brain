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
    prefixes = [str(w["prefix"]) for w in data.get("writers", []) if w.get("prefix")]
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

    allowed = sorted(set(prefixes) | set(SANCTIONED), key=len, reverse=True)
    pat = re.compile(r"^(" + "|".join(re.escape(p) for p in allowed) + r")[:( ]")

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
