"""Tests for high impact alerts. All HTTP requests are mocked."""

import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

from scripts.notify_high_impact import PAUSE, load_scan, main, notify

NOW = datetime(2026, 9, 23, 10, tzinfo=timezone.utc)
TARGET = "matouskozak/issue-dashboard"
ASSIGNEE = "matouskozak"
MARKER = "<!-- high-impact-alert:dotnet/runtime:123 -->"


@pytest.fixture
def scan():
    return {
        "org": "dotnet",
        "repo": "runtime",
        "generated_at": NOW.isoformat(),
        "issues": [{
            "number": 123,
            "title": "Mobile test failure",
            "state": "OPEN",
            "labels": ["Known Build Error", "os-ios"],
            "hits_24h": 7,
            "hits_7d": 23,
        }],
    }


def response(data=None, status=200):
    result = requests.Response()
    result.status_code = status
    result.url = f"https://api.github.com/repos/{TARGET}/issues"
    result._content = json.dumps(data).encode()
    return result


@pytest.fixture
def api(monkeypatch):
    state = SimpleNamespace(issues=[], assignees=[{"login": ASSIGNEE}])

    def request(method, url, **kwargs):
        assert kwargs["timeout"] == 30
        assert kwargs["headers"]["Authorization"] == "Bearer test-token"
        if method == "GET" and url.endswith(f"/assignees/{ASSIGNEE}"):
            return response(status=204)
        if method == "POST" and url.endswith("/assignees"):
            assert kwargs["json"] == {"assignees": [ASSIGNEE]}
            existing = next(
                issue for issue in state.issues
                if url == f"https://api.github.com/repos/{TARGET}/issues/{issue['number']}/assignees"
            )
            existing["assignees"].extend(
                user for user in state.assignees if user not in existing["assignees"]
            )
            return response(existing)
        assert url == f"https://api.github.com/repos/{TARGET}/issues"
        if method == "GET":
            params = kwargs["params"]
            assert params["state"] == "all"
            assert params["per_page"] == 100
            start = (params["page"] - 1) * 100
            return response(state.issues[start:start + 100])
        assert method == "POST"
        created = {
            **kwargs["json"],
            "number": max((issue["number"] for issue in state.issues), default=0) + 1,
            "state": "open",
            "closed_at": None,
            "assignees": list(state.assignees),
            "user": {"login": "github-actions[bot]", "type": "Bot"},
        }
        state.issues.append(created)
        return response(created, status=201)

    state.request = Mock(side_effect=request)
    monkeypatch.setattr("scripts.notify_high_impact.requests.request", state.request)
    return state


def run(scan, **kwargs):
    return notify(scan, TARGET, ASSIGNEE, "test-token", now=NOW, **kwargs)


def alert(number=1, *, closed_at=None, marker=MARKER):
    return {
        "number": number,
        "body": marker,
        "state": "closed" if closed_at else "open",
        "closed_at": closed_at.isoformat() if closed_at else None,
        "assignees": [{"login": ASSIGNEE}],
        "user": {"login": "github-actions[bot]", "type": "Bot"},
    }


@pytest.mark.parametrize("hits, expected", [(0, 0), (6, 0), (7, 1), (8, 1)])
def test_threshold(scan, api, hits, expected):
    scan["issues"][0]["hits_24h"] = hits
    assert run(scan) == expected
    if not expected:
        api.request.assert_not_called()


@pytest.mark.parametrize("labels, expected", [
    (["runtime-mono"], 1),
    (["area-Infrastructure-mono"], 1),
    (["area-Codegen-JIT-mono"], 1),
    (["os-android"], 1),
    (["OS-IOS"], 1),
    (["os-tvos"], 1),
    (["os-maccatalyst"], 1),
    (["area-System.Net"], 0),
    ([], 0),
    (["runtime-mono", "arch-wasm"], 0),
    (["os-ios", "os-browser"], 0),
    (["os-android", "OS-WASI"], 0),
])
def test_existing_mobile_filter(scan, api, labels, expected):
    scan["issues"][0]["labels"] = ["Known Build Error", *labels]
    assert run(scan) == expected


@pytest.mark.parametrize("change", [{"state": "CLOSED"}, {"labels": ["os-ios"]}])
def test_only_open_kbe_issues(scan, api, change):
    scan["issues"][0].update(change)
    assert run(scan) == 0
    api.request.assert_not_called()


