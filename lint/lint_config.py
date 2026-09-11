#!/usr/bin/env python3
"""Vault-specific lint scoping, loaded from the vault — never hardcoded here.

This engine repo is PUBLIC and BRAIN.md §12 / lint rule E1 require it to hold zero
personal data. Three helpers previously hardcoded real vault page paths and personal
directory names, which reached origin/main. E1 passed throughout because it grepped
for personal NAMES only, never for vault PATHS.

Scoping now comes from <vault>/_system/lint-config.yaml, which lives in the private
vault. If that file is absent the defaults below apply: they are derived from
BRAIN.md §1's published layout and name nothing personal, so the engine stays
runnable standalone without ever learning anything about a particular vault.
"""
import os

# BRAIN.md §1 page directories. Structural, not personal.
DEFAULT_CORE_DIRS = ("entities/", "concepts/", "mocs/", "decisions/",
                     "sources/", "references/", "projects/")
# BRAIN.md §1 non-page layers. Structural, not personal.
DEFAULT_EXCLUDED_PREFIXES = ("raw/", "corpus/", "overlays/", "site/")
DEFAULT_EXCLUDED_BASENAMES = ("log.md", "index.md", "INDEX.md", "README.md",
                              "AGENTS.md", "RESOLVER.md", "SCHEMA.md")
DEFAULT_R8R9 = {"min_body_bytes": 4000, "min_sources": 1, "sample_size": 12}


def load(vault):
    """Return the scoping config for `vault`, falling back to schema defaults."""
    cfg = {
        "core_dirs": list(DEFAULT_CORE_DIRS),
        "excluded_prefixes": list(DEFAULT_EXCLUDED_PREFIXES),
        "excluded_basenames": list(DEFAULT_EXCLUDED_BASENAMES),
        "r8r9": dict(DEFAULT_R8R9),
    }
    path = os.path.join(vault, "_system", "lint-config.yaml")
    if not os.path.exists(path):
        return cfg
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
    except Exception as exc:              # missing yaml, unreadable, malformed
        print(f"WARN: lint-config unreadable ({exc}); using schema defaults")
        return cfg
    if not isinstance(loaded, dict):
        print("WARN: lint-config is not a mapping; using schema defaults")
        return cfg
    for key in ("core_dirs", "excluded_prefixes", "excluded_basenames"):
        if isinstance(loaded.get(key), list) and loaded[key]:
            cfg[key] = [str(v) for v in loaded[key]]
    if isinstance(loaded.get("r8r9"), dict):
        # Validate the VALUE, not just the key: a string where an int belongs used
        # to crash check_r8r9 at its first comparison.
        for k, v in loaded["r8r9"].items():
            if k in DEFAULT_R8R9 and isinstance(v, int) and not isinstance(v, bool):
                cfg["r8r9"][k] = v
            elif k in DEFAULT_R8R9:
                print(f"WARN: lint-config r8r9.{k}={v!r} is not an integer; "
                      f"using default {DEFAULT_R8R9[k]}")
    return cfg


def is_core(rel, cfg):
    """True when `rel` (vault-relative) is a page the lint should grade."""
    if rel.startswith(("_", ".")):
        return False
    if rel.startswith(tuple(cfg["excluded_prefixes"])):
        return False
    if not rel.startswith(tuple(cfg["core_dirs"])):
        return False
    base = os.path.basename(rel)
    if base in cfg["excluded_basenames"]:
        return False
    # Digests are a machine-produced daily stream; they are pages, but grading them
    # as curated content buries the real ones (BRAIN.md v1.3, type: digest).
    if "digest" in base.lower():
        return False
    return True
