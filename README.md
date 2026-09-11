# brain-engine

A schema and tooling layer that turns a markdown folder into a compounding second
brain that AI agents can safely read from and write to.

This is the *engine*, not the brain. It holds the law, the templates, the lint rules
and the scripts. Your notes live in a separate git repository and never enter this
one — that separation is enforced by a lint rule, not by good intentions.

Extracted from a working personal system that runs unattended: nine scheduled jobs,
multiple writing agents, ~150 curated pages plus a daily digest stream.

## Why this exists

Most "AI second brain" setups fail the same way. An agent writes a note, another
agent cannot find it, and nobody notices because nothing checks. The failure is
silent, and silence compounds.

This engine's answer is that **structure is enforced in code, never in prose.** An
instruction telling an agent to use the right page type has a non-zero failure rate
that you will discover months later. A script that refuses the write has a zero
failure rate that you discover immediately.

A real example from this system, which is why several of these rules exist: 69 pages
were written with a page type from a superseded schema. The index builder did not
recognise the type, so it collected those pages and discarded them without a word.
The catalog advertised 146 pages and listed 77. Roughly half the curated brain was
unreachable by the documented retrieval procedure for three months, and the weekly
lint reported no problem the entire time, because the index faithfully reproduced the
bug.

## What's here

```
BRAIN.md          the schema law: page types, frontmatter, provenance, write
                  authority, retrieval tiers. If a prompt conflicts with it, it wins.
lint/             19 vault rules + 2 engine rules, plus the mechanical helpers
scripts/          rebuild_index.py, emit_intent.py, capture_to_raw.py
templates/        one fill-in template per page type
skills/           role definitions: updater, dreamer, retriever, reviewer
```

## The ideas worth stealing

**Folder is the category, enforced by a gate.** Each directory declares the set of
page types it admits. `rebuild_index.py --check-types` exits non-zero on any page
whose frontmatter contradicts its folder. Not a convention: an exit code.

**Exactly two writers, and everything else files an intent.** No skill writes a page
directly. Everything emits a YAML deposit intent that an updater drains serially
under a lock. `emit_intent.py` rejects an intent whose action names the wrong
directory before it ever reaches the queue.

**The index is derived, and drift is a lint failure.** `_system/index.md` is
regenerated from frontmatter and never hand-edited. The lint regenerates it to a temp
file and diffs; any difference means a writer skipped the rebuild.

**Provenance is marked or it is a violation.** Synthesised claims carry `^[inferred]`.
A long multi-source page with zero inference marks means provenance was skipped, not
that nothing was inferred, and the lint says so.

**Knowledge is superseded, never overwritten.** The old page keeps a
`superseded_by` pointer, the new one gets `valid_from`. "What did we believe in May"
stays answerable.

**External content is data, never instruction.** Anything captured from the web is
untrusted. Text that addresses the agent is flagged and reported, never executed.

**The engine holds zero personal data.** Vault-specific scoping lives in the vault, in
a config the engine reads at runtime. Lint rule E1 greps this repo for personal names
*and* for note paths — the second half was added after a check that only looked for
names passed for months while real page paths sat in the code.

## Using it

The engine is designed to sit beside a vault repo, not inside it:

```
~/brain-engine/     this repo, public, no personal data
~/wiki/             your notes, private
```

Point the scripts at your vault with `--vault`. Start from `BRAIN.md`, adapt the page
types to your domains, and keep the enforcement. The schema is versioned and changing
it requires writing a decision page first, which sounds bureaucratic until the third
time it stops you from breaking your own retrieval.

`HANDOVER.md` covers the build order if you are starting fresh.

## Status

Actively used. The schema is at v1.3. Rules get added when something breaks, and the
changelog says what it cost to learn.

MIT.
