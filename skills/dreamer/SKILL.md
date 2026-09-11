---
name: dreamer
category: brain-core
trigger: Weekly cron ONLY. Never per-session.
authority: write (own commits, prefixed "dream:")
---

# Dreamer

Consolidation and restructuring. The dreamer keeps the vault coherent as it
grows: merging near-duplicates, weaving MOCs, tending the taxonomy, and
surfacing structure the per-session flow can't see. Conservative by default —
nuance is expensive to recreate and cheap to preserve.

## Procedure

1. Acquire `~/wiki/_system/.write-lock` per BRAIN.md §5 (exit if held and
   fresh; break + log if stale). Release when done, always.
2. Read `index.md`, the last two lint reports, and `log.md` entries since the
   previous dream run.
3. **Merge candidates.** Find concept pages covering the same idea. Merge only
   when overlap is near-total; otherwise cross-link and differentiate their
   Summaries instead. A merge must preserve all sources, all provenance marks,
   add `superseded_by` on the retired page (retired, not deleted), and update
   ALL inbound wikilinks to point at the surviving page in the same commit —
   or leave the retired page as a redirect stub if rewriting is unsafe.
4. **MOC weaving.** For each MOC: incorporate new member pages from recent
   deposits, keep the narrative thread coherent, and propose new MOCs when
   ≥5 related pages lack one.
5. **Orphan repair.** For lint-flagged orphans, add meaningful inbound links
   from related pages — or propose archival if the page is genuinely dead.
6. **Taxonomy tending.** Normalize rogue tags to canonical ones; propose new
   canonical tags (as edits to `taxonomy.md`) when ≥3 pages share an untagged
   theme.
7. **Missing pages.** For concepts repeatedly mentioned without a page (lint
   rule 6), create stubs with `confidence: low` and a clear TODO Summary.
8. Log one `## [date] dream | consolidation` entry summarizing actions.
9. Rebuild the index. Commit everything as `dream: <summary>` and push to the remote — dream commits
   must be separable in git history so over-consolidation is revertible.

## Rules

- When in doubt, link instead of merging. Destructive restructuring of pages
  marked `confidence: high` requires flagging in the log for human attention.
- Never touch `raw/`, `corpus/`, or `overlays/personal/` structure.
- Budget: if the run would touch more than ~15% of vault pages, stop, do the
  highest-value subset, and note the remainder for next week. Slow is fine.
