#!/usr/bin/env python3
"""Brain lint analysis v2 — scoped to core schema pages (entities/concepts/mocs/decisions/sources/references), excluding digests/archives/vendor."""
import os, re, sys, yaml
from collections import Counter, defaultdict

VAULT = os.path.expanduser("~/wiki")
TAXONOMY = os.path.join(VAULT, "_system/taxonomy.md")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lint_config
CFG = lint_config.load(VAULT)
CORE_DIRS = tuple(CFG["core_dirs"])

def frontmatter(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if not text.startswith("---"):
        return None, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text
    try:
        fm = yaml.safe_load(parts[1])
    except Exception:
        fm = {}
    return (fm or {}), text

def is_core(rel):
    """Delegates to lint_config so no vault-specific path lives in this repo."""
    return lint_config.is_core(rel, CFG)

def main():
    all_md = []
    for root, dirs, files in os.walk(VAULT):
        dirs[:] = [d for d in dirs if not d.startswith(".git") and d != "node_modules"]
        for fn in files:
            if fn.endswith(".md"):
                all_md.append(os.path.join(root, fn))
    core = [os.path.relpath(p, VAULT) for p in all_md if is_core(os.path.relpath(p, VAULT))]
    print(f"Core pages (schema dirs, non-digest): {len(core)}")

    # ---- tags on core pages ----
    tag_counter = Counter(); tag_file = defaultdict(list)
    for p in all_md:
        rel = os.path.relpath(p, VAULT)
        fm, _ = frontmatter(p)
        if not fm: continue
        tags = fm.get("tags", [])
        if isinstance(tags, str):
            tags = re.findall(r"[\w-]+", tags)
        for t in tags:
            tag_counter[t] += 1
            tag_file[t].append(rel)
    tax_text = open(TAXONOMY, encoding="utf-8").read()
    tax_tags = set(re.findall(r"`([\w-]+)`", tax_text))
    for line in tax_text.splitlines():
        line = line.strip()
        if line and not line.startswith(("#", "-", "`", "|", ">", "*", "[")):
            for w in line.split():
                w = w.strip("`,")
                if re.fullmatch(r"[\w-]+", w):
                    tax_tags.add(w)
    rogue_core = {t: tag_counter[t] for t in tag_counter if t not in tax_tags and any(tag_file[t][0] in core for _ in [0]) and tag_file[t][0] in core}
    print("\n=== R7 ROGUE TAGS (core pages) ===")
    r7 = sorted(rogue_core.items(), key=lambda x: -x[1])
    if r7:
        for t, c in r7:
            print(f"  {t} ({c}x) in {[f for f in tag_file[t] if f in core][:3]}")
    else:
        print("  none")

    # ---- wikilinks (all md, excluding site/node_modules) ----
    link_re = re.compile(r"\[\[([^\]|#]+)(?:\|[^\]]+)?\]\]")
    inbound = Counter(); outbound = {}; basename_map = defaultdict(list)
    for p in all_md:
        rel = os.path.relpath(p, VAULT)
        fm, text = frontmatter(p)
        links = [l.strip() for l in link_re.findall(text)]
        outbound[rel] = links
        for l in links:
            inbound[l] += 1
        base = os.path.splitext(os.path.basename(p))[0]
        basename_map[base].append(rel)
    broken = []
    for rel, links in outbound.items():
        for l in links:
            l = l.strip()
            if l.startswith("http") or "://" in l: continue
            if l.startswith("mailto:"): continue
            target_base = os.path.splitext(os.path.basename(l))[0]
            if l in basename_map or target_base in basename_map: continue
            if os.path.exists(os.path.join(VAULT, l + ".md")): continue
            if os.path.exists(os.path.join(VAULT, l)): continue
            broken.append((rel, l))
    broken_core = [(r, l) for r, l in broken if r in core]
    print("\n=== R16 BROKEN WIKILINKS (core source pages) ===")
    bc = Counter(l for _, l in broken_core)
    if bc:
        for t, c in bc.most_common(30):
            print(f"  {t} ({c}x) from {[r for r,l in broken_core if l==t][:3]}")
    else:
        print("  none")
    print(f"  (total broken incl non-core: {len(broken)})")

    # ---- orphans: core page with zero inbound from any page ----
    def inbound_count(rel):
        base = os.path.splitext(os.path.basename(rel))[0]
        return sum(1 for l in inbound if os.path.splitext(os.path.basename(l))[0] == base or l == rel)
    orphans = [rel for rel in core if inbound_count(rel) == 0]
    print(f"\n=== R5 ORPHANS (core, zero inbound): {len(orphans)}/{len(core)} = {100*len(orphans)/max(len(core),1):.1f}% ===")
    for o in orphans:
        print(f"  {o}")

    # ---- mentions of missing targets (R6): broken targets with >=3 inbound mentions ----
    print("\n=== R6 MISSING PAGES (broken targets mentioned >=3x anywhere) ===")
    r6 = [(t, c) for t, c in inbound.items() if t not in basename_map and not os.path.exists(os.path.join(VAULT, t + ".md")) and c >= 3]
    r6_sorted = sorted(r6, key=lambda x: -x[1])
    if r6_sorted:
        for t, c in r6_sorted:
            srcs = [r for r, ls in outbound.items() if t in ls][:4]
            print(f"  {t} ({c}x) from {srcs}")
    else:
        print("  none")

if __name__ == "__main__":
    main()
