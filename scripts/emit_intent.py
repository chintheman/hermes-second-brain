#!/usr/bin/env python3
"""emit_intent.py — queue one schema-valid deposit-intent file.

Usage:
  emit_intent.py --skill brain-capture --session <session-id>
                 [--vault ~/wiki] [--dry-run] < intents.json

Reads a JSON array of intent objects from stdin (or --intents-file) and writes
ONE file to <vault>/_system/pending-deposits/<YYYYMMDDTHHMMSS>-<skill>.yaml,
per BRAIN.md §6 (one YAML file per session per skill). The updater drains it.

This is the only engine component that writes to pending-deposits/. It is
deliberately dumb about *content*: what to deposit is a judgment call owned by
the calling agent. What it enforces, in code rather than in prose:

  - action is one of the BRAIN.md §6 enum values
  - page path, knowledge, provenance, confidence are present and legal
  - no key outside the §6 schema (notably `tags` — the schema has none, and the
    only rejected fixture in the vault died on a rogue tag)
  - lists serialize INLINE (`sources: [a, b]`); block/dash lists degrade to a
    concatenated string in the frontmatter parser (rebuild_index.py)
  - `session` is required — it is the provenance trail transcript → intent →
    commit (BRAIN.md §6, §8)

Stdlib only. No vault path is hardcoded: --vault parameterizes everything.
Exit codes: 0 ok, 2 IntentValidationError.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

ACTIONS = {
    "update_entity", "create_entity", "update_concept", "create_concept",
    "create_decision", "create_project", "update_project", "create_source",
    "update_moc",
    "log_only",
}
PROVENANCE = {"extracted", "inferred", "ambiguous"}
CONFIDENCE = {"high", "medium", "low"}

# Folder is the category (BRAIN.md v1.3). An action names a page KIND, so it also
# names the only directory that page may live in. Enforced here because this is
# the write seam: an intent that files a person under concepts/ is a filing error
# the updater would otherwise apply faithfully. `log_only` is exempt — it records
# narrative and touches no page.
ACTION_DIR = {
    "create_entity": "entities/", "update_entity": "entities/",
    "create_concept": "concepts/", "update_concept": "concepts/",
    "create_decision": "decisions/",
    "create_project": "projects/", "update_project": "projects/",
    "create_source": "sources/",
    "update_moc": "mocs/",
}

# Field order is the BRAIN.md §6 order; anything outside this set is rejected.
SCALAR_FIELDS = ["action", "page", "knowledge", "provenance", "confidence"]
LIST_FIELDS = ["sources", "contradicts"]
ALLOWED_FIELDS = set(SCALAR_FIELDS) | set(LIST_FIELDS)
EMIT_ORDER = ["action", "page", "knowledge", "provenance", "sources",
              "confidence", "contradicts"]


class IntentValidationError(Exception):
    """An intent that would be rejected by the updater. Fail here, not there."""


def _yaml_scalar(value):
    """Double-quoted YAML scalar, safe for colons, quotes, and newlines."""
    s = str(value)
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    s = re.sub(r"\s*\n\s*", " ", s).strip()
    return f'"{s}"'


def _yaml_inline_list(items, field):
    """Inline list only (BRAIN.md §6). Items must not need quoting."""
    out = []
    for item in items:
        s = str(item).strip()
        if not s:
            raise IntentValidationError(f"{field}: empty list item")
        if any(c in s for c in ',[]"\n'):
            raise IntentValidationError(
                f"{field}: item {s!r} contains a character that cannot appear "
                "in an inline list"
            )
        out.append(s)
    return "[" + ", ".join(out) + "]"


def validate_intent(intent, idx=0):
    """Raise IntentValidationError unless this intent matches BRAIN.md §6."""
    where = f"intent[{idx}]"
    if not isinstance(intent, dict):
        raise IntentValidationError(f"{where}: not a mapping")

    unknown = sorted(set(intent) - ALLOWED_FIELDS)
    if unknown:
        raise IntentValidationError(
            f"{where}: field(s) not in the BRAIN.md §6 schema: "
            f"{', '.join(unknown)}"
        )

    action = str(intent.get("action", "")).strip()
    if action not in ACTIONS:
        raise IntentValidationError(
            f"{where}: action {action!r} not in {sorted(ACTIONS)}"
        )

    page = str(intent.get("page", "")).strip()
    if not page:
        raise IntentValidationError(f"{where}: page is required and non-empty")
    if page.startswith("/") or ".." in page.split("/"):
        raise IntentValidationError(
            f"{where}: page {page!r} must be a vault-relative path"
        )

    if action != "log_only":
        if not page.endswith(".md"):
            raise IntentValidationError(
                f"{where}: page {page!r} must name a .md file"
            )
        tail = page.split("/", 1)[1] if "/" in page else ""
        if not tail or tail.startswith((".", "_")) or "/_" in tail or "/." in tail:
            raise IntentValidationError(
                f"{where}: page {page!r} must be a real page path; dot- and "
                "underscore-prefixed segments are not page directories"
            )

    required_dir = ACTION_DIR.get(action)
    if required_dir and not page.startswith(required_dir):
        raise IntentValidationError(
            f"{where}: action {action!r} must target {required_dir}, got {page!r}. "
            "Folder is the category (BRAIN.md v1.3): the action names the page "
            "kind, so it names the directory."
        )

    knowledge = str(intent.get("knowledge", "")).strip()
    if not knowledge:
        raise IntentValidationError(
            f"{where}: knowledge is required — the actual knowledge to deposit, "
            "not a description of it"
        )

    provenance = str(intent.get("provenance", "")).strip()
    if provenance not in PROVENANCE:
        raise IntentValidationError(
            f"{where}: provenance {provenance!r} not in {sorted(PROVENANCE)}"
        )

    confidence = str(intent.get("confidence", "")).strip()
    if confidence not in CONFIDENCE:
        raise IntentValidationError(
            f"{where}: confidence {confidence!r} not in {sorted(CONFIDENCE)}"
        )

    for field in LIST_FIELDS:
        value = intent.get(field, [])
        if isinstance(value, str) or not isinstance(value, (list, tuple)):
            raise IntentValidationError(f"{where}: {field} must be a list")


def render_intent_file(skill, session, intents, emitted):
    """Serialize one deposit-intent file. Inline lists only."""
    skill = str(skill).strip()
    session = str(session).strip()
    if not skill:
        raise IntentValidationError("skill is required")
    if not session:
        raise IntentValidationError(
            "session is required — it is the provenance trail linking "
            "transcript → intent → commit (BRAIN.md §6)"
        )
    if not intents:
        raise IntentValidationError("intents is required and non-empty")

    lines = [
        f"skill: {skill}",
        f"session: {session}",
        f"emitted: {emitted.isoformat(timespec='seconds')}",
        "intents:",
    ]
    for idx, intent in enumerate(intents):
        validate_intent(intent, idx)
        first = True
        for field in EMIT_ORDER:
            if field in LIST_FIELDS:
                rendered = _yaml_inline_list(intent.get(field, []), field)
            elif field == "knowledge":
                rendered = _yaml_scalar(intent[field])
            else:
                rendered = str(intent[field]).strip()
            prefix = "  - " if first else "    "
            lines.append(f"{prefix}{field}: {rendered}")
            first = False
    return "\n".join(lines) + "\n"


def intent_path(vault, skill, emitted):
    """<vault>/_system/pending-deposits/<YYYYMMDDTHHMMSS>-<skill>.yaml, with
    -2/-3 collision suffixes (BRAIN.md §6)."""
    queue = os.path.join(os.path.expanduser(vault), "_system", "pending-deposits")
    slug = re.sub(r"[^a-z0-9-]+", "-", str(skill).lower()).strip("-")[:60]
    if not slug:
        raise IntentValidationError("skill must contain alphanumerics")
    base = f"{emitted.strftime('%Y%m%dT%H%M%S')}-{slug}"
    path = os.path.join(queue, base + ".yaml")
    n = 2
    while os.path.exists(path):
        path = os.path.join(queue, f"{base}-{n}.yaml")
        n += 1
    return path


def emit_intent(vault, skill, session, intents, emitted=None, dry_run=False):
    """Write one schema-valid deposit-intent file to
    <vault>/_system/pending-deposits/. Returns the written path (in dry-run,
    the path it would have written, after printing the file to stdout).
    Raises IntentValidationError on anything the updater would reject."""
    emitted = emitted or dt.datetime.now().astimezone()
    text = render_intent_file(skill, session, intents, emitted)
    path = intent_path(vault, skill, emitted)
    if dry_run:
        print(f"# --dry-run: would write {path}")
        print(text, end="")
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--skill", required=True)
    ap.add_argument("--session", required=True,
                    help="session id — REQUIRED (BRAIN.md §6 provenance trail)")
    ap.add_argument("--vault", default=os.path.expanduser("~/wiki"))
    ap.add_argument("--intents-file", default="",
                    help="JSON array of intents (default: read stdin)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the file instead of writing it")
    args = ap.parse_args()

    if args.intents_file:
        with open(args.intents_file, encoding="utf-8") as f:
            payload = f.read()
    else:
        payload = sys.stdin.read()
    try:
        intents = json.loads(payload)
    except json.JSONDecodeError as e:
        print(f"emit_intent: intents are not valid JSON: {e}", file=sys.stderr)
        sys.exit(2)
    if isinstance(intents, dict):
        intents = [intents]

    try:
        path = emit_intent(args.vault, args.skill, args.session, intents,
                           dry_run=args.dry_run)
    except IntentValidationError as e:
        print(f"emit_intent: {e}", file=sys.stderr)
        sys.exit(2)
    if not args.dry_run:
        print(path)


if __name__ == "__main__":
    main()
