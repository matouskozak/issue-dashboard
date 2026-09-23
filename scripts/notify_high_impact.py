"""Create GitHub alerts for high impact mono/mobile KBE issues.

Run with: python -m scripts.notify_high_impact --help
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from .html_template import _is_mobile_issue

log = logging.getLogger(__name__)
PAUSE = timedelta(days=7)
REPOSITORY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*")
DASHBOARD_URL = "https://matouskozak.github.io/issue-dashboard/"
ALERT_AUTHOR = "github-actions[bot]"


def _parse_time(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Expected an ISO timestamp with a timezone")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp has no timezone: {value}")
    return parsed.astimezone(timezone.utc)


def load_scan(path: Path) -> dict:
    scan = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(scan, dict):
        raise ValueError("Scan must be an object")
    source = f"{scan.get('org', '')}/{scan.get('repo', '')}"
    if (
        not isinstance(scan.get("org"), str)
        or not isinstance(scan.get("repo"), str)
        or not REPOSITORY_RE.fullmatch(source)
    ):
        raise ValueError("Scan must name its source organization and repository")
    _parse_time(scan.get("generated_at"))
    if not isinstance(scan.get("issues"), list):
        raise ValueError("Scan must contain an issues list")

    seen = set()
    for issue in scan["issues"]:
        if not isinstance(issue, dict):
            raise ValueError("Each scan issue must be an object")
        number = issue.get("number")
        if type(number) is not int or number <= 0 or number in seen:
            raise ValueError(f"Invalid or duplicate source issue number: {number}")
        seen.add(number)
        if not isinstance(issue.get("title"), str) or not issue["title"].strip():
            raise ValueError(f"Missing title for source issue {number}")
        if issue.get("state") not in ("OPEN", "CLOSED"):
            raise ValueError(f"Invalid state for source issue {number}")
        labels = issue.get("labels")
        if not isinstance(labels, list) or any(not isinstance(label, str) for label in labels):
            raise ValueError(f"Invalid labels for source issue {number}")
        for field in ("hits_24h", "hits_7d"):
            if type(issue.get(field)) is not int or issue[field] < 0:
                raise ValueError(f"Invalid {field} for source issue {number}")
    return scan


def _request(token: str, method: str, path: str, **kwargs) -> requests.Response:
    response = requests.request(
        method,
        f"https://api.github.com/repos/{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30,
        **kwargs,
    )
    response.raise_for_status()
    return response


def _list_issues(token: str, target: str) -> list[dict]:
    issues = []
    page = 1
    while True:
        batch = _request(
            token, "GET", f"{target}/issues",
            params={"state": "all", "per_page": 100, "page": page},
        ).json()
        if not isinstance(batch, list) or any(not isinstance(issue, dict) for issue in batch):
            raise ValueError("GitHub returned an invalid issue list")
        issues.extend(issue for issue in batch if "pull_request" not in issue)
        if len(batch) < 100:
            return issues
        page += 1


def _alert_body(scan: dict, issue: dict, marker: str, threshold: int, previous_url: str) -> str:
    source = f"{scan['org']}/{scan['repo']} issue {issue['number']}"
    source_url = f"https://redirect.github.com/{scan['org']}/{scan['repo']}/issues/{issue['number']}"
    lines = [
        marker,
        f"Source: [{source}]({source_url})",
        f"This mono/mobile issue has **{issue['hits_24h']} failures in 24 hours** "
        f"(alert threshold: {threshold}).",
        f"7-day failure count: **{issue['hits_7d']}**.",
        f"Labels: {', '.join('`' + label + '`' for label in issue['labels'])}",
        f"Scan time: {scan['generated_at']}",
        f"[Issue dashboard]({DASHBOARD_URL})",
        "Counts come from the source issue's KBE summary.",
        "No repeat notification is sent while this alert is open.",
        "**Close this alert to pause notifications for this source issue for 7 days.**",
        "After the pause, the next hourly check creates a new alert if the source "
        f"still has at least {threshold} failures in 24 hours.",
        "Keep the hidden source marker in this body so the pause can be tracked.",
    ]
    if previous_url:
        lines.append(f"Previous alert: {previous_url}")
    return "\n\n".join(lines)


def _has_assignee(issue: dict, assignee: str) -> bool:
    return any(
        user["login"].lower() == assignee.lower()
        for user in issue.get("assignees", [])
    )


def notify(
    scan: dict,
    target: str,
    assignee: str,
    token: str,
    *,
    threshold: int = 7,
    dry_run: bool = False,
    now: datetime | None = None,
) -> int:
    if not REPOSITORY_RE.fullmatch(target):
        raise ValueError("Target repository must use owner/repo format")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*", assignee):
        raise ValueError("Assignee must be a GitHub login without @")
    if type(threshold) is not int or threshold <= 0:
        raise ValueError("Threshold must be a positive integer")
    now = now or datetime.now(timezone.utc)
    candidates = [
        issue for issue in scan["issues"]
        if issue["state"] == "OPEN"
        and "known build error" in {label.lower() for label in issue["labels"]}
        and _is_mobile_issue(issue)
        and issue["hits_24h"] >= threshold
    ]
    log.info("%d qualifying issues; %d nonqualifying issues",
             len(candidates), len(scan["issues"]) - len(candidates))
    if not candidates:
        return 0
    if not token:
        raise ValueError("GITHUB_TOKEN is required to read alert history")

    alerts = _list_issues(token, target)
    source_repo = f"{scan['org']}/{scan['repo']}"
    assignment_checked = False
    created_count = 0
    for issue in sorted(candidates, key=lambda item: (-item["hits_24h"], item["number"])):
        source = f"{source_repo}#{issue['number']}"
        marker = f"<!-- high-impact-alert:{source_repo}:{issue['number']} -->"
        # Read older markers without publishing reference syntax in new alerts.
        markers = (marker, f"<!-- high-impact-alert:{source} -->")
        history = [
            alert for alert in alerts
            if (alert.get("user") or {}).get("login") == ALERT_AUTHOR
            and any(value in (alert.get("body") or "") for value in markers)
        ]
        if any(alert.get("state") not in ("open", "closed") for alert in history):
            raise ValueError(f"Invalid alert state for {source}")
        open_alerts = [alert for alert in history if alert["state"] == "open"]
        if open_alerts:
            for alert in open_alerts:
                if _has_assignee(alert, assignee):
                    continue
                alert_path = f"{target}/issues/{alert['number']}"
                alert_url = f"https://github.com/{alert_path}"
                if dry_run:
                    log.info("%s: would assign %s to existing alert %s", source, assignee, alert_url)
                    continue
                if not assignment_checked:
                    _request(token, "GET", f"{target}/assignees/{assignee}")
                    assignment_checked = True
                updated = _request(
                    token, "POST", f"{alert_path}/assignees",
                    json={"assignees": [assignee]},
                ).json()
                if not isinstance(updated, dict) or not _has_assignee(updated, assignee):
                    raise ValueError(f"Alert {alert_url}: {assignee} was not assigned")
                log.info("%s: restored assignment to %s on %s", source, assignee, alert_url)
            log.info("%s: alert already open", source)
            continue
        previous = max(history, key=lambda alert: _parse_time(alert.get("closed_at")), default=None)
        if previous:
            pause_end = _parse_time(previous["closed_at"]) + PAUSE
            if now < pause_end:
                log.info("%s: paused until %s", source, pause_end.isoformat())
                continue

        previous_url = f"https://github.com/{target}/issues/{previous['number']}" if previous else ""
        payload = {
            "title": f"[High impact] {source_repo} issue {issue['number']}: {issue['title']}"[:256],
            "body": _alert_body(scan, issue, marker, threshold, previous_url),
            "assignees": [assignee],
        }
        if dry_run:
            log.info("%s: would create an alert in %s assigned to %s", source, target, assignee)
            print(json.dumps(payload, indent=2))
            continue
        if not assignment_checked:
            _request(token, "GET", f"{target}/assignees/{assignee}")
            assignment_checked = True
        created = _request(token, "POST", f"{target}/issues", json=payload).json()
        if not isinstance(created, dict) or not isinstance(created.get("number"), int):
            raise ValueError(f"GitHub returned an invalid creation response for {source}; check the target repository")
        created_url = f"https://github.com/{target}/issues/{created['number']}"
        if not _has_assignee(created, assignee):
            raise ValueError(f"Created {created_url}, but {assignee} was not assigned")
        created_count += 1
        log.info("%s: created %s", source, created_url)
    return created_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scan", type=Path, help="Path to the current scan.json")
    parser.add_argument("--target-repo", required=True)
    parser.add_argument("--assignee", required=True)
    parser.add_argument("--threshold", type=int, default=7)
    parser.add_argument("--dry-run", action="store_true", help="Read history and print actions; never write")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        notify(
            load_scan(args.scan), args.target_repo, args.assignee,
            os.environ.get("GITHUB_TOKEN", ""),
            threshold=args.threshold, dry_run=args.dry_run,
        )
    except (OSError, ValueError, requests.RequestException) as exc:
        log.error("High impact notification failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
