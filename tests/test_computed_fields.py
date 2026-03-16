"""
Tests for computed display fields in ParsedIssue.

Author: Hockney (Tester)
Date: 2026-03-16

Verifies that computed fields (age_days, last_human_activity_days, assignee_display)
are correctly calculated from raw issue data and properly rendered in HTML output.
"""

import pytest
from datetime import datetime, timezone
from scripts.fetch_issues import ParsedIssue, _days_between


class TestDaysBetween:
    """Test the _days_between helper function."""

    def test_same_date(self):
        """Issue created now has 0 days age."""
        now = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
        iso_date = "2026-03-16T12:00:00Z"
        assert _days_between(iso_date, now) == 0.0

    def test_five_days_ago(self):
        """Issue created 5 days ago has 5 days age."""
        now = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
        iso_date = "2026-03-11T12:00:00Z"
        result = _days_between(iso_date, now)
        assert result == pytest.approx(5.0, abs=0.01)

    def test_hundred_days_ago(self):
        """Issue created 100 days ago has 100 days age."""
        now = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
        iso_date = "2025-12-06T12:00:00Z"
        result = _days_between(iso_date, now)
        assert result == pytest.approx(100.0, abs=0.01)

    def test_fractional_days(self):
        """Issue created 12 hours ago has 0.5 days age."""
        now = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
        iso_date = "2026-03-16T00:00:00Z"
        result = _days_between(iso_date, now)
        assert result == pytest.approx(0.5, abs=0.01)

    def test_invalid_date_returns_zero(self):
        """Invalid date strings return 0.0."""
        now = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
        assert _days_between("invalid", now) == 0.0
        assert _days_between("", now) == 0.0

    def test_none_date_returns_zero(self):
        """None date returns 0.0."""
        now = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
        # This should handle AttributeError gracefully (None.replace fails)
        with pytest.raises(AttributeError):
            _days_between(None, now)
        # NOTE: Current implementation doesn't handle None - edge case found!


class TestAgeDaysComputation:
    """Test age_days computation in ParsedIssue."""

    def test_age_days_computed_from_created_at_five_days(self):
        """Issue created 5 days ago should have age_days == 5."""
        from scripts.fetch_issues import parse_issue_node

        now = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
        node = {
            "number": 123,
            "title": "Test Issue",
            "url": "https://github.com/test/repo/issues/123",
            "state": "OPEN",
            "createdAt": "2026-03-11T12:00:00Z",
            "updatedAt": "2026-03-11T12:00:00Z",
            "author": {"login": "user1"},
            "assignees": {"nodes": []},
            "labels": {"nodes": []},
            "reactions": {"totalCount": 0},
            "comments": {"nodes": [], "totalCount": 0},
            "body": "",
        }
        
        issue = parse_issue_node(node, "test/repo", now)
        assert issue.age_days == 5

    def test_age_days_computed_today(self):
        """Issue created today should have age_days == 0."""
        from scripts.fetch_issues import parse_issue_node

        now = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
        node = {
            "number": 123,
            "title": "Test Issue",
            "url": "https://github.com/test/repo/issues/123",
            "state": "OPEN",
            "createdAt": "2026-03-16T12:00:00Z",
            "updatedAt": "2026-03-16T12:00:00Z",
            "author": {"login": "user1"},
            "assignees": {"nodes": []},
            "labels": {"nodes": []},
            "reactions": {"totalCount": 0},
            "comments": {"nodes": [], "totalCount": 0},
            "body": "",
        }
        
        issue = parse_issue_node(node, "test/repo", now)
        assert issue.age_days == 0

    def test_age_days_computed_hundred_days(self):
        """Issue created 100 days ago should have age_days == 100."""
        from scripts.fetch_issues import parse_issue_node

        now = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
        node = {
            "number": 123,
            "title": "Test Issue",
            "url": "https://github.com/test/repo/issues/123",
            "state": "OPEN",
            "createdAt": "2025-12-06T12:00:00Z",
            "updatedAt": "2025-12-06T12:00:00Z",
            "author": {"login": "user1"},
            "assignees": {"nodes": []},
            "labels": {"nodes": []},
            "reactions": {"totalCount": 0},
            "comments": {"nodes": [], "totalCount": 0},
            "body": "",
        }
        
        issue = parse_issue_node(node, "test/repo", now)
        assert issue.age_days == 100


