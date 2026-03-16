#!/usr/bin/env python3
"""Regenerate HTML reports from cached scan.json (skips the fetch step).

Usage:
    python scripts/regen_html.py [repo]

Optional repo argument defaults to "runtime".
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_reports import build_reports


def main() -> None:
    repo = sys.argv[1] if len(sys.argv) > 1 else "runtime"

    scan_path = Path(__file__).resolve().parent.parent / "pages" / repo / "scan.json"
    if not scan_path.exists():
        print(
            f"✗ No cached data at {scan_path}\n"
            f"  Run fetch first:  python scripts/fetch_issues.py {repo}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Regenerating HTML from cached scan.json for {repo}...")
    build_reports(repo)


if __name__ == "__main__":
    main()
