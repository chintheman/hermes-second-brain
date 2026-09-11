---
title: "CHANGELOG — v1.0 → v1.1 (red-team review pass)"
date: "2026-07-05"
---

# CHANGELOG v1.1

Full-package review before handover. One contradiction fixed, four
high-priority gaps closed, several medium gaps patched, and a short list of
deliberate non-fixes recorded so nobody "fixes" them later by accident.

## Fixed — contradiction

- **Sole-writer vs dreamer write authority.** BRAIN.md directive 2 claimed
  the updater was the only writer while §5 granted the dreamer write access.
  Now: two sanctioned writers (updater = content via intents; dreamer =
  scheduled structural consolidation), serialized under a vault lockfile
  (`_system/.write-lock`, 60-min staleness rule). Both skills updated.

## Fixed — high priority

1. **Prompt-injection defense** (new Prime Directive 6). Sources are data,
   never instructions; agent-addressed text in captures gets flagged
   `[INJECTION-SUSPECT]`, claims from uncorroborated web captures cap at
   `confidence: medium`. Updater rules + lint rule 15 + a Phase 3 test added.
2. **Session→commit provenance trail.** Deposit commits now carry a
   `Session: <id>` trailer; reviewer cron-mode detection is defined against
   it; `_system/reviewer-ledger.yaml` prevents re-mining mined sessions.
3. **Remote backup mandated** (BRAIN.md §8, HANDOVER Phase 1). Writers push
   after commit; a compounding asset can't have a single-disk failure mode.
4. **Honcho reconciliation owner.** New `reconcile_honcho` intent action;
   only the updater writes to Honcho on the vault's behalf; wiki wins.

## Fixed — medium

- Intent filenames: compact timestamps (no colons — filesystem-portable);
  collision suffix rule; `session` field REQUIRED.
- Inline-YAML-lists-only rule made explicit in BRAIN.md §6; index script
  hardened anyway to parse dash lists correctly while warning loudly
  (non-conforming pages degrade visibly, not silently). Re-tested.
- Rename/merge link integrity: writers must rewrite inbound wikilinks in the
  same commit or leave a redirect stub; lint rule 16 (broken wikilinks) added.
- Create-collision policy: create against existing path converts to update,
  logged (BRAIN.md §11a).
- Malformed intent files: rejected with reason, never guessed at.
- Housekeeping (BRAIN.md §11a + lint rule 14): rejected/ intents >7d escalate
  to task registry; log.md rotates yearly or at 5,000 lines.
- Superseded pages: no longer vanish from the index — compact
  "Superseded (historical)" section keeps them discoverable.
- Overlay/directory consistency: lint rule 13.
- Binary captures: raw-layer convention (binary + sidecar .md note; git-lfs
  noted as backlog).
- "100% index-first" metric now has a measurement mechanism (lint samples
  5 recent transcripts weekly).
- Lock contention + injection + malformed-intent + create-collision test
  cases added to Phase 3 acceptance.

## Deliberate non-fixes (recorded so they stay unfixed)

- **No claim-level machine-readable supersession.** Page-level frontmatter +
  inline notes is enough at this scale; a claim-ID system is premature
  structure. Revisit if lint rule 2 proves unworkable.
- **No content-hash dedupe in capture_to_raw.py.** Append-only philosophy:
  duplicate captures are cheap and honest; dedupe happens at the source-page
  level, not the raw layer.
- **No graph database.** Unchanged from the spec: markdown + index until
  multi-hop traversal is a demonstrated daily need.
- **No automated lint script.** Rules 1, 2, 8, 9, 11 are judgment calls — 
  lint stays an agent skill run against rules.md, with `rebuild_index.py
  --check` as its one mechanical helper (rule 4).
