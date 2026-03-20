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
    score_guide_html = _render_score_guide()
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
        score_guide=score_guide_html,
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
# Score guide
# ---------------------------------------------------------------------------

def _render_score_guide() -> str:
    """Render a collapsible score explanation section."""
    return (
        '<details class="score-guide">'
        '<summary>Score Guide — what do the numbers mean?'
        '<span class="chevron">▶</span></summary>'
        '<div class="score-guide-body">'
        # Urgency card
        '<div class="score-guide-card">'
        '<h3>Urgency (0–10)</h3>'
        '<p class="guide-question">How urgently does this issue need attention?</p>'
        "<ul>"
        "<li>24-hour and 7-day hit counts</li>"
        "<li>Hit trend (acceleration)</li>"
        "<li>blocking-clean-ci label</li>"
        "<li>Issue age vs hit volume</li>"
        "<li>Whether unassigned</li>"
        "</ul>"
        '<p class="guide-hint">Higher = more urgent. Many recent hits, accelerating trends, '
        "or blocking labels push the score up.</p>"
        "</div>"
        # Neglect card
        '<div class="score-guide-card">'
        '<h3>Neglect (0–10)</h3>'
        '<p class="guide-question">Is this issue being ignored despite being active?</p>'
        "<ul>"
        "<li>Hits with no assignee</li>"
        "<li>Hits with no human comments</li>"
        "<li>High hits + untriaged label</li>"
        "<li>Days since last human comment</li>"
        "<li>Missing area label</li>"
        "</ul>"
        '<p class="guide-hint">Higher = more neglected. Active issues with no one '
        "investigating score highest.</p>"
        "</div>"
        # Staleness card
        '<div class="score-guide-card">'
        '<h3>Staleness (0–10)</h3>'
        '<p class="guide-question">Is this issue likely resolved or stale?</p>'
        "<ul>"
        "<li>Zero 24-hour hits</li>"
        "<li>Zero 7-day hits</li>"
        "<li>Days since last update</li>"
        "<li>Issue age</li>"
        "<li>Low monthly hit count</li>"
        "</ul>"
        '<p class="guide-hint">Higher = more stale. Issues with no recent hits and '
        "no recent updates score highest.</p>"
        "</div>"
        "</div>"
        "</details>"
    )


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
    ("Last Activity", "number", "110px"),
    ("Area", "text", "140px"),
    ("Age", "number", "60px"),
    ("Labels", "text", "280px"),
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
        f'<label class="mobile-filter-toggle">'
        f'<input type="checkbox" id="mobile-filter-checkbox">'
        f'<span class="toggle-label">Show only mobile/mono issues</span>'
        f'</label>'
        f'<label class="mobile-filter-toggle">'
        f'<input type="checkbox" id="no-hits-filter-checkbox">'
        f'<span class="toggle-label">Show only no-hit issues</span>'
        f'</label>'
        f'<label class="mobile-filter-toggle"'
        f' title="Issues with a known area label, excluding mobile/mono,'
        f' special environments (iOS, Android, WASI, wasm),'
        f' and infrastructure/VM-internals/AOT/GC areas.'
        f' Sorted by staleness ascending (freshest first).">'
        f'<input type="checkbox" id="copilot-candidate-filter-checkbox">'
        f'<span class="toggle-label">Show only Copilot candidates</span>'
        f'</label>'
        f'<span class="active-label-filter" id="active-label-filter" style="display:none"></span>'
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
    cells.append(
        f'<td class="title-cell">{_esc(title)}</td>'
    )

    # --- Hit counts ---
    for hit_key in ("hits_24h", "hits_7d", "hits_30d"):
        val = issue.get(hit_key, 0) or 0
        bold_cls = "hits-active" if val > 0 and hit_key != "hits_30d" else ""
        cells.append(
            f'<td class="{bold_cls}" data-sort-value="{val}">{val}</td>'
        )

    # --- Assignee ---
    assignee = issue.get("assignee_display") or ", ".join(issue.get("assignees") or [])
    if assignee:
        cells.append(f"<td>{_esc(assignee)}</td>")
    else:
        cells.append('<td class="no-assignee">—</td>')

    # --- Last Activity ---
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
    cells.append(f'<td class="labels-cell">{labels_html}</td>')

    mobile_attr = ' data-mobile="true"' if _is_mobile_issue(issue) else ""
    no_hits = issue.get("hits_24h", 0) == 0 and issue.get("hits_7d", 0) == 0 and issue.get("hits_30d", 0) == 0
    no_hits_attr = ' data-no-hits="true"' if no_hits else ""
    copilot_attr = ' data-copilot-candidate="true"' if _is_copilot_candidate(issue) else ""
    return f"<tr{mobile_attr}{no_hits_attr}{copilot_attr}>" + "".join(cells) + "</tr>"


