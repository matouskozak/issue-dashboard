#!/usr/bin/env python3
"""
html_template.py — HTML report template engine for KBE Issue Dashboard.

Generates report HTML files from scan data using Python string formatting.
No external template dependencies (no Jinja2).
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_report(
    report_type: str,
    issues: list[dict],
    repo: str,
    generated_at: str,
    meta: dict | None = None,
) -> str:
    """Return a complete HTML string for the given report type.

    Args:
        report_type: One of "needs-attention", "unattended", "stale", "all".
        issues: List of issue dicts from scan.json.
        repo: Repository slug, e.g. "runtime".
        generated_at: ISO-8601 timestamp string.
        meta: Optional metadata dict (history stats, counts, etc.).
    """
    title_map = {
        "needs-attention": "Needs Attention",
        "unattended": "Unattended Issues",
        "stale": "Stale Issues",
        "all": "All Issues",
    }
    report_title = title_map.get(report_type, report_type.replace("-", " ").title())

    stats = _compute_stats(issues)
    nav_html = _render_nav(report_type, meta)
    stats_bar_html = _render_stats_bar(stats)
    table_html = _render_table(issues, repo)

    return _PAGE_TEMPLATE.format(
        page_title=_esc(f"{report_title} — {repo} — KBE Dashboard"),
        report_type=_esc(report_type),
        report_title=_esc(report_title),
        repo=_esc(repo),
        generated_at=_esc(generated_at),
        issue_count=len(issues),
        nav=nav_html,
        stats_bar=stats_bar_html,
        table=table_html,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _esc(text: str) -> str:
    """HTML-escape a string."""
    return html.escape(str(text), quote=True)


def _severity_class(score: float) -> str:
    """Return CSS severity class name for a 0-10 score."""
    clamped = max(0, min(10, score))
    return f"severity-{round(clamped)}"


def _format_score(value: float) -> str:
    """Format a score to one decimal place."""
    return f"{value:.1f}"


def _compute_stats(issues: list[dict]) -> dict:
    """Compute summary stats from issue list."""
    total = len(issues)
    total_24h = sum(i.get("hits_24h", 0) or 0 for i in issues)
    urgencies = [i.get("urgency_score", 0) or 0 for i in issues]
    avg_urgency = sum(urgencies) / total if total else 0
    unattended = sum(
        1 for i in issues
        if (i.get("neglect_score", 0) or 0) > 5.0
    )
    return {
        "total": total,
        "total_24h": total_24h,
        "avg_urgency": avg_urgency,
        "unattended": unattended,
    }


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

def _render_nav(active: str, meta: dict | None) -> str:
    """Render the report-type navigation bar."""
    reports = [
        ("needs-attention", "Needs Attention", "needs_attention"),
        ("unattended", "Unattended", "unattended"),
        ("stale", "Stale", "stale"),
        ("all", "All Issues", "all"),
    ]
    links = []
    for slug, label, meta_key in reports:
        cls = "active" if slug == active else ""
        count = ""
        if meta and "counts" in meta:
            c = meta["counts"].get(meta_key)
            if c is not None:
                count = f'<span class="nav-count">{c}</span>'
        links.append(
            f'<a href="{slug}.html" class="{cls}">{_esc(label)}{count}</a>'
        )
    return '<nav class="report-nav">' + "".join(links) + "</nav>"


# ---------------------------------------------------------------------------
# Stats bar
# ---------------------------------------------------------------------------

def _render_stats_bar(stats: dict) -> str:
    """Render the summary statistics bar."""
    items = [
        ("Total Issues", str(stats["total"])),
        ("24h Hits", str(stats["total_24h"])),
        ("Avg Urgency", f"{stats['avg_urgency']:.1f}"),
        ("Unattended", str(stats["unattended"])),
    ]
    parts = []
    for label, value in items:
        parts.append(
            f'<div class="stat-item">'
            f'<span class="stat-value">{_esc(value)}</span>'
            f'<span class="stat-label">{_esc(label)}</span>'
            f"</div>"
        )
    return '<div class="stats-bar">' + "".join(parts) + "</div>"


# ---------------------------------------------------------------------------
# Score tooltip breakdown
# ---------------------------------------------------------------------------

def _render_score_tooltip(issue: dict, score_type: str) -> str:
    """Render the [?] tooltip with score breakdown."""
    breakdown_key = f"{score_type}_breakdown"
    breakdown = issue.get(breakdown_key) or issue.get("breakdown", {}).get(score_type)
    score = issue.get(f"{score_type}_score", 0) or 0

    if not breakdown:
        return ""

    lines = [f"{score_type.title()}: {_format_score(score)} / 10.0"]
    items = breakdown if isinstance(breakdown, list) else []
    for idx, item in enumerate(items):
        name = item.get("name", "?")
        raw = item.get("raw", 0)
        weight = item.get("weight", 0)
        value = item.get("value", raw * weight)
        prefix = "└─" if idx == len(items) - 1 else "├─"
        lines.append(
            f"{prefix} {name}: {raw:.2f} × {weight:.1f} = {value:.2f}"
        )

    tooltip_text = "\n".join(lines)
    return (
        f'<span class="tooltip-trigger">?'
        f'<span class="tooltip-content">{_esc(tooltip_text)}</span>'
        f"</span>"
    )


# ---------------------------------------------------------------------------
# Table rendering
# ---------------------------------------------------------------------------

_COLUMNS = [
    ("Urgency", "number", "80px"),
    ("Neglect", "number", "80px"),
    ("Staleness", "number", "80px"),
    ("Issue #", "number", "80px"),
    ("Title", "text", "350px"),
    ("24h Hits", "number", "70px"),
    ("7d Hits", "number", "70px"),
    ("30d Hits", "number", "70px"),
    ("Assignee", "text", "110px"),
    ("Last Human Activity", "number", "130px"),
    ("Area", "text", "140px"),
    ("Age", "number", "60px"),
    ("Labels", "text", "180px"),
]


def _render_table(issues: list[dict], repo: str) -> str:
    """Render the full data table."""
    # Header
    header_cells = []
    for col_name, sort_type, width in _COLUMNS:
        header_cells.append(
            f'<th data-sortable data-sort-type="{sort_type}" style="width:{width}">'
            f'{_esc(col_name)}<span class="sort-indicator">⇅</span>'
            f'<span class="col-resize"></span>'
            f"</th>"
        )
    header = "<tr>" + "".join(header_cells) + "</tr>"

    # Body rows
    rows = []
    for issue in issues:
        rows.append(_render_row(issue, repo))

    return (
        f'<div class="filter-bar">'
        f'<input type="text" id="filter-input" placeholder="Filter issues…" aria-label="Filter issues">'
        f'<span class="row-count" id="row-count"></span>'
        f"</div>"
        f'<div class="table-container">'
        f'<table class="data-table">'
        f"<thead>{header}</thead>"
        f'<tbody>{"".join(rows)}</tbody>'
        f"</table></div>"
    )


def _render_row(issue: dict, repo: str) -> str:
    """Render a single table row for an issue."""
    cells = []

    # --- Score cells (urgency, neglect, staleness) ---
    for score_key in ("urgency", "neglect", "staleness"):
        score = issue.get(f"{score_key}_score", 0) or 0
        sev = _severity_class(score)
        tooltip = _render_score_tooltip(issue, score_key)
        cells.append(
            f'<td class="score-td {sev}" data-sort-value="{score:.2f}">'
            f'<span class="score-cell">{_format_score(score)}{tooltip}</span>'
            f"</td>"
        )

    # --- Issue # ---
    number = issue.get("number", "")
    url = issue.get("url", f"https://github.com/dotnet/{repo}/issues/{number}")
    cells.append(
        f'<td data-sort-value="{number}">'
        f'<a href="{_esc(url)}" target="_blank" rel="noopener">#{number}</a>'
        f"</td>"
    )

    # --- Title ---
    title = issue.get("title", "")
    truncated = title[:80] + "…" if len(title) > 80 else title
    cells.append(
        f'<td class="title-cell" title="{_esc(title)}">{_esc(truncated)}</td>'
    )

    # --- Hit counts ---
    for hit_key in ("hits_24h", "hits_7d", "hits_30d"):
        val = issue.get(hit_key, 0) or 0
        bold_cls = "hits-active" if val > 0 and hit_key != "hits_30d" else ""
        cells.append(
            f'<td class="{bold_cls}" data-sort-value="{val}">{val}</td>'
        )

    # --- Assignee ---
    assignee = issue.get("assignee") or ""
    if assignee:
        cells.append(f"<td>{_esc(assignee)}</td>")
    else:
        cells.append('<td class="no-assignee">—</td>')

    # --- Last Human Activity ---
    last_human = issue.get("last_human_activity_days")
    if last_human is None:
        cells.append(
            '<td class="stale-activity" data-sort-value="99999">never</td>'
        )
    else:
        days = int(last_human)
        cls = "stale-activity" if days > 14 else ""
        cells.append(
            f'<td class="{cls}" data-sort-value="{days}">{days}d ago</td>'
        )

    # --- Area ---
    area = _extract_area(issue)
    cells.append(f"<td>{_esc(area)}</td>")

    # --- Age ---
    age = issue.get("age_days", 0) or 0
    cells.append(f'<td data-sort-value="{age}">{age}d</td>')

    # --- Labels ---
    labels_html = _render_labels(issue)
    cells.append(f"<td>{labels_html}</td>")

    return "<tr>" + "".join(cells) + "</tr>"


def _extract_area(issue: dict) -> str:
    """Extract area label from issue labels."""
    labels = issue.get("labels", [])
    if isinstance(labels, list):
        for lbl in labels:
            name = lbl if isinstance(lbl, str) else lbl.get("name", "")
            if name.lower().startswith("area-"):
                return name
    return ""


def _render_labels(issue: dict) -> str:
    """Render key labels as badge pills."""
    labels = issue.get("labels", [])
    if not isinstance(labels, list):
        return ""

    badges = []
    for lbl in labels:
        name = lbl if isinstance(lbl, str) else lbl.get("name", "")
        lower = name.lower()
        if lower == "blocking-clean-ci":
            badges.append(
                f'<span class="label-badge blocking">{_esc(name)}</span>'
            )
        elif lower == "untriaged":
            badges.append(
                f'<span class="label-badge untriaged">{_esc(name)}</span>'
            )
    return "".join(badges)


# ---------------------------------------------------------------------------
# Page template
# ---------------------------------------------------------------------------

_PAGE_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{page_title}</title>
  <link rel="stylesheet" href="../shared-styles.css">
</head>
<body data-report="{report_type}">
  <div class="page-container">
    <div class="report-header">
      <h1>{report_title}</h1>
      <p class="subtitle">dotnet/{repo} — Known Build Error issues</p>
      <div class="meta">
        <span>{issue_count} issues</span>
        <span id="last-updated" data-timestamp="{generated_at}">Updated…</span>
      </div>
    </div>

    {nav}

    {stats_bar}

    {table}
  </div>

  <script src="../shared-ui.js"></script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Generate HTML reports from a scan.json file."""
    if len(sys.argv) < 3:
        print("Usage: python html_template.py <scan.json> <output_dir> [repo]")
        print("Example: python html_template.py scan.json docs/runtime runtime")
        sys.exit(1)

    scan_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    repo = sys.argv[3] if len(sys.argv) > 3 else "runtime"

    with open(scan_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    issues = data if isinstance(data, list) else data.get("issues", [])
    from datetime import datetime, timezone

    generated_at = datetime.now(timezone.utc).isoformat()

    # Filter for each report type
    report_filters = {
        "needs-attention": lambda lst: sorted(
            lst, key=lambda i: i.get("urgency_score", 0) or 0, reverse=True
        ),
        "unattended": lambda lst: sorted(
            [i for i in lst if (i.get("neglect_score", 0) or 0) > 5.0],
            key=lambda i: i.get("neglect_score", 0) or 0,
            reverse=True,
        ),
        "stale": lambda lst: sorted(
            [i for i in lst if (i.get("staleness_score", 0) or 0) > 5.0],
            key=lambda i: i.get("staleness_score", 0) or 0,
            reverse=True,
        ),
        "all": lambda lst: lst,
    }

    output_dir.mkdir(parents=True, exist_ok=True)

    # Build metadata counts for nav badges
    meta = {"counts": {}}
    for report_type, filter_fn in report_filters.items():
        filtered = filter_fn(issues)
        meta_key = report_type.replace("-", "_")
        meta["counts"][meta_key] = len(filtered)

    for report_type, filter_fn in report_filters.items():
        filtered = filter_fn(issues)
        html_content = render_report(
            report_type=report_type,
            issues=filtered,
            repo=repo,
            generated_at=generated_at,
            meta=meta,
        )
        out_file = output_dir / f"{report_type}.html"
        out_file.write_text(html_content, encoding="utf-8")
        print(f"✓ Generated: {out_file} ({len(filtered)} issues)")

    # Write meta.json for the index page
    meta["generated_at"] = generated_at
    meta_file = output_dir / "meta.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"✓ Generated: {meta_file}")


if __name__ == "__main__":
    main()
