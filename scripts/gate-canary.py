#!/usr/bin/env python3
"""gate-canary.py — prove the schema gates can still FAIL.

THE PROBLEM THIS SOLVES
A gate that stops working does not announce it. It reports "clean" forever, and
silence is indistinguishable from health. Every failure in this vault's history
has that shape: 69 pages dropped while lint said "no drift"; a privacy check that
passed for months because it grepped for names and never paths; a writer audit
defeated by one backdated commit while printing PASS; a delimiter that let prose
through while all 632 real commits still matched.

A detector is only trustworthy if you periodically prove it still detects. This
plants known-bad conditions in a throwaway sandbox and asserts each gate catches
them. If a canary PASSES, the gate is dead and the vault has been unguarded for
however long that has been true.

It also asserts the gates stay quiet on a clean sandbox, because a gate that fires
on everything is just as useless and gets muted by whoever reads it.

THREE OUTCOMES, NEVER TWO
  exit 0  every gate caught every planted defect, and passed the clean control
  exit 1  a gate FAILED TO CATCH something — the gate is broken, not the vault
  exit 2  the canary could not run (missing script, unusable temp dir)
Exit 2 is not "clean". Missing data is a skip, never a pass.

Usage: gate-canary.py [--engine ~/brain-engine] [--verbose]
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

FM = """---
title: "{title}"
type: {ptype}
created: 2026-01-01
updated: 2026-01-01
confidence: high
valid_from: 2026-01-01
superseded_by: {superseded}
sources: []
tags: []
links: []
overlay: core
---

# {title}

## Summary
Canary fixture. Not real content.
"""


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def build_vault(root, defect):
    """A minimal vault with exactly one planted defect (or none)."""
    for d in ("entities", "concepts", "projects", "_system"):
        os.makedirs(os.path.join(root, d), exist_ok=True)
    write(os.path.join(root, "entities", "good.md"),
          FM.format(title="Good", ptype="entity", superseded="null"))
    write(os.path.join(root, "concepts", "idea.md"),
          FM.format(title="Idea", ptype="concept", superseded="null"))

    if defect == "wrong_type":
        write(os.path.join(root, "entities", "bad.md"),
              FM.format(title="Bad", ptype="project", superseded="null"))
    elif defect == "no_frontmatter":
        write(os.path.join(root, "concepts", "bare.md"), "# Bare\n\nNo frontmatter.\n")
    elif defect == "nested":
        write(os.path.join(root, "concepts", "deep", "buried.md"),
              FM.format(title="Buried", ptype="project", superseded="null"))
    elif defect == "self_supersede":
        write(os.path.join(root, "entities", "selfref.md"),
              FM.format(title="Selfref", ptype="project",
                        superseded="[[entities/selfref]]"))
    elif defect == "null_supersede":
        write(os.path.join(root, "entities", "tilde.md"),
              FM.format(title="Tilde", ptype="project", superseded="~"))


CASES = [
    ("wrong_type",      "a page whose type its folder does not admit"),
    ("no_frontmatter",  "a page the index would silently drop"),
    ("nested",          "a bad page in a subdirectory"),
    ("self_supersede",  "a page exempting itself via superseded_by"),
    ("null_supersede",  "superseded_by set to YAML null as an escape"),
]


def run_check_types(engine, vault):
    return subprocess.run(
        [sys.executable, os.path.join(engine, "scripts", "rebuild_index.py"),
         "--vault", vault, "--check-types"],
        capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default=os.path.expanduser("~/brain-engine"))
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    script = os.path.join(args.engine, "scripts", "rebuild_index.py")
    if not os.path.exists(script):
        print(f"CANARY UNRUNNABLE: no rebuild_index.py at {script}")
        return 2

    tmp = tempfile.mkdtemp(prefix="gate-canary-")
    broken, checked = [], 0
    try:
        # Control: a clean vault must NOT trip the gate.
        ctl = os.path.join(tmp, "clean")
        build_vault(ctl, None)
        res = run_check_types(args.engine, ctl)
        checked += 1
        if res.returncode != 0:
            broken.append(("clean control", "gate fired on a clean vault "
                           f"(exit {res.returncode}) — it will be muted as noise"))
        elif args.verbose:
            print("  ok  clean control stayed quiet")

        # Each planted defect must be caught.
        for defect, desc in CASES:
            v = os.path.join(tmp, defect)
            build_vault(v, defect)
            res = run_check_types(args.engine, v)
            checked += 1
            if res.returncode == 0:
                broken.append((defect, f"NOT CAUGHT: {desc}"))
            elif args.verbose:
                print(f"  ok  caught: {desc}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if broken:
        print(f"GATE CANARY FAILED — {len(broken)} of {checked} checks:")
        for name, why in broken:
            print(f"  {name}: {why}")
        print("\nThe GATE is broken, not the vault. Until this is fixed, a clean "
              "report from --check-types means nothing.")
        return 1

    print(f"gate canary: {checked}/{checked} — every planted defect caught, "
          f"clean control quiet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