_MOBILE_LABELS_EXACT = frozenset([
    "area-infrastructure-mono",
    "os-android",
    "os-ios",
    "os-tvos",
    "os-maccatalyst",
])

_MOBILE_KEYWORDS = ("android", "ios", "mono", "maccatalyst", "tvos")

_WASM_EXCLUDE_KEYWORDS = ("wasm", "browser", "wasi")


def _is_mobile_issue(issue: dict) -> bool:
    """Return True if any label indicates a mobile/mono issue, excluding wasm/browser."""
    labels = issue.get("labels", [])
    if not isinstance(labels, list):
        return False
    lower_labels = []
    for lbl in labels:
        name = lbl if isinstance(lbl, str) else lbl.get("name", "")
        lower_labels.append(name.lower())
    # Exclude if any label contains wasm/browser/wasi
    for lower in lower_labels:
        if any(kw in lower for kw in _WASM_EXCLUDE_KEYWORDS):
            return False
    # Check for mobile/mono match
    for lower in lower_labels:
        if lower in _MOBILE_LABELS_EXACT:
            return True
        if any(kw in lower for kw in _MOBILE_KEYWORDS):
            return True
    return False


_COPILOT_EXCLUDE_AREA_PREFIXES = (
    "area-infrastructure",
    "area-vm-",
    "area-codegen-aot-mono",
    "area-crossgen2-",
    "area-build-mono",
    "area-gc-coreclr",
)

_COPILOT_EXCLUDE_LABELS = frozenset([
    "tracking-external-issue",
    "os-ios",
    "os-android",
    "os-tvos",
    "os-maccatalyst",
    "os-wasi",
    "arch-wasm",
])


def _is_copilot_candidate(issue: dict) -> bool:
    """Return True if the issue looks suitable for investigation by a Copilot agent.

    Good candidates have a known area label and are not mobile/mono, not tied to
    special environments (iOS, Android, WASI, wasm), and not in infrastructure,
    VM-internals, AOT, or GC areas.
    """
    labels = issue.get("labels", [])
    if not isinstance(labels, list):
        return False

    lower_labels = []
    for lbl in labels:
        name = lbl if isinstance(lbl, str) else lbl.get("name", "")
        lower_labels.append(name.lower())

    # Exclude issues with labels that indicate special environments
    for lower in lower_labels:
        if lower in _COPILOT_EXCLUDE_LABELS:
            return False

    # Exclude mobile/mono issues (already detected by _is_mobile_issue)
    if _is_mobile_issue(issue):
        return False

    # Exclude area labels for infrastructure, VM internals, AOT, GC
    area = (issue.get("area_label") or _extract_area(issue)).lower()
    if not area:
        return False
    for prefix in _COPILOT_EXCLUDE_AREA_PREFIXES:
        if area.startswith(prefix):
            return False

    # Remaining issues have a known area, are on standard platforms,
    # and are not infrastructure/VM/AOT/GC — good Copilot candidates.
    # Staleness is NOT a hard filter; the JS UI sorts candidates by
    # ascending staleness so the freshest issues appear first.
    return True


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
    """Render all labels as badge pills (skip 'Known Build Error' noise)."""
    labels = issue.get("labels", [])
    if not isinstance(labels, list):
        return ""

    badges = []
    for lbl in labels:
        name = lbl if isinstance(lbl, str) else lbl.get("name", "")
        if not name:
            continue
        lower = name.lower()
        if lower == "known build error":
            continue
        escaped = _esc(name)
        if lower == "blocking-clean-ci":
            badges.append(
                f'<span class="label-badge blocking clickable" data-label="{escaped}">{escaped}</span>'
            )
        elif lower == "untriaged":
            badges.append(
                f'<span class="label-badge untriaged clickable" data-label="{escaped}">{escaped}</span>'
            )
        else:
            badges.append(
                f'<span class="label-badge clickable" data-label="{escaped}">{escaped}</span>'
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

    {score_guide}

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
        print("Example: python html_template.py scan.json pages/runtime runtime")
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
