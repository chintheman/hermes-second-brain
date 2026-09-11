#!/usr/bin/env python3
"""capture_to_raw.py — land a source in the immutable raw/ archive.

Usage:
  capture_to_raw.py --desc "meeting-notes-design-review" [--url URL]
                    [--method web_extract|pa-intake|upload|ocr|manual]
                    [--vault ~/wiki] [--commit]
                    [--emit-intent --session <id> [--skill brain-capture]]
                    < content.md

Reads content from stdin, writes ~/wiki/raw/YYYY-MM/YYYY-MM-DD-<desc>.md with
capture frontmatter. Refuses to overwrite (raw/ is append-only): collisions
get a -2, -3 suffix. With --commit, git-commits as 'capture: <desc>'.

With --emit-intent it also queues exactly ONE `create_source` deposit intent so
the capture cannot terminate without an ingest hook (BRAIN.md §7 steps 1-2).
It never emits create_concept/update_* — those are judgment calls on content,
owned by the calling agent (devops:brain-capture), which appends them to the
same intent file. provenance/confidence are hardcoded extracted/medium: every
capture is an untrusted web capture, which caps at medium (BRAIN.md §0.6).

stdout is always exactly the landed raw path, one line — callers parse it.
Everything else (intent path, lock notes, errors) goes to stderr.

Exit codes: 0 landed (committed, or commit deliberately skipped); 2 bad args /
rejected intent; 3 landed but NOT committed (hook or git refused) — the raw
file and intent are on disk, do NOT re-run capture.

Wire this into every capture pipeline (PA intake, web_extract, competitor
monitors) BEFORE any processing happens.
"""
import argparse
import datetime as dt
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emit_intent import IntentValidationError, emit_intent  # noqa: E402

LOCK_STALE_MINUTES = 60  # BRAIN.md §5: a lock older than this is stale


def lock_age_minutes(lock_path):
    """Age of the vault write-lock in minutes, or None if there is no lock.
    Computed in Python — shell `date` arithmetic is not portable here."""
    try:
        mtime = os.path.getmtime(lock_path)
    except OSError:
        return None
    now = dt.datetime.now().timestamp()
    return max(0.0, (now - mtime) / 60.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--desc", required=True)
    ap.add_argument("--url", default="")
    ap.add_argument("--method", default="manual")
    ap.add_argument("--vault", default=os.path.expanduser("~/wiki"))
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--emit-intent", action="store_true",
                    help="also queue a create_source deposit intent for this capture")
    ap.add_argument("--session", default="",
                    help="session id — REQUIRED with --emit-intent (BRAIN.md §6)")
    ap.add_argument("--skill", default="brain-capture",
                    help="skill name recorded in the intent file")
    args = ap.parse_args()

    if args.emit_intent:
        if not args.session.strip():
            ap.error("--session is required with --emit-intent: it is the "
                     "provenance trail linking transcript -> intent -> commit "
                     "(BRAIN.md §6)")
        if not args.url.strip():
            ap.error("--url is required with --emit-intent: a source page that "
                     "cites no URL is not a source page")

    content = sys.stdin.read()
    if not content.strip():
        sys.exit("capture_to_raw: empty stdin, nothing captured")

    now = dt.datetime.now().astimezone()
    slug = re.sub(r"[^a-z0-9-]+", "-", args.desc.lower()).strip("-")[:80]
    month_dir = os.path.join(args.vault, "raw", now.strftime("%Y-%m"))
    os.makedirs(month_dir, exist_ok=True)

    base = f"{now.strftime('%Y-%m-%d')}-{slug}"
    path = os.path.join(month_dir, base + ".md")
    n = 2
    while os.path.exists(path):  # append-only: never overwrite
        path = os.path.join(month_dir, f"{base}-{n}.md")
        n += 1

    fm = (
        "---\n"
        f'captured: "{now.isoformat(timespec="seconds")}"\n'
        f'source_url: "{args.url}"\n'
        f'capture_method: "{args.method}"\n'
        "immutable: true\n"
        "---\n\n"
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(fm + content)
    print(path)

    paths = [path]
    if args.emit_intent:
        rel_raw = os.path.relpath(path, args.vault)
        intent = {
            "action": "create_source",
            "page": f"sources/{slug}.md",
            "knowledge": (
                f"Raw capture \"{args.desc}\" landed {now.strftime('%Y-%m-%d')} "
                f"from {args.url} via {args.method}. The full untouched text is "
                f"at {rel_raw}; key claims are to be extracted from that file."
            ),
            # Untrusted web capture: extracted/medium is not a guess, it is the
            # cap BRAIN.md §0.6 imposes. Never raise it here.
            "provenance": "extracted",
            "confidence": "medium",
            "sources": [rel_raw],
            "contradicts": [],
        }
        try:
            intent_file = emit_intent(args.vault, args.skill, args.session,
                                      [intent], emitted=now)
        except IntentValidationError as e:
            print(f"capture_to_raw: intent rejected before queueing: {e}",
                  file=sys.stderr)
            sys.exit(2)
        print(f"capture_to_raw: queued intent {intent_file}", file=sys.stderr)
        paths.append(intent_file)

    if args.commit:
        lock = os.path.join(args.vault, "_system", ".write-lock")
        lock_age = lock_age_minutes(lock)
        if lock_age is not None and lock_age < LOCK_STALE_MINUTES:
            print(
                f"capture_to_raw: {lock} held ({lock_age:.0f}m old) — commit "
                "SKIPPED to avoid stealing the writer's staged work. Landed: "
                + ", ".join(paths),
                file=sys.stderr,
            )
            return
        try:
            subprocess.run(["git", "-C", args.vault, "add", *paths], check=True)
            # Pathspec commit: the vault index routinely holds other agents'
            # staged work, and an unscoped commit would sweep it in.
            subprocess.run(
                ["git", "-C", args.vault, "commit", "-m", f"capture: {slug}",
                 "--", *paths],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            # The write already succeeded. Never --no-verify (the pre-commit
            # hook is a secrets scanner) and never retry capture: a retry
            # duplicates the raw file into an append-only layer.
            print(
                f"capture_to_raw: git refused the commit (exit {e.returncode}). "
                "Landed but NOT committed: " + ", ".join(paths) + " — inspect "
                "the hook output, then commit by hand. Do NOT re-run capture.",
                file=sys.stderr,
            )
            sys.exit(3)


if __name__ == "__main__":
    main()
