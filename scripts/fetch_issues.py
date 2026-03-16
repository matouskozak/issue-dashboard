#!/usr/bin/env python3
"""Fetch dotnet Known Build Error issues via GitHub GraphQL API and produce scan.json.

Usage:
    python scripts/fetch_issues.py runtime

Requires GITHUB_TOKEN environment variable.
Outputs to pages/<repo>/scan.json.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
ORG = "dotnet"
LABEL = "Known Build Error"

BOT_LOGINS = frozenset(
    [
        "dotnet-issue-labeler",
        "msftbot",
        "dotnet-policy-service",
        "github-actions",
        "fabricbot",
    ]
)

# GraphQL query — fetches open issues with the KBE label, paginated.
ISSUES_QUERY = """
query($owner: String!, $repo: String!, $label: String!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    issues(
      first: 50
      after: $cursor
      states: [OPEN]
      labels: [$label]
      orderBy: {field: UPDATED_AT, direction: DESC}
    ) {
      pageInfo {
        hasNextPage
        endCursor
      }
      nodes {
        number
        title
        state
        createdAt
        updatedAt
        body
        author { login }
        labels(first: 30) { nodes { name } }
        assignees(first: 20) { nodes { login } }
        comments(first: 50) {
          nodes {
            author { login }
            body
            createdAt
            authorAssociation
          }
        }
        reactions { totalCount }
      }
    }
  }
}
"""

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class SignalResult:
    """One scored signal inside a score breakdown."""

    value: float
    weight: float
    contribution: float


@dataclass
class HitCounts:
    hits_24h: int = 0
    hits_7d: int = 0
    hits_30d: int = 0


@dataclass
class ParsedIssue:
    """All data extracted from a single GitHub issue."""

    number: int = 0
    title: str = ""
    url: str = ""
    state: str = "OPEN"
    created_at: str = ""
    updated_at: str = ""
    author: str = ""
    assignees: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    area_label: Optional[str] = None
    comment_count: int = 0
    human_comment_count: int = 0
    last_human_comment_date: Optional[str] = None
    last_human_comment_author: Optional[str] = None
    reactions_count: int = 0
    hits_24h: int = 0
    hits_7d: int = 0
    hits_30d: int = 0
    error_pattern: Optional[str] = None
    build_link: Optional[str] = None
    has_blocking_label: bool = False
    has_untriaged_label: bool = False
    # Computed fields for display (added 2026-03-16)
    age_days: int = 0
    last_human_activity_days: Optional[int] = None
    assignee_display: str = ""
    urgency_score: float = 0.0
    urgency_breakdown: dict[str, dict[str, float]] = field(default_factory=dict)
    staleness_score: float = 0.0
    staleness_breakdown: dict[str, dict[str, float]] = field(default_factory=dict)
    neglect_score: float = 0.0
    neglect_breakdown: dict[str, dict[str, float]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------


def _get_token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        log.error("GITHUB_TOKEN environment variable is not set")
        sys.exit(1)
    return token


def _graphql_request(
    token: str, query: str, variables: dict[str, Any]
) -> dict[str, Any]:
    """Execute a single GraphQL request and return the JSON response."""
    headers = {
        "Authorization": f"bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {"query": query, "variables": variables}
    resp = requests.post(GITHUB_GRAPHQL_URL, json=payload, headers=headers, timeout=30)

    # Rate-limit awareness
    remaining = resp.headers.get("X-RateLimit-Remaining")
    if remaining is not None:
        remaining_int = int(remaining)
        if remaining_int < 100:
            log.warning("GitHub API rate limit remaining: %d", remaining_int)
        if remaining_int == 0:
            reset_ts = resp.headers.get("X-RateLimit-Reset", "unknown")
            log.error("Rate limit exhausted. Resets at %s", reset_ts)
            sys.exit(1)

    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        log.error("GraphQL errors: %s", json.dumps(data["errors"], indent=2))
        sys.exit(1)
    return data


def fetch_all_issues(token: str, repo: str) -> list[dict[str, Any]]:
    """Paginate through all open KBE issues and return raw GraphQL nodes."""
    all_nodes: list[dict[str, Any]] = []
    cursor: Optional[str] = None
    page = 0

    while True:
        page += 1
        log.info("Fetching page %d (cursor=%s)…", page, cursor or "START")
        variables: dict[str, Any] = {
            "owner": ORG,
            "repo": repo,
            "label": LABEL,
            "cursor": cursor,
        }
        data = _graphql_request(token, ISSUES_QUERY, variables)
        issues_data = data["data"]["repository"]["issues"]
        nodes = issues_data["nodes"]
        all_nodes.extend(nodes)
        log.info("  … got %d issues (total so far: %d)", len(nodes), len(all_nodes))

        page_info = issues_data["pageInfo"]
        if page_info["hasNextPage"]:
            cursor = page_info["endCursor"]
        else:
            break

    log.info("Fetched %d total issues", len(all_nodes))
    return all_nodes


# ---------------------------------------------------------------------------
# Issue body parsing
# ---------------------------------------------------------------------------

# Regex for the summary hit-count table.
# Matches markdown tables with 3 numeric columns, tolerating whitespace.
_HIT_TABLE_RE = re.compile(
    r"\|[^|]*Hit\s*Count[^|]*\|[^|]*Hit\s*Count[^|]*\|[^|]*Count[^|]*\|"
    r"\s*\n\s*\|[-\s:|]+\|[-\s:|]+\|[-\s:|]+\|\s*\n"
    r"\s*\|[^\S\n]*(\d[\d,]*)[^\S\n]*\|[^\S\n]*(\d[\d,]*)[^\S\n]*\|[^\S\n]*(\d[\d,]*)[^\S\n]*\|",
    re.IGNORECASE,
)

# Fallback: any 3-column numeric table right after a separator row
_HIT_TABLE_FALLBACK_RE = re.compile(
    r"\|[-\s:|]+\|[-\s:|]+\|[-\s:|]+\|\s*\n"
    r"\s*\|[^\S\n]*(\d[\d,]*)[^\S\n]*\|[^\S\n]*(\d[\d,]*)[^\S\n]*\|[^\S\n]*(\d[\d,]*)[^\S\n]*\|",
)

# JSON code block
_JSON_BLOCK_RE = re.compile(r"```json\s*\n(.*?)```", re.DOTALL)

# Build links
_BUILD_LINK_RE = re.compile(r"https?://dev\.azure\.com/[^\s\)>\]]+")


def parse_hit_counts(body: str) -> HitCounts:
    """Extract 24h, 7d, and 30d hit counts from the issue body.

    Uses the LAST match if multiple hit tables exist (the body may contain
    historical snapshots; the most recent table is at the bottom).
    """
    if not body:
        return HitCounts()

    matches = list(_HIT_TABLE_RE.finditer(body))
    if not matches:
        matches = list(_HIT_TABLE_FALLBACK_RE.finditer(body))
    if matches:
        m = matches[-1]  # last occurrence = most recent
        try:
            return HitCounts(
                hits_24h=int(m.group(1).replace(",", "")),
                hits_7d=int(m.group(2).replace(",", "")),
                hits_30d=int(m.group(3).replace(",", "")),
            )
        except (ValueError, IndexError):
            log.debug("Failed to parse hit counts from table match")
    return HitCounts()


def parse_error_pattern(body: str) -> Optional[str]:
    """Extract JSON error pattern block from the issue body."""
    if not body:
        return None
    m = _JSON_BLOCK_RE.search(body)
    if m:
        return m.group(1).strip()
    return None


def parse_build_link(body: str) -> Optional[str]:
    """Extract the first Azure DevOps build link from the issue body."""
    if not body:
        return None
    m = _BUILD_LINK_RE.search(body)
    return m.group(0) if m else None


# ---------------------------------------------------------------------------
# Comment analysis
# ---------------------------------------------------------------------------


def _is_human_comment(comment: dict[str, Any]) -> bool:
    """Return True if the comment is from a human (not a bot)."""
    assoc = (comment.get("authorAssociation") or "").upper()
    if assoc == "BOT":
        return False
    author = (comment.get("author") or {}).get("login", "")
    if author.lower() in {b.lower() for b in BOT_LOGINS}:
        return False
    return True


def analyse_comments(
    comments: list[dict[str, Any]],
) -> tuple[int, int, Optional[str], Optional[str]]:
    """Return (total_count, human_count, last_human_date, last_human_author)."""
    total = len(comments)
    human_count = 0
    last_human_date: Optional[str] = None
    last_human_author: Optional[str] = None

    for c in comments:
        if _is_human_comment(c):
            human_count += 1
            c_date = c.get("createdAt", "")
            if c_date and (last_human_date is None or c_date > last_human_date):
                last_human_date = c_date
                last_human_author = (c.get("author") or {}).get("login", "")

    return total, human_count, last_human_date, last_human_author


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _signal(name: str, value: float, weight: float) -> tuple[str, SignalResult]:
    return name, SignalResult(
        value=round(value, 4),
        weight=weight,
        contribution=round(value * weight, 4),
    )


def _days_between(iso_date: str, now: datetime) -> float:
    """Parse an ISO-8601 timestamp and return days elapsed until *now*."""
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return max((now - dt).total_seconds() / 86400, 0.0)
    except (ValueError, TypeError):
        return 0.0


def compute_urgency(issue: ParsedIssue, now: datetime) -> tuple[float, dict]:
    signals: list[tuple[str, SignalResult]] = []

    # 24h hit count
    if issue.hits_24h > 10:
        v = 1.0
    elif issue.hits_24h > 5:
        v = 0.75
    elif issue.hits_24h > 0:
        v = 0.5
    else:
        v = 0.0
    signals.append(_signal("hits_24h", v, 3.0))

    # 7d hit count
    if issue.hits_7d > 50:
        v = 1.0
    elif issue.hits_7d > 20:
        v = 0.75
    elif issue.hits_7d > 5:
        v = 0.5
    else:
        v = 0.0
    signals.append(_signal("hits_7d", v, 2.0))

    # Hit trend
    if issue.hits_7d > 0:
        ratio = (issue.hits_24h * 7) / issue.hits_7d
        if ratio > 1.5:
            v = 1.0
        elif ratio > 1.0:
            v = 0.75
        elif ratio > 0.5:
            v = 0.5
        else:
            v = 0.0
    else:
        # No 7-day baseline — if 24h hits appeared, that's maximum acceleration
        v = 1.0 if issue.hits_24h > 0 else 0.0
    signals.append(_signal("hit_trend", v, 1.5))

    # Blocking label
    v = 1.0 if issue.has_blocking_label else 0.0
    signals.append(_signal("blocking_label", v, 1.5))

    # Age vs hits
    age_days = _days_between(issue.created_at, now)
    if age_days < 3 and issue.hits_24h > 5:
        v = 1.0
    elif age_days < 7 and issue.hits_24h > 0:
        v = 0.5
    else:
        v = 0.0
    signals.append(_signal("age_vs_hits", v, 1.0))

    # No assignee
    v = 1.0 if not issue.assignees else 0.0
    signals.append(_signal("no_assignee", v, 1.0))

    breakdown = {name: asdict(sr) for name, sr in signals}
    total = min(sum(sr.contribution for _, sr in signals), 10.0)
    return round(total, 2), breakdown


def compute_staleness(issue: ParsedIssue, now: datetime) -> tuple[float, dict]:
    # Issues with disabled-test label have intentionally zero hits — not stale
    if "disabled-test" in issue.labels:
        return 0.0, {}

    signals: list[tuple[str, SignalResult]] = []

    # 24h hits = 0
    v = 1.0 if issue.hits_24h == 0 else 0.0
    signals.append(_signal("hits_24h_zero", v, 3.0))

    # 7d hits = 0
    v = 1.0 if issue.hits_7d == 0 else 0.0
    signals.append(_signal("hits_7d_zero", v, 2.5))

    # Days since update
    days_since_update = _days_between(issue.updated_at, now)
    if days_since_update > 30:
        v = 1.0
    elif days_since_update > 14:
        v = 0.75
    elif days_since_update > 7:
        v = 0.5
    else:
        v = 0.0
    signals.append(_signal("days_since_update", v, 2.0))

    # Issue age
    age_days = _days_between(issue.created_at, now)
    if age_days > 60:
        v = 1.0
    elif age_days > 30:
        v = 0.75
    elif age_days > 14:
        v = 0.5
    else:
        v = 0.0
    signals.append(_signal("issue_age", v, 1.5))

    # 1-month count low
    if issue.hits_30d < 5:
        v = 1.0
    elif issue.hits_30d < 20:
        v = 0.5
    else:
        v = 0.0
    signals.append(_signal("monthly_count_low", v, 1.0))

    breakdown = {name: asdict(sr) for name, sr in signals}
    total = min(sum(sr.contribution for _, sr in signals), 10.0)
    return round(total, 2), breakdown


def compute_neglect(issue: ParsedIssue, now: datetime) -> tuple[float, dict]:
    signals: list[tuple[str, SignalResult]] = []
    has_hits = issue.hits_24h > 0 or issue.hits_7d > 0

    # Hits > 0 + no assignee
    v = 1.0 if has_hits and not issue.assignees else 0.0
    signals.append(_signal("hits_no_assignee", v, 3.0))

    # Hits > 0 + no human comments
    v = 1.0 if has_hits and issue.human_comment_count == 0 else 0.0
    signals.append(_signal("hits_no_human_comments", v, 2.5))

    # High hit count + untriaged
    v = 1.0 if issue.hits_7d > 20 and issue.has_untriaged_label else 0.0
    signals.append(_signal("high_hits_untriaged", v, 2.0))

    # Days since last human comment
    if issue.last_human_comment_date is None:
        v = 1.0  # no human comments ever
    else:
        days = _days_between(issue.last_human_comment_date, now)
        if days > 14:
            v = 1.0
        elif days > 7:
            v = 0.75
        elif days > 3:
            v = 0.5
        else:
            v = 0.0
    signals.append(_signal("days_since_human_comment", v, 1.5))

    # No area label
    v = 1.0 if issue.area_label is None else 0.0
    signals.append(_signal("no_area_label", v, 1.0))

    breakdown = {name: asdict(sr) for name, sr in signals}
    total = min(sum(sr.contribution for _, sr in signals), 10.0)
    return round(total, 2), breakdown


# ---------------------------------------------------------------------------
# Node → ParsedIssue
# ---------------------------------------------------------------------------


def parse_issue_node(node: dict[str, Any], repo: str, now: datetime) -> ParsedIssue:
    """Transform a raw GraphQL issue node into a fully scored ParsedIssue."""
    body = node.get("body") or ""

    labels = [n["name"] for n in (node.get("labels") or {}).get("nodes", [])]
    assignees = [
        n["login"] for n in (node.get("assignees") or {}).get("nodes", [])
    ]
    comments_nodes = (node.get("comments") or {}).get("nodes", [])

    area_label = next((l for l in labels if l.lower().startswith("area-")), None)
    total_comments, human_comments, last_hc_date, last_hc_author = analyse_comments(
        comments_nodes
    )

    hits = parse_hit_counts(body)

    issue = ParsedIssue(
        number=node.get("number", 0),
        title=node.get("title", ""),
        url=f"https://github.com/{ORG}/{repo}/issues/{node.get('number', 0)}",
        state=node.get("state", "OPEN"),
        created_at=node.get("createdAt", ""),
        updated_at=node.get("updatedAt", ""),
        author=(node.get("author") or {}).get("login", ""),
        assignees=assignees,
        labels=labels,
        area_label=area_label,
        comment_count=total_comments,
        human_comment_count=human_comments,
        last_human_comment_date=last_hc_date,
        last_human_comment_author=last_hc_author,
        reactions_count=(node.get("reactions") or {}).get("totalCount", 0),
        hits_24h=hits.hits_24h,
        hits_7d=hits.hits_7d,
        hits_30d=hits.hits_30d,
        error_pattern=parse_error_pattern(body),
        build_link=parse_build_link(body),
        has_blocking_label="blocking-clean-ci" in labels,
        has_untriaged_label="untriaged" in labels,
    )

    # Compute display fields from raw data
    issue.age_days = int(_days_between(issue.created_at, now))
    if issue.last_human_comment_date:
        issue.last_human_activity_days = int(_days_between(issue.last_human_comment_date, now))
    issue.assignee_display = ", ".join(issue.assignees) if issue.assignees else ""

    issue.urgency_score, issue.urgency_breakdown = compute_urgency(issue, now)
    issue.staleness_score, issue.staleness_breakdown = compute_staleness(issue, now)
    issue.neglect_score, issue.neglect_breakdown = compute_neglect(issue, now)

    return issue


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <repo>", file=sys.stderr)
        sys.exit(1)

    repo = sys.argv[1]
    token = _get_token()
    now = datetime.now(timezone.utc)

    log.info("Fetching KBE issues for %s/%s …", ORG, repo)
    raw_nodes = fetch_all_issues(token, repo)

    parsed: list[dict[str, Any]] = []
    for node in raw_nodes:
        issue = parse_issue_node(node, repo, now)
        parsed.append(asdict(issue))

    scan = {
        "repo": repo,
        "org": ORG,
        "generated_at": now.isoformat(timespec="seconds"),
        "issue_count": len(parsed),
        "issues": parsed,
    }

    # Ensure output directory exists
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    out_dir = repo_root / "pages" / repo
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "scan.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(scan, f, indent=2, ensure_ascii=False)

    log.info("Wrote %d issues to %s", len(parsed), out_path)


if __name__ == "__main__":
    main()