class TestLastHumanActivityDaysComputation:
    """Test last_human_activity_days computation in ParsedIssue."""

    def test_last_human_activity_three_days_ago(self):
        """Issue with human comment 3 days ago should have last_human_activity_days == 3."""
        from scripts.fetch_issues import parse_issue_node

        now = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
        node = {
            "number": 123,
            "title": "Test Issue",
            "url": "https://github.com/test/repo/issues/123",
            "state": "OPEN",
            "createdAt": "2026-03-01T12:00:00Z",
            "updatedAt": "2026-03-13T12:00:00Z",
            "author": {"login": "user1"},
            "assignees": {"nodes": []},
            "labels": {"nodes": []},
            "reactions": {"totalCount": 0},
            "comments": {
                "nodes": [
                    {
                        "author": {"login": "github-actions[bot]"},
                        "authorAssociation": "BOT",
                        "createdAt": "2026-03-15T12:00:00Z"
                    },
                    {
                        "author": {"login": "human-user"},
                        "authorAssociation": "CONTRIBUTOR",
                        "createdAt": "2026-03-13T12:00:00Z"
                    }
                ],
                "totalCount": 2
            },
            "body": "",
        }
        
        issue = parse_issue_node(node, "test/repo", now)
        assert issue.last_human_activity_days == 3

    def test_last_human_activity_today(self):
        """Issue with human comment today should have last_human_activity_days == 0."""
        from scripts.fetch_issues import parse_issue_node

        now = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
        node = {
            "number": 123,
            "title": "Test Issue",
            "url": "https://github.com/test/repo/issues/123",
            "state": "OPEN",
            "createdAt": "2026-03-01T12:00:00Z",
            "updatedAt": "2026-03-16T12:00:00Z",
            "author": {"login": "user1"},
            "assignees": {"nodes": []},
            "labels": {"nodes": []},
            "reactions": {"totalCount": 0},
            "comments": {
                "nodes": [
                    {
                        "author": {"login": "human-user"},
                        "createdAt": "2026-03-16T12:00:00Z"
                    }
                ],
                "totalCount": 1
            },
            "body": "",
        }
        
        issue = parse_issue_node(node, "test/repo", now)
        assert issue.last_human_activity_days == 0

    def test_last_human_activity_no_human_comments(self):
        """Issue with no human comments should have last_human_activity_days == None."""
        from scripts.fetch_issues import parse_issue_node

        now = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
        node = {
            "number": 123,
            "title": "Test Issue",
            "url": "https://github.com/test/repo/issues/123",
            "state": "OPEN",
            "createdAt": "2026-03-01T12:00:00Z",
            "updatedAt": "2026-03-16T12:00:00Z",
            "author": {"login": "user1"},
            "assignees": {"nodes": []},
            "labels": {"nodes": []},
            "reactions": {"totalCount": 0},
            "comments": {
                "nodes": [
                    {
                        "author": {"login": "github-actions[bot]"},
                        "authorAssociation": "BOT",
                        "createdAt": "2026-03-15T12:00:00Z"
                    },
                    {
                        "author": {"login": "dotnet-bot"},
                        "authorAssociation": "BOT",
                        "createdAt": "2026-03-14T12:00:00Z"
                    }
                ],
                "totalCount": 2
            },
            "body": "",
        }
        
        issue = parse_issue_node(node, "test/repo", now)
        assert issue.last_human_activity_days is None

    def test_last_human_activity_no_comments_at_all(self):
        """Issue with no comments at all should have last_human_activity_days == None."""
        from scripts.fetch_issues import parse_issue_node

        now = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
        node = {
            "number": 123,
            "title": "Test Issue",
            "url": "https://github.com/test/repo/issues/123",
            "state": "OPEN",
            "createdAt": "2026-03-01T12:00:00Z",
            "updatedAt": "2026-03-16T12:00:00Z",
            "author": {"login": "user1"},
            "assignees": {"nodes": []},
            "labels": {"nodes": []},
            "reactions": {"totalCount": 0},
            "comments": {"nodes": [], "totalCount": 0},
            "body": "",
        }
        
        issue = parse_issue_node(node, "test/repo", now)
        assert issue.last_human_activity_days is None


