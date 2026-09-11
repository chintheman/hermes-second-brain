#!/usr/bin/env python3
"""R8 provenance gaps + R9 confidence audit — synthesis-heavy pages.

R8 asks whether a synthesis-heavy page carries `^[inferred]` marks; a long,
multi-source page with none of them means provenance was skipped, not that nothing
was inferred. R9 samples `confidence: high` pages and asks whether their claims
trace to a cited source.

Pages are SELECTED AT RUNTIME by the rule's own definition (long body AND at least
one source), not from a list. The previous version hardcoded 13 real vault page
paths into this file, which is in a PUBLIC repo — a live BRAIN.md §12 / E1 breach
that E1 never caught because it only grepped for personal names. Scoping now comes
from <vault>/_system/lint-config.yaml, which lives in the private vault.

Usage: check_r8r9.py [--vault ~/wiki]
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lint_config


def body_after_frontmatter(text):
    m = re.match(r"\A---\s*\n.*?\n---\s*\n", text, re.DOTALL)
    return text[m.end():] if m else text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default=os.path.expanduser("~/wiki"))
    args = ap.parse_args()
    vault = args.vault
    cfg = lint_config.load(vault)
    tune = cfg["r8r9"]

    candidates = []
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
        for fn in files:
            if not fn.endswith(".md"):
                continue
            rel = os.path.relpath(os.path.join(root, fn), vault)
            if not lint_config.is_core(rel, cfg):
                continue
            try:
                text = open(os.path.join(vault, rel), encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            body = body_after_frontmatter(text)
            src_line = re.findall(r"^sources:\s*(.*)$", text, re.M)
            srcs = src_line[0].strip() if src_line else "NO-FIELD"
            n_src = 0 if srcs in ("[]", "NO-FIELD", "") else srcs.count(",") + 1
            if len(body) < tune["min_body_bytes"] or n_src < tune["min_sources"]:
                continue
            candidates.append({
                "rel": rel,
                "bytes": len(body),
                "sources": srcs,
                "n_src": n_src,
                "inferred": text.count("^[inferred]"),
                "confidence": (re.findall(r"^confidence:\s*(\S+)", text, re.M) or [""])[0],
            })

    # Longest bodies first: most synthesis, most to account for.
    candidates.sort(key=lambda c: -c["bytes"])
    sample = candidates[:tune["sample_size"]]

    print(f"R8/R9 candidates: {len(candidates)} synthesis-heavy pages "
          f"(body >= {tune['min_body_bytes']}B, sources >= {tune['min_sources']}); "
          f"showing {len(sample)}")
    r8_hits = 0
    for c in sample:
        flag = ""
        if c["inferred"] == 0:
            flag = "  <-- R8: no ^[inferred] on a synthesis-heavy page"
            r8_hits += 1
        print(f"{c['rel']} | inferred={c['inferred']} | conf={c['confidence']} "
              f"| sources={c['sources']} | {c['bytes']}B{flag}")
    print(f"\nR8 findings in sample: {r8_hits}")
    print("R9: re-derive claims on the `confidence: high` rows above against their "
          "cited sources; downgrade any that do not trace.")


if __name__ == "__main__":
    main()
