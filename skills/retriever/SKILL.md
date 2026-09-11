---
name: retriever
category: brain-core
trigger: Every session start, and any query against the brain. Read-only.
authority: read
---

# Retriever

Read-oriented memory lookup. This role NEVER writes to the vault.

## Procedure

1. Read `~/wiki/_system/index.md` in full. This is mandatory at session start
   even if the task seems unrelated — the index tells you what the brain knows.
2. From the query or task, identify candidate pages by category (entities,
   concepts, mocs, projects, decisions, sources).
3. Read candidate pages individually. Do not read directories wholesale.
4. Escalate only if the index scan is insufficient:
   a. Honcho semantic search — conceptual "what do we know about X".
   b. session_search (FTS5) — "what did we discuss about X" in transcripts.
   c. search_files regex — exact term or filename hunting.
5. Return findings with page references (`[[wikilinks]]`) so downstream steps
   can cite and so deposits can link correctly.

## Rules

- Respect `superseded_by`: if a page or claim is superseded, follow the link
  and report the current knowledge, noting the supersession when relevant.
- Report `confidence` and provenance marks to the consumer of the lookup —
  an `^[inferred]` claim is not the same as an extracted one.
- If the index looks stale (references pages that don't exist, or a page you
  just read isn't listed), note it — that is lint rule 4 evidence — but do NOT
  fix it yourself. Emit a `log_only` intent describing the drift.
