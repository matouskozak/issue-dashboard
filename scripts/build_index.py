#!/usr/bin/env python3
"""Build the cross-repo dashboard index page.

Usage:
    python scripts/build_index.py

Reads pages/repos.json for the repo list, verifies each repo's meta.json
exists. The existing pages/index.html loads dynamically from repos.json +
meta.json via JavaScript, so this script just validates that all data
files are in place.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PAGES_DIR = Path(__file__).resolve().parent.parent / "pages"


def main() -> None:
    repos_path = PAGES_DIR / "repos.json"
    if not repos_path.exists():
        print(f"✗ {repos_path} not found.", file=sys.stderr)
        sys.exit(1)

    with open(repos_path, "r", encoding="utf-8") as f:
        repos = json.load(f)

    index_path = PAGES_DIR / "index.html"
    if not index_path.exists():
        print("✗ pages/index.html not found.", file=sys.stderr)
        sys.exit(1)

    print("Verifying dashboard index data...")

    ok = True
    for entry in repos:
        repo_path = entry.get("path", entry.get("repo", ""))
        meta_file = PAGES_DIR / repo_path / "meta.json"
        if meta_file.exists():
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
            total = meta.get("total_issues", "?")
            print(f"  ✓ {repo_path}/meta.json ({total} issues)")
        else:
            print(f"  ✗ {repo_path}/meta.json missing — run build_reports.py first")
            ok = False

    if ok:
        print("Dashboard index is ready. index.html loads data dynamically.")
    else:
        print("Warning: some meta.json files are missing.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