def test_created_alert_content_and_assignment(scan, api):
    assert run(scan) == 1
    created = api.issues[0]
    assert created["title"] == "[High impact] dotnet/runtime issue 123: Mobile test failure"
    assert created["assignees"] == [{"login": ASSIGNEE}]
    for text in (
        MARKER, "https://redirect.github.com/dotnet/runtime/issues/123",
        "**7 failures in 24 hours**", "7-day failure count: **23**",
        "`os-ios`", NOW.isoformat(), "https://matouskozak.github.io/issue-dashboard/",
        "7 days", "new alert", "hidden source marker",
    ):
        assert text in created["body"]
    assert "[dotnet/runtime issue 123]" in created["body"]
    for field in ("body", "title"):
        assert "https://github.com/dotnet/runtime" not in created[field]
        assert "dotnet/runtime#123" not in created[field]
    assert [call.args[0] for call in api.request.call_args_list] == ["GET", "GET", "POST"]


def test_open_alert_stops_all_repeat_writes(scan, api):
    assert run(scan) == 1
    first = dict(api.issues[0])
    api.request.reset_mock()
    assert run(scan) == 0
    assert run(scan) == 0
    assert api.issues == [first]
    assert all(call.args[0] == "GET" for call in api.request.call_args_list)


@pytest.mark.parametrize("closed_at", [None, NOW - timedelta(days=1)])
def test_older_bot_markers_still_prevent_duplicates(scan, api, closed_at):
    api.issues = [alert(
        closed_at=closed_at, marker="<!-- high-impact-alert:dotnet/runtime#123 -->",
    )]
    assert run(scan) == 0
    api.request.assert_called_once()
    assert api.request.call_args.args[0] == "GET"


@pytest.mark.parametrize("age, expected", [
    (PAUSE - timedelta(seconds=1), 0),
    (PAUSE, 1),
    (PAUSE + timedelta(seconds=1), 1),
])
def test_pause_boundary_creates_new_issue(scan, api, age, expected):
    previous = alert(closed_at=NOW - age)
    api.issues = [previous]
    assert run(scan) == expected
    assert api.issues[0] == previous
    assert api.issues[0]["state"] == "closed"
    if expected:
        assert api.issues[1]["number"] != previous["number"]
        assert f"https://github.com/{TARGET}/issues/1" in api.issues[1]["body"]


def test_most_recent_closure_controls_pause(scan, api):
    api.issues = [
        alert(20, closed_at=NOW - timedelta(days=20)),
        alert(2, closed_at=NOW - timedelta(days=1)),
    ]
    assert run(scan) == 0
    assert len(api.issues) == 2


def test_any_open_alert_wins_over_expired_pause(scan, api):
    api.issues = [alert(1, closed_at=NOW - PAUSE), alert(2)]
    assert run(scan) == 0


def test_low_count_waits_after_pause(scan, api):
    api.issues = [alert(closed_at=NOW - timedelta(days=8))]
    scan["issues"][0]["hits_24h"] = 6
    assert run(scan) == 0
    scan["issues"][0]["hits_24h"] = 7
    assert run(scan) == 1


def test_new_alert_closure_starts_another_pause(scan, api):
    api.issues = [alert(closed_at=NOW - timedelta(days=8))]
    assert run(scan) == 1
    api.issues[-1].update(state="closed", closed_at=NOW.isoformat())
    assert run(scan) == 0
    assert notify(scan, TARGET, ASSIGNEE, "test-token", now=NOW + PAUSE) == 1
    assert len(api.issues) == 3
    assert all(issue["state"] == "closed" for issue in api.issues[:2])


def test_timezone_offsets_use_elapsed_time(scan, api):
    closed_at = (NOW - PAUSE).astimezone(timezone(timedelta(hours=2)))
    api.issues = [alert(closed_at=closed_at)]
    assert run(scan) == 1


def test_history_pagination_and_unrelated_issues(scan, api):
    api.issues = [
        alert(number, marker="<!-- high-impact-alert:dotnet/runtime:1234 -->")
        for number in range(1, 101)
    ] + [alert(101)]
    assert run(scan) == 0
    assert [call.kwargs["params"]["page"] for call in api.request.call_args_list] == [1, 2]


def test_pull_requests_other_sources_and_titles_do_not_suppress_alert(scan, api):
    api.issues = [
        {**alert(1), "pull_request": {}},
        alert(2, marker="<!-- high-impact-alert:dotnet/maui:123 -->"),
        {**alert(3, marker=None), "title": "[High impact] dotnet/runtime#123"},
    ]
    assert run(scan) == 1
    assert len(api.issues) == 4


def test_multiple_sources_check_assignment_once(scan, api):
    scan["issues"].append({**scan["issues"][0], "number": 456, "hits_24h": 8})
    assert run(scan) == 2
    assert "issue 456" in api.issues[0]["title"]
    assert sum("/assignees/" in call.args[1] for call in api.request.call_args_list) == 1


