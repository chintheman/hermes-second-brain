#!/usr/bin/env python3
"""Core orphan rate + index-read proxy check."""
import os, re

VAULT = os.path.expanduser("~/wiki")
CORE = ('entities/', 'concepts/', 'mocs/', 'decisions/', 'sources/')
allmd = []
for root, dirs, files in os.walk(VAULT):
    dirs[:] = [d for d in dirs if not d.startswith('.git') and d != 'node_modules']
    for fn in files:
        if fn.endswith('.md'):
            allmd.append(os.path.relpath(os.path.join(root, fn), VAULT))
core = [r for r in allmd if any(r.startswith(d) for d in CORE) and 'digest' not in os.path.basename(r)]
link_re = re.compile(r'\[\[([^\]|#]+)(?:\|[^\]]+)?\]\]')
inbound = {}
for r in allmd:
    try:
        text = open(os.path.join(VAULT, r), encoding='utf-8').read()
    except Exception:
        continue
    for l in link_re.findall(text):
        inbound[l.strip()] = inbound.get(l.strip(), 0) + 1
orphans = [r for r in core if not any(os.path.splitext(os.path.basename(l))[0] == os.path.splitext(os.path.basename(r))[0] for l in inbound)]
print(f'core pages (no refs/scopes): {len(core)}, orphans: {len(orphans)} ({100*len(orphans)/max(len(core),1):.1f}%)')
for o in orphans:
    print(' ', o)

print('\n=== INDEX-READ PROXY (learnings/context-digests Aug 2026 mentioning index.md) ===')
for d in ('_system/learnings', '_system/context-digests'):
    hits = 0
    total = 0
    for fn in sorted(os.listdir(os.path.join(VAULT, d))):
        if not fn.startswith('2026-08') or not fn.endswith('.md'):
            continue
        total += 1
        try:
            t = open(os.path.join(VAULT, d, fn), encoding='utf-8').read()
        except Exception:
            continue
        if 'index.md' in t:
            hits += 1
    print(f'  {d}: {hits}/{total} mention index.md')