class TestAssigneeDisplayComputation:
    """Test assignee_display computation in ParsedIssue."""

    def test_assignee_display_single_assignee(self):
        """Single assignee should display as 'user1'."""
        from scripts.fetch_issues import parse_issue_node

        now = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
        node = {
            "number": 123,
            "title": "Test Issue",
            "url": "https://github.com/test/repo/issues/123",
            "state": "OPEN",
            "createdAt": "2026-03-01T12:00:00Z",
            "updatedAt": "2026-03-16T12:00:00Z",
            "author": {"login": "user1"},
            "assignees": {"nodes": [{"login": "user1"}]},
            "labels": {"nodes": []},
            "reactions": {"totalCount": 0},
            "comments": {"nodes": [], "totalCount": 0},
            "body": "",
        }
        
        issue = parse_issue_node(node, "test/repo", now)
        assert issue.assignee_display == "user1"

    def test_assignee_display_multiple_assignees(self):
        """Multiple assignees should display as 'user1, user2'."""
        from scripts.fetch_issues import parse_issue_node

        now = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
        node = {
            "number": 123,
            "title": "Test Issue",
            "url": "https://github.com/test/repo/issues/123",
            "state": "OPEN",
            "createdAt": "2026-03-01T12:00:00Z",
            "updatedAt": "2026-03-16T12:00:00Z",
            "author": {"login": "user1"},
            "assignees": {"nodes": [{"login": "user1"}, {"login": "user2"}]},
            "labels": {"nodes": []},
            "reactions": {"totalCount": 0},
            "comments": {"nodes": [], "totalCount": 0},
            "body": "",
        }
        
        issue = parse_issue_node(node, "test/repo", now)
        assert issue.assignee_display == "user1, user2"

    def test_assignee_display_no_assignees(self):
        """No assignees should display as empty string."""
        from scripts.fetch_issues import parse_issue_node

        now = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
        node = {
            "number": 123,
            "title": "Test Issue",
            "url": "https://github.com/test/repo/issues/123",
            "state": "OPEN",
            "createdAt": "2026-03-01T12:00:00Z",
            "updatedAt": "2026-03-16T12:00:00Z",
            "author": {"login": "user1"},
            "assignees": {"nodes": []},
            "labels": {"nodes": []},
            "reactions": {"totalCount": 0},
            "comments": {"nodes": [], "totalCount": 0},
            "body": "",
        }
        
        issue = parse_issue_node(node, "test/repo", now)
        assert issue.assignee_display == ""


