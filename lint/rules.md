---
title: "Lint Rules v1"
version: "1.1"
schedule: "Weekly cron. Report to ~/wiki/_system/lint-reports/YYYY-MM-DD.md, committed as 'lint:'."
---

# Lint Rules

Lint is the sole error-catching mechanism in a full-autonomy vault. Every HIGH
finding, and every MED finding over its stated target for a second consecutive
cycle, must produce action — a deposit intent or a task-registry entry — not just
prose. **A finding carried as prose for three consecutive cycles is promoted to
HIGH**: it means the report is being read and ignored. Rule 10 spent eight cycles
over target with no action before this clause existed. Each report ends with a
scorecard against the success metrics.

| # | Rule | Severity | Check | Output |
|---|------|----------|-------|--------|
| 1 | Contradictions | HIGH | Compare claims across pages sharing entities/tags; include existing `[CONTRADICTS:]` flags awaiting resolution | Paired claims + proposed resolution (supersession or `^[ambiguous]`) as deposit intents |
| 2 | Stale claims | HIGH | Claims superseded by newer sources but not marked; broken `valid_from`/`superseded_by` chains | Supersession intents |
| 3 | Raw immutability | HIGH | `git log --diff-filter=MD -- raw/` since last lint must be empty | Violation report + offending commits |
| 4 | Index drift | HIGH | Regenerate index to temp; diff vs committed index.md | Zero-diff expected; else rebuild + investigate which writer skipped it |
| 5 | Orphan pages | MED | Pages with no inbound wikilinks (target <5%) | List → dreamer weaving queue |
| 6 | Missing pages | MED | Concepts/entities mentioned ≥3 times with no page | `create_*` stub intents |
| 7 | Rogue tags | MED | Tags not in taxonomy.md | Auto-fix intents (normalize) or taxonomy proposals |
| 8 | Provenance gaps | MED | Synthesis-heavy pages (multi-source, long Body) with zero `^[inferred]` marks | Flag for updater re-audit |
| 9 | Confidence audit | MED | Sample 5 `confidence: high` pages; re-derive claims from cited sources | Downgrade intents where claims don't trace |
| 10 | Stale pages | MED | Per type, over pages in `core_dirs` that carry a parseable `updated:`. Targets: `project` <10%, `entity` <25%, `moc` <25%. `concept`, `source`, `decision` and `digest` are NOT graded — a source is a reading of a fixed artifact and a decision is an event. `references/` is not graded: §2 exempts it from the frontmatter mandate. The report MUST print the denominator, and MUST report graded pages with no parseable `updated:` as a separate finding rather than folding them into a pass. A single vault-wide staleness percentage is itself a rule-10 violation. | Per-type table; one task-registry entry per over-target type, and one for the undated set |
| 11 | Data gaps | LOW | Questions the vault raises but can't answer; thin pages on active topics | Suggested web-search-and-ingest tasks |
| 12 | Queue health | HIGH | Any pending-deposits/ file older than 24h; rejected/ growth | Alert + immediate updater run |
| 13 | Overlay/dir consistency | MED | Page's `overlay:` field matches its directory (overlays/dev/ ⇒ dev, etc.); core types live outside overlays/ | Fix intents |
| 14 | Housekeeping | MED | rejected/ intents >7d → task-registry entries; log.md >5,000 lines → rotation due; reviewer-ledger parses | Task entries / rotation intent |
| 15 | Injection audit | HIGH | Grep vault for `[INJECTION-SUSPECT]` flags awaiting human review; sample recent web-sourced pages for unflagged instruction-like text | Report + task entries |
| 16 | Broken wikilinks | HIGH | All `[[links]]` resolve to existing pages (catches bad renames/merges) | Fix intents |
| 17 | Capture→ingest coverage | MED | Every `raw/**/*.md` older than 24h must be cited by some page's `sources:` OR have an intent naming it queued in `pending-deposits/`. Catches captures that landed and were never ingested (R12 watches queue *contents*, not queue *absence*) | `create_source` stub intents, one file per lint run |
| 18 | Type/folder mismatch | HIGH | `python3 scripts/rebuild_index.py --vault ~/wiki --check-types` (exit 3). A page whose `type` is not admitted by its folder. Distinct from rule 4: drift is fixed by rebuilding the index, a mismatch is not — it needs the frontmatter or the folder corrected. Superseded pages are exempt (a redirect sits at its old path by design) | Retype or move intents; a move rewrites inbound wikilinks in the same commit |
| 19 | Unresolved directory | MED | Any top-level directory or root `.md` file not classified in `~/wiki/RESOLVER.md`. Catches new working directories appearing without a filing ruling | RESOLVER update intent |

## Engine repo lint (run on ~/brain-engine, same cadence)

| # | Rule | Check |
|---|------|-------|
| E1 | Privacy boundary | Grep engine files for personal names, clients, vault content. Must be zero hits. **Also grep for vault PATHS**, not just names: `grep -rnE '(entities|concepts|projects|sources|mocs|decisions)/[a-z0-9-]+\.md' --include='*.py' --include='*.md' ~/brain-engine`. A page path is personal data. This clause was added 2026-09-11 after E1 passed for months while three helpers hardcoded 13 real vault page paths plus three personal directory names on a PUBLIC remote — the name-only grep could not see them. Vault-specific scoping belongs in `<vault>/_system/lint-config.yaml`, never in engine code. |
| E2 | Schema/skill drift | Skills reference only sections that exist in BRAIN.md at current version. |
