#!/usr/bin/env python3
"""R10 stale pages + R11 data gaps — scoped to core schema dirs."""
import os, sys, time, re

VAULT = os.path.expanduser("~/wiki")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lint_config
CFG = lint_config.load(VAULT)
now = time.time()
cutoff = now - 30 * 86400

core = []
for root, dirs, files in os.walk(VAULT):
    dirs[:] = [d for d in dirs if not d.startswith(".git") and d != "node_modules"]
    for fn in files:
        if not fn.endswith(".md"):
            continue
        rel = os.path.relpath(os.path.join(root, fn), VAULT)
        if not lint_config.is_core(rel, CFG):
            continue
        core.append(rel)

stale = []
for rel in core:
    mt = os.path.getmtime(os.path.join(VAULT, rel))
    if mt < cutoff:
        days = int((now - mt) / 86400)
        stale.append((rel, days))

print(f"Core non-digest pages: {len(core)}")
print(f"Stale >30d: {len(stale)} ({100*len(stale)/max(len(core),1):.1f}%)")
stale.sort(key=lambda x: -x[1])
for rel, days in stale:
    print(f"  {days:3d}d  {rel}")

print("\n=== R11: THIN / PLACEHOLDER PAGES ===")
# Detected by the rule's own definition, not from a list. The previous version
# named three real vault pages inline, in a PUBLIC repo (BRAIN.md §12 / E1).
MARKERS = ("placeholder", "todo", "tbd", "coming soon", "stub",
           "implementation companion", "to be written")
THIN_BYTES = 1200
gaps = []
for rel in core:
    try:
        text = open(os.path.join(VAULT, rel), encoding="utf-8").read()
    except (UnicodeDecodeError, OSError):
        continue
    low = text.lower()
    marked = [m for m in MARKERS if m in low]
    if marked or len(text) < THIN_BYTES:
        gaps.append((rel, len(text), marked))
gaps.sort(key=lambda g: g[1])
for rel, n, marked in gaps[:20]:
    why = ", ".join(marked) if marked else f"thin (<{THIN_BYTES}B)"
    print(f"  {rel}: {n}B — {why}")
print(f"{len(gaps)} thin or placeholder pages of {len(core)} core pages")