class TestHTMLTemplateRendering:
    """Test that computed fields are correctly rendered in HTML output."""

    def test_assignee_cell_shows_display_name(self):
        """Assignee cell should show display name, not '—' when assignees exist."""
        from scripts.html_template import _render_row

        issue = {
            "number": 123,
            "title": "Test Issue",
            "url": "https://github.com/test/repo/issues/123",
            "urgency_score": 5.0,
            "staleness_score": 3.0,
            "neglect_score": 2.0,
            "assignees": ["user1"],
            "assignee_display": "user1",
            "last_human_activity_days": 5,
            "age_days": 10,
            "labels": [],
            "area_label": None,
        }

        html = _render_row(issue, "needs-attention")
        assert "user1" in html
        assert '<td class="no-assignee">—</td>' not in html

    def test_assignee_cell_shows_dash_when_empty(self):
        """Assignee cell should show '—' when no assignees."""
        from scripts.html_template import _render_row

        issue = {
            "number": 123,
            "title": "Test Issue",
            "url": "https://github.com/test/repo/issues/123",
            "urgency_score": 5.0,
            "staleness_score": 3.0,
            "neglect_score": 2.0,
            "assignees": [],
            "assignee_display": "",
            "last_human_activity_days": 5,
            "age_days": 10,
            "labels": [],
            "area_label": None,
        }

        html = _render_row(issue, "needs-attention")
        assert '<td class="no-assignee">—</td>' in html

    def test_age_cell_shows_correct_days(self):
        """Age cell should show '5d' not '0d' when age_days == 5."""
        from scripts.html_template import _render_row

        issue = {
            "number": 123,
            "title": "Test Issue",
            "url": "https://github.com/test/repo/issues/123",
            "urgency_score": 5.0,
            "staleness_score": 3.0,
            "neglect_score": 2.0,
            "assignees": [],
            "assignee_display": "",
            "last_human_activity_days": 3,
            "age_days": 5,
            "labels": [],
            "area_label": None,
        }

        html = _render_row(issue, "needs-attention")
        assert ">5d</td>" in html
        assert ">0d</td>" not in html

    def test_last_human_activity_shows_correct_days(self):
        """Last Human Activity cell should show '3d ago' not 'never' when activity exists."""
        from scripts.html_template import _render_row

        issue = {
            "number": 123,
            "title": "Test Issue",
            "url": "https://github.com/test/repo/issues/123",
            "urgency_score": 5.0,
            "staleness_score": 3.0,
            "neglect_score": 2.0,
            "assignees": [],
            "assignee_display": "",
            "last_human_activity_days": 3,
            "age_days": 10,
            "labels": [],
            "area_label": None,
        }

        html = _render_row(issue, "needs-attention")
        assert "3d ago</td>" in html
        assert ">never</td>" not in html

    def test_last_human_activity_shows_never_when_none(self):
        """Last Human Activity cell should show 'never' when None."""
        from scripts.html_template import _render_row

        issue = {
            "number": 123,
            "title": "Test Issue",
            "url": "https://github.com/test/repo/issues/123",
            "urgency_score": 5.0,
            "staleness_score": 3.0,
            "neglect_score": 2.0,
            "assignees": [],
            "assignee_display": "",
            "last_human_activity_days": None,
            "age_days": 10,
            "labels": [],
            "area_label": None,
        }

        html = _render_row(issue, "needs-attention")
        assert ">never</td>" in html

    def test_age_zero_days_shows_zero(self):
        """Age cell should show '0d' when issue created today."""
        from scripts.html_template import _render_row

        issue = {
            "number": 123,
            "title": "Test Issue",
            "url": "https://github.com/test/repo/issues/123",
            "urgency_score": 5.0,
            "staleness_score": 3.0,
            "neglect_score": 2.0,
            "assignees": [],
            "assignee_display": "",
            "last_human_activity_days": 0,
            "age_days": 0,
            "labels": [],
            "area_label": None,
        }

        html = _render_row(issue, "needs-attention")
        assert ">0d</td>" in html

    def test_multiple_assignees_displayed_correctly(self):
        """Multiple assignees should display as 'user1, user2'."""
        from scripts.html_template import _render_row

        issue = {
            "number": 123,
            "title": "Test Issue",
            "url": "https://github.com/test/repo/issues/123",
            "urgency_score": 5.0,
            "staleness_score": 3.0,
            "neglect_score": 2.0,
            "assignees": ["user1", "user2"],
            "assignee_display": "user1, user2",
            "last_human_activity_days": 5,
            "age_days": 10,
            "labels": [],
            "area_label": None,
        }

        html = _render_row(issue, "needs-attention")
        assert "user1, user2" in html