def test_dry_run_reads_history_without_writes(scan, api, capsys):
    api.issues = [alert(closed_at=NOW - PAUSE)]
    assert run(scan, dry_run=True) == 0
    assert len(api.issues) == 1
    api.request.assert_called_once()
    assert api.request.call_args.args[0] == "GET"
    payload = json.loads(capsys.readouterr().out)
    assert payload["assignees"] == [ASSIGNEE]
    assert MARKER in payload["body"]


@pytest.mark.parametrize("status", [403, 404, 429, 500])
def test_failed_history_lookup_never_creates(scan, api, status):
    api.request.side_effect = [response(status=status)]
    with pytest.raises(requests.HTTPError):
        run(scan)
    api.request.assert_called_once()


def test_assignment_permission_checked_before_create(scan, api):
    api.request.side_effect = [response([]), response(status=404)]
    with pytest.raises(requests.HTTPError):
        run(scan)
    assert all(call.args[0] == "GET" for call in api.request.call_args_list)


def test_failed_creation_is_not_retried(scan, api):
    api.request.side_effect = [response([]), response(status=204), requests.Timeout("timeout")]
    with pytest.raises(requests.Timeout):
        run(scan)
    assert api.request.call_count == 3


def test_missing_assignment_is_an_error(scan, api):
    api.assignees = []
    with pytest.raises(ValueError, match="was not assigned"):
        run(scan)
    assert len(api.issues) == 1
    assert api.request.call_count == 3


def test_next_run_repairs_missing_assignment_without_duplicate(scan, api):
    api.assignees = []
    with pytest.raises(ValueError, match="was not assigned"):
        run(scan)
    api.assignees = [{"login": ASSIGNEE}]
    api.request.reset_mock()

    assert run(scan) == 0
    assert len(api.issues) == 1
    assert api.issues[0]["assignees"] == [{"login": ASSIGNEE}]
    assert api.request.call_args.args == (
        "POST", f"https://api.github.com/repos/{TARGET}/issues/1/assignees",
    )
    api.request.reset_mock()
    assert run(scan) == 0
    api.request.assert_called_once()
    assert api.request.call_args.args[0] == "GET"


def test_repair_preserves_other_assignees_and_notes(scan, api):
    existing = alert()
    existing["assignees"] = [{"login": "another-maintainer"}]
    existing["body"] += "\n\nA note from a maintainer."
    api.issues = [existing]
    body = existing["body"]
    assert run(scan) == 0
    assert existing["assignees"] == [
        {"login": "another-maintainer"}, {"login": ASSIGNEE},
    ]
    assert existing["body"] == body
    assert existing["state"] == "open"


def test_failed_repair_remains_an_error_without_duplicate(scan, api):
    api.issues = [{**alert(), "assignees": []}]
    api.assignees = []
    for _ in range(2):
        with pytest.raises(ValueError, match="was not assigned"):
            run(scan)
    assert len(api.issues) == 1
    assert all(
        call.args[0] == "GET" or call.args[1].endswith("/issues/1/assignees")
        for call in api.request.call_args_list
    )


def test_repair_checks_permission_before_write(scan, api):
    api.request.side_effect = [
        response([{**alert(), "assignees": []}]), response(status=403),
    ]
    with pytest.raises(requests.HTTPError):
        run(scan)
    assert api.request.call_count == 2
    assert all(call.args[0] == "GET" for call in api.request.call_args_list)


def test_repair_dry_run_never_writes(scan, api, caplog):
    api.issues = [{**alert(), "assignees": []}]
    with caplog.at_level(logging.INFO):
        assert run(scan, dry_run=True) == 0
    assert "would assign matouskozak" in caplog.text
    assert api.issues[0]["assignees"] == []
    api.request.assert_called_once()
    assert api.request.call_args.args[0] == "GET"


@pytest.mark.parametrize("user", [
    None, {}, {"login": "unrelated-author"}, {"login": "another-app[bot]"},
])
@pytest.mark.parametrize("closed_at", [None, NOW - timedelta(days=1)])
@pytest.mark.parametrize("marker", [MARKER, "<!-- high-impact-alert:dotnet/runtime#123 -->"])
def test_untrusted_markers_do_not_suppress_alerts(scan, api, user, closed_at, marker):
    untrusted = {
        **alert(closed_at=closed_at, marker=marker), "user": user, "assignees": [],
    }
    api.issues = [untrusted]
    assert run(scan) == 1
    assert len(api.issues) == 2
    assert untrusted["assignees"] == []
    assert "Previous alert" not in api.issues[-1]["body"]


