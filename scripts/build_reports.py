#!/usr/bin/env python3
"""Build HTML reports, meta.json, and history.json from scan.json.

Usage:
    python scripts/build_reports.py runtime

Reads pages/<repo>/scan.json (produced by fetch_issues.py).
Outputs:
  - pages/<repo>/needs-attention.html
  - pages/<repo>/unattended.html
  - pages/<repo>/stale.html
  - pages/<repo>/all.html
  - pages/<repo>/meta.json
  - pages/<repo>/history.json  (appends, keeps last 90 days)
"""

from __future__ import annotations

import json
import statistics
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from html_template import render_report

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ORG = "dotnet"
HISTORY_RETENTION_DAYS = 90

REPORT_FILTERS = {
    "needs-attention": lambda issues: sorted(
        [i for i in issues if (i.get("urgency_score", 0) or 0) > 2.0],
        key=lambda i: i.get("urgency_score", 0) or 0,
        reverse=True,
    ),
    "unattended": lambda issues: sorted(
        [i for i in issues if (i.get("neglect_score", 0) or 0) > 5.0],
        key=lambda i: i.get("neglect_score", 0) or 0,
        reverse=True,
    ),
    "stale": lambda issues: sorted(
        [i for i in issues if (i.get("staleness_score", 0) or 0) > 5.0],
        key=lambda i: i.get("staleness_score", 0) or 0,
        reverse=True,
    ),
    "all": lambda issues: sorted(
        issues, key=lambda i: i.get("number", 0) or 0
    ),
}


def _load_scan(repo_dir: Path) -> list[dict]:
    """Load issues from scan.json."""
    scan_path = repo_dir / "scan.json"
    if not scan_path.exists():
        print(f"✗ {scan_path} not found. Run fetch_issues.py first.", file=sys.stderr)
        sys.exit(1)

    with open(scan_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data if isinstance(data, list) else data.get("issues", [])


def _build_filtered(issues: list[dict]) -> dict[str, list[dict]]:
    """Apply report filters and return {report_type: filtered_issues}."""
    return {rt: fn(issues) for rt, fn in REPORT_FILTERS.items()}


def _generate_html_reports(
    filtered: dict[str, list[dict]],
    repo: str,
    repo_dir: Path,
    generated_at: str,
) -> None:
    """Write HTML report files."""
    # Build nav-badge counts
    meta = {
        "counts": {
            rt.replace("-", "_"): len(issues)
            for rt, issues in filtered.items()
        }
    }

    for report_type, issues in filtered.items():
        html_content = render_report(
            report_type=report_type,
            issues=issues,
            repo=repo,
            generated_at=generated_at,
            meta=meta,
        )
        out_file = repo_dir / f"{report_type}.html"
        out_file.write_text(html_content, encoding="utf-8")
        print(f"  ✓ {out_file.name} ({len(issues)} issues)")


def _safe_avg(values: list[float]) -> float:
    """Average that returns 0.0 for empty list."""
    return round(sum(values) / len(values), 1) if values else 0.0


def _generate_meta(
    issues: list[dict],
    filtered: dict[str, list[dict]],
    repo: str,
    repo_dir: Path,
    generated_at: str,
) -> dict:
    """Write meta.json and return the meta dict."""
    total_24h = sum(i.get("hits_24h", 0) or 0 for i in issues)
    total_7d = sum(i.get("hits_7d", 0) or 0 for i in issues)

    meta = {
        "repo": repo,
        "org": ORG,
        "generated_at": generated_at,
        "total_issues": len(issues),
        "needs_attention_count": len(filtered["needs-attention"]),
        "unattended_count": len(filtered["unattended"]),
        "stale_count": len(filtered["stale"]),
        "total_24h_hits": total_24h,
        "total_7d_hits": total_7d,
        "avg_urgency": _safe_avg([i.get("urgency_score", 0) or 0 for i in issues]),
        "avg_neglect": _safe_avg([i.get("neglect_score", 0) or 0 for i in issues]),
        "avg_staleness": _safe_avg([i.get("staleness_score", 0) or 0 for i in issues]),
        "counts": {
            rt.replace("-", "_"): len(iss) for rt, iss in filtered.items()
        },
    }

    meta_path = repo_dir / "meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"  ✓ meta.json")

    return meta


def _update_history(
    issues: list[dict],
    filtered: dict[str, list[dict]],
    repo_dir: Path,
    generated_at: str,
) -> None:
    """Append entry to history.json, keeping last 90 days."""
    history_path = repo_dir / "history.json"

    history: list[dict] = []
    if history_path.exists():
        try:
            with open(history_path, "r", encoding="utf-8") as f:
                history = json.load(f)
        except (json.JSONDecodeError, ValueError):
            history = []

    ages = [i.get("age_days", 0) or 0 for i in issues]
    median_age = round(statistics.median(ages)) if ages else 0

    entry = {
        "date": generated_at,
        "open_kbe_issues": len(issues),
        "total_24h_hits": sum(i.get("hits_24h", 0) or 0 for i in issues),
        "total_7d_hits": sum(i.get("hits_7d", 0) or 0 for i in issues),
        "unattended_count": len(filtered["unattended"]),
        "stale_count": len(filtered["stale"]),
        "median_age_days": median_age,
    }
    history.append(entry)

    # Prune entries older than 90 days
    cutoff = datetime.now(timezone.utc) - timedelta(days=HISTORY_RETENTION_DAYS)
    pruned = []
    for h in history:
        try:
            dt = datetime.fromisoformat(h["date"].replace("Z", "+00:00"))
            if dt >= cutoff:
                pruned.append(h)
        except (KeyError, ValueError):
            pruned.append(h)
    history = pruned

    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)
    print(f"  ✓ history.json ({len(history)} entries)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_reports(repo: str) -> None:
    """Full report generation pipeline for a single repo."""
    repo_dir = Path(__file__).resolve().parent.parent / "pages" / repo
    repo_dir.mkdir(parents=True, exist_ok=True)

    print(f"Building reports for {ORG}/{repo}...")

    issues = _load_scan(repo_dir)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    filtered = _build_filtered(issues)
    _generate_html_reports(filtered, repo, repo_dir, generated_at)
    _generate_meta(issues, filtered, repo, repo_dir, generated_at)
    _update_history(issues, filtered, repo_dir, generated_at)

    print(f"Done — {len(issues)} issues processed.")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/build_reports.py <repo>", file=sys.stderr)
        print("Example: python scripts/build_reports.py runtime", file=sys.stderr)
        sys.exit(1)

    repo = sys.argv[1]
    build_reports(repo)


if __name__ == "__main__":
    main()