def test_untrusted_closure_does_not_extend_pause(scan, api):
    api.issues = [
        alert(1, closed_at=NOW - PAUSE),
        {**alert(2, closed_at=NOW), "user": {"login": "unrelated-author"}},
    ]
    assert run(scan) == 1
    assert f"Previous alert: https://github.com/{TARGET}/issues/1" in api.issues[-1]["body"]


def test_repair_and_creation_share_assignment_check(scan, api):
    api.issues = [{**alert(), "assignees": []}]
    scan["issues"].append({**scan["issues"][0], "number": 456, "hits_24h": 8})
    assert run(scan) == 1
    assert api.issues[0]["assignees"] == [{"login": ASSIGNEE}]
    assert len(api.issues) == 2
    assert sum(
        call.args[0] == "GET" and "/assignees/" in call.args[1]
        for call in api.request.call_args_list
    ) == 1


@pytest.mark.parametrize("data", [None, {}, [None]])
def test_invalid_history_response_is_an_error(scan, api, data):
    api.request.side_effect = [response(data)]
    with pytest.raises(ValueError, match="invalid issue list"):
        run(scan)
    api.request.assert_called_once()


@pytest.mark.parametrize("changes", [
    {"state": "unknown"},
    {"state": "closed", "closed_at": None},
    {"state": "closed", "closed_at": "2026-09-01T00:00:00"},
])
def test_invalid_managed_history_never_creates(scan, api, changes):
    api.issues = [{**alert(), **changes}]
    with pytest.raises(ValueError):
        run(scan)
    api.request.assert_called_once()


def test_missing_token_is_an_error(scan, api):
    with pytest.raises(ValueError, match="GITHUB_TOKEN"):
        notify(scan, TARGET, ASSIGNEE, "")
    api.request.assert_not_called()


@pytest.mark.parametrize("target, assignee, threshold", [
    ("invalid", ASSIGNEE, 7),
    ("../issues", ASSIGNEE, 7),
    (TARGET, "@matouskozak", 7),
    (TARGET, ASSIGNEE, 0),
    (TARGET, ASSIGNEE, -1),
    (TARGET, ASSIGNEE, True),
])
def test_invalid_settings_fail_before_api(scan, api, target, assignee, threshold):
    with pytest.raises(ValueError):
        notify(scan, target, assignee, "test-token", threshold=threshold)
    api.request.assert_not_called()


@pytest.mark.parametrize("field, value", [
    ("number", 0), ("number", True), ("title", ""), ("state", "unknown"),
    ("labels", None), ("labels", [None]),
    ("hits_24h", None), ("hits_24h", -1), ("hits_24h", "7"), ("hits_24h", True),
    ("hits_7d", -1),
])
def test_invalid_scan_issue(tmp_path, scan, field, value):
    scan["issues"][0][field] = value
    path = tmp_path / "scan.json"
    path.write_text(json.dumps(scan))
    with pytest.raises(ValueError):
        load_scan(path)


@pytest.mark.parametrize("field, value", [
    ("org", None), ("repo", "../runtime"), ("issues", None),
    ("generated_at", None), ("generated_at", "invalid"),
    ("generated_at", "2026-09-23T10:00:00"),
])
def test_invalid_scan_metadata(tmp_path, scan, field, value):
    scan[field] = value
    path = tmp_path / "scan.json"
    path.write_text(json.dumps(scan))
    with pytest.raises(ValueError):
        load_scan(path)


def test_duplicate_source_records_are_rejected(tmp_path, scan):
    scan["issues"].append(dict(scan["issues"][0]))
    path = tmp_path / "scan.json"
    path.write_text(json.dumps(scan))
    with pytest.raises(ValueError, match="duplicate"):
        load_scan(path)


def test_command_reads_scan_and_dry_runs(tmp_path, scan, api, monkeypatch, capsys):
    path = tmp_path / "scan.json"
    path.write_text(json.dumps(scan))
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(sys, "argv", [
        "notify_high_impact", str(path), "--target-repo", TARGET,
        "--assignee", ASSIGNEE, "--threshold", "7", "--dry-run",
    ])
    assert main() == 0
    assert json.loads(capsys.readouterr().out)["assignees"] == [ASSIGNEE]
    assert api.issues == []


def test_command_reports_failures(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(sys, "argv", [
        "notify_high_impact", str(tmp_path / "missing.json"),
        "--target-repo", TARGET, "--assignee", ASSIGNEE,
    ])
    with caplog.at_level(logging.ERROR):
        assert main() == 1
    assert "High impact notification failed" in caplog.text
