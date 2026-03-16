"""Tests for KBE Issue Dashboard scoring logic.

Scoring spec defines three scores (0–10 each): Urgency, Staleness, Neglect.
Each is a weighted sum of signal values, capped at 10.0.

Functions under test:
    compute_urgency(issue: ParsedIssue, now: datetime) -> (float, dict)
    compute_staleness(issue: ParsedIssue, now: datetime) -> (float, dict)
    compute_neglect(issue: ParsedIssue, now: datetime) -> (float, dict)
"""

import sys
import os
import pytest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scripts.fetch_issues import (
    compute_urgency,
    compute_staleness,
    compute_neglect,
    ParsedIssue,
)


# =========================================================================
# URGENCY SCORE
# =========================================================================


class TestUrgencyScore:
    """Urgency: weighted sum of 24h hits, 7d hits, trend, blocking label,
    age-vs-hits bonus, and no-assignee flag.  Capped at 10.0."""

    # --- zero / minimal input -------------------------------------------

    def test_zero_hits_no_labels_assigned(self, make_parsed_issue, now):
        """All zeros and no flags → urgency ≈ 0."""
        issue = make_parsed_issue(
            hits_24h=0, hits_7d=0, assignees=["someone"]
        )
        score, _ = compute_urgency(issue, now)
        assert score == pytest.approx(0.0, abs=0.01)

    def test_zero_hits_no_assignee(self, make_parsed_issue, now):
        """Zero hits but no assignee → only no-assignee fires (1.0×1.0 = 1.0)."""
        issue = make_parsed_issue(hits_24h=0, hits_7d=0, assignees=[])
        score, _ = compute_urgency(issue, now)
        assert score == pytest.approx(1.0, abs=0.01)

    # --- 24h hit count thresholds ----------------------------------------

    @pytest.mark.parametrize(
        "hits_24h, expected_value",
        [
            (0, 0.0),
            (1, 0.5),
            (5, 0.5),
            (6, 0.75),
            (10, 0.75),
            (11, 1.0),
            (100, 1.0),
        ],
    )
    def test_24h_hit_thresholds(self, make_parsed_issue, now, hits_24h, expected_value):
        """24h hit signal: >10→1.0, >5→0.75, >0→0.5, 0→0.0."""
        issue = make_parsed_issue(
            hits_24h=hits_24h, hits_7d=0, assignees=["x"]
        )
        _, breakdown = compute_urgency(issue, now)
        assert breakdown["hits_24h"]["value"] == pytest.approx(expected_value, abs=0.01)
        assert breakdown["hits_24h"]["contribution"] == pytest.approx(
            expected_value * 3.0, abs=0.01
        )

    # --- 7d hit count thresholds -----------------------------------------

    @pytest.mark.parametrize(
        "hits_7d, expected_value",
        [
            (0, 0.0),
            (1, 0.0),
            (5, 0.0),
            (6, 0.5),
            (20, 0.5),
            (21, 0.75),
            (50, 0.75),
            (51, 1.0),
        ],
    )
    def test_7d_hit_thresholds(self, make_parsed_issue, now, hits_7d, expected_value):
        """7d hit signal: >50→1.0, >20→0.75, >5→0.5, else 0.0."""
        issue = make_parsed_issue(
            hits_24h=0, hits_7d=hits_7d, assignees=["x"]
        )
        _, breakdown = compute_urgency(issue, now)
        assert breakdown["hits_7d"]["value"] == pytest.approx(expected_value, abs=0.01)

    # --- hit trend -------------------------------------------------------

    def test_trend_accelerating(self, make_parsed_issue, now):
        """24h=10, 7d=10 → ratio = 10*7/10 = 7.0 → value 1.0."""
        issue = make_parsed_issue(hits_24h=10, hits_7d=10, assignees=["x"])
        _, breakdown = compute_urgency(issue, now)
        assert breakdown["hit_trend"]["value"] == pytest.approx(1.0, abs=0.01)

    def test_trend_decelerating(self, make_parsed_issue, now):
        """24h=1, 7d=100 → ratio = 1*7/100 = 0.07 → value 0.0."""
        issue = make_parsed_issue(hits_24h=1, hits_7d=100, assignees=["x"])
        _, breakdown = compute_urgency(issue, now)
        assert breakdown["hit_trend"]["value"] == pytest.approx(0.0, abs=0.01)

    def test_trend_moderate(self, make_parsed_issue, now):
        """24h=5, 7d=30 → ratio = 5*7/30 ≈ 1.17 → value 0.75 (>1.0)."""
        issue = make_parsed_issue(hits_24h=5, hits_7d=30, assignees=["x"])
        _, breakdown = compute_urgency(issue, now)
        assert breakdown["hit_trend"]["value"] == pytest.approx(0.75, abs=0.01)

    def test_trend_both_zero(self, make_parsed_issue, now):
        """Both 24h and 7d are 0 → value 0.0."""
        issue = make_parsed_issue(hits_24h=0, hits_7d=0, assignees=["x"])
        _, breakdown = compute_urgency(issue, now)
        assert breakdown["hit_trend"]["value"] == pytest.approx(0.0, abs=0.01)

    def test_trend_7d_zero_24h_positive(self, make_parsed_issue, now):
        """Spec: 7d=0 and 24h>0 → value 1.0 (brand-new spike)."""
        issue = make_parsed_issue(hits_24h=5, hits_7d=0, assignees=["x"])
        _, breakdown = compute_urgency(issue, now)
        assert breakdown["hit_trend"]["value"] == pytest.approx(1.0, abs=0.01)

    # --- blocking label --------------------------------------------------

    def test_blocking_label_present(self, make_parsed_issue, now):
        """'blocking-clean-ci' label → value 1.0 (×1.5 weight)."""
        issue = make_parsed_issue(
            hits_24h=0, hits_7d=0,
            has_blocking_label=True, assignees=["x"],
        )
        _, breakdown = compute_urgency(issue, now)
        assert breakdown["blocking_label"]["value"] == pytest.approx(1.0)

    def test_blocking_label_absent(self, make_parsed_issue, now):
        """No blocking label → value 0.0."""
        issue = make_parsed_issue(
            hits_24h=0, hits_7d=0,
            has_blocking_label=False, assignees=["x"],
        )
        _, breakdown = compute_urgency(issue, now)
        assert breakdown["blocking_label"]["value"] == pytest.approx(0.0)

    # --- age vs hits -----------------------------------------------------

    def test_new_issue_high_hits(self, make_parsed_issue, now):
        """Issue < 3 days old AND hits_24h > 5 → value 1.0."""
        issue = make_parsed_issue(
            hits_24h=10, hits_7d=0,
            created_days_ago=1, assignees=["x"],
        )
        _, breakdown = compute_urgency(issue, now)
        assert breakdown["age_vs_hits"]["value"] == pytest.approx(1.0)

    def test_new_issue_moderate_hits(self, make_parsed_issue, now):
        """Issue < 7 days old AND hits_24h > 0 → value 0.5."""
        issue = make_parsed_issue(
            hits_24h=3, hits_7d=0,
            created_days_ago=5, assignees=["x"],
        )
        _, breakdown = compute_urgency(issue, now)
        assert breakdown["age_vs_hits"]["value"] == pytest.approx(0.5)

    def test_old_issue_with_hits(self, make_parsed_issue, now):
        """Issue 30 days old → no age bonus even with hits."""
        issue = make_parsed_issue(
            hits_24h=20, hits_7d=100,
            created_days_ago=30, assignees=["x"],
        )
        _, breakdown = compute_urgency(issue, now)
        assert breakdown["age_vs_hits"]["value"] == pytest.approx(0.0)

    def test_new_issue_zero_hits(self, make_parsed_issue, now):
        """Issue < 3 days old but 0 hits → no bonus."""
        issue = make_parsed_issue(
            hits_24h=0, hits_7d=0,
            created_days_ago=1, assignees=["x"],
        )
        _, breakdown = compute_urgency(issue, now)
        assert breakdown["age_vs_hits"]["value"] == pytest.approx(0.0)

    # --- no assignee -----------------------------------------------------

    def test_no_assignee(self, make_parsed_issue, now):
        issue = make_parsed_issue(hits_24h=0, hits_7d=0, assignees=[])
        _, breakdown = compute_urgency(issue, now)
        assert breakdown["no_assignee"]["value"] == pytest.approx(1.0)

    def test_has_assignee(self, make_parsed_issue, now):
        issue = make_parsed_issue(hits_24h=0, hits_7d=0, assignees=["alice"])
        _, breakdown = compute_urgency(issue, now)
        assert breakdown["no_assignee"]["value"] == pytest.approx(0.0)

    # --- score cap -------------------------------------------------------

    def test_score_capped_at_10(self, make_parsed_issue, now):
        """Max out every signal → score ≤ 10.0."""
        issue = make_parsed_issue(
            hits_24h=50, hits_7d=100,
            has_blocking_label=True,
            assignees=[],
            created_days_ago=1,
        )
        score, _ = compute_urgency(issue, now)
        assert score <= 10.0

    def test_high_urgency_combination(self, make_parsed_issue, now):
        """High 24h hits + blocking + no assignee → urgency near max."""
        issue = make_parsed_issue(
            hits_24h=15, hits_7d=60,
            has_blocking_label=True,
            assignees=[],
            created_days_ago=2,
        )
        score, _ = compute_urgency(issue, now)
        assert score >= 8.0

    # --- breakdown structure ---------------------------------------------

    def test_breakdown_keys(self, make_parsed_issue, now):
        """Breakdown dict should contain all six signal keys."""
        issue = make_parsed_issue()
        _, breakdown = compute_urgency(issue, now)
        expected_keys = {
            "hits_24h",
            "hits_7d",
            "hit_trend",
            "blocking_label",
            "age_vs_hits",
            "no_assignee",
        }
        assert set(breakdown.keys()) == expected_keys

    def test_breakdown_contribution_equals_value_times_weight(
        self, make_parsed_issue, now
    ):
        """For every signal, contribution == value × weight."""
        issue = make_parsed_issue(hits_24h=8, hits_7d=25, assignees=[])
        _, breakdown = compute_urgency(issue, now)
        for key, signal in breakdown.items():
            assert signal["contribution"] == pytest.approx(
                signal["value"] * signal["weight"], abs=0.001
            ), f"Mismatch for signal '{key}'"

    def test_total_matches_sum_of_contributions(self, make_parsed_issue, now):
        """Score should equal sum of all contributions (before cap)."""
        issue = make_parsed_issue(hits_24h=3, hits_7d=10, assignees=["a"])
        score, breakdown = compute_urgency(issue, now)
        total = sum(s["contribution"] for s in breakdown.values())
        assert score == pytest.approx(min(total, 10.0), abs=0.01)


# =========================================================================
# STALENESS SCORE
# =========================================================================


class TestStalenessScore:
    """Staleness: weighted sum of zero-hit flags, update recency, age, low-month count."""

    def test_active_issue_low_staleness(self, make_parsed_issue, now):
        """Recent activity across all windows → staleness near 0."""
        issue = make_parsed_issue(
            hits_24h=10, hits_7d=50, hits_30d=200,
            updated_days_ago=1, created_days_ago=5,
        )
        score, _ = compute_staleness(issue, now)
        assert score < 1.0

    def test_stale_issue_high_staleness(self, make_parsed_issue, now):
        """Zero hits + old timestamps → staleness near max."""
        issue = make_parsed_issue(
            hits_24h=0, hits_7d=0, hits_30d=0,
            updated_days_ago=60, created_days_ago=120,
        )
        score, _ = compute_staleness(issue, now)
        assert score >= 8.0

    # --- 24h hits = 0 signal ---------------------------------------------

    def test_24h_zero_signal(self, make_parsed_issue, now):
        issue = make_parsed_issue(hits_24h=0, hits_7d=5, hits_30d=20)
        _, breakdown = compute_staleness(issue, now)
        assert breakdown["hits_24h_zero"]["value"] == pytest.approx(1.0)

    def test_24h_nonzero_signal(self, make_parsed_issue, now):
        issue = make_parsed_issue(hits_24h=1, hits_7d=5, hits_30d=20)
        _, breakdown = compute_staleness(issue, now)
        assert breakdown["hits_24h_zero"]["value"] == pytest.approx(0.0)

    # --- 7d hits = 0 signal ----------------------------------------------

    def test_7d_zero_signal(self, make_parsed_issue, now):
        issue = make_parsed_issue(hits_24h=0, hits_7d=0, hits_30d=5)
        _, breakdown = compute_staleness(issue, now)
        assert breakdown["hits_7d_zero"]["value"] == pytest.approx(1.0)

    def test_7d_nonzero_signal(self, make_parsed_issue, now):
        issue = make_parsed_issue(hits_24h=0, hits_7d=1, hits_30d=5)
        _, breakdown = compute_staleness(issue, now)
        assert breakdown["hits_7d_zero"]["value"] == pytest.approx(0.0)

    # --- days since update -----------------------------------------------

    @pytest.mark.parametrize(
        "days_ago, expected_value",
        [
            (1, 0.0),
            (7, 0.0),
            (8, 0.5),
            (14, 0.5),
            (15, 0.75),
            (30, 0.75),
            (31, 1.0),
            (90, 1.0),
        ],
    )
    def test_days_since_update(self, make_parsed_issue, now, days_ago, expected_value):
        issue = make_parsed_issue(updated_days_ago=days_ago)
        _, breakdown = compute_staleness(issue, now)
        assert breakdown["days_since_update"]["value"] == pytest.approx(
            expected_value, abs=0.01
        )

    # --- issue age -------------------------------------------------------

    @pytest.mark.parametrize(
        "created_days_ago, expected_value",
        [
            (1, 0.0),
            (14, 0.0),
            (15, 0.5),
            (30, 0.5),
            (31, 0.75),
            (60, 0.75),
            (61, 1.0),
            (120, 1.0),
        ],
    )
    def test_issue_age(self, make_parsed_issue, now, created_days_ago, expected_value):
        issue = make_parsed_issue(created_days_ago=created_days_ago)
        _, breakdown = compute_staleness(issue, now)
        assert breakdown["issue_age"]["value"] == pytest.approx(
            expected_value, abs=0.01
        )

    # --- 1-month count low -----------------------------------------------

    @pytest.mark.parametrize(
        "hits_30d, expected_value",
        [
            (0, 1.0),
            (4, 1.0),
            (5, 0.5),
            (19, 0.5),
            (20, 0.0),
            (100, 0.0),
        ],
    )
    def test_month_count_low(self, make_parsed_issue, now, hits_30d, expected_value):
        issue = make_parsed_issue(hits_30d=hits_30d)
        _, breakdown = compute_staleness(issue, now)
        assert breakdown["monthly_count_low"]["value"] == pytest.approx(
            expected_value, abs=0.01
        )

    # --- breakdown structure ---------------------------------------------

    def test_breakdown_keys(self, make_parsed_issue, now):
        issue = make_parsed_issue()
        _, breakdown = compute_staleness(issue, now)
        expected_keys = {
            "hits_24h_zero",
            "hits_7d_zero",
            "days_since_update",
            "issue_age",
            "monthly_count_low",
        }
        assert set(breakdown.keys()) == expected_keys

    def test_contribution_equals_value_times_weight(self, make_parsed_issue, now):
        issue = make_parsed_issue(hits_24h=0, hits_7d=0, hits_30d=3, updated_days_ago=20)
        _, breakdown = compute_staleness(issue, now)
        for key, signal in breakdown.items():
            assert signal["contribution"] == pytest.approx(
                signal["value"] * signal["weight"], abs=0.001
            ), f"Mismatch for signal '{key}'"

    def test_total_matches_sum(self, make_parsed_issue, now):
        issue = make_parsed_issue(
            hits_24h=0, hits_7d=0, hits_30d=10, updated_days_ago=35
        )
        score, breakdown = compute_staleness(issue, now)
        total = sum(s["contribution"] for s in breakdown.values())
        assert score == pytest.approx(min(total, 10.0), abs=0.01)

    def test_score_capped_at_10(self, make_parsed_issue, now):
        issue = make_parsed_issue(
            hits_24h=0, hits_7d=0, hits_30d=0,
            updated_days_ago=90, created_days_ago=120,
        )
        score, _ = compute_staleness(issue, now)
        assert score <= 10.0


# =========================================================================
# NEGLECT SCORE
# =========================================================================


class TestNeglectScore:
    """Neglect: weighted sum of hit+no-assignee, hit+no-human-comment,
    high-hits+untriaged, days-since-human-comment, no-area-label."""

    def test_attended_issue_low_neglect(self, make_parsed_issue, now):
        """Assigned, recent human comments, area label → neglect near 0."""
        issue = make_parsed_issue(
            hits_24h=5, hits_7d=20,
            area_label="area-Networking",
            assignees=["alice"],
            human_comment_count=2,
            last_human_comment_days_ago=1,
        )
        score, _ = compute_neglect(issue, now)
        assert score < 1.5

    def test_neglected_issue_high_neglect(self, make_parsed_issue, now):
        """Hits + no assignee + no human comments + untriaged + no area → near max."""
        issue = make_parsed_issue(
            hits_24h=8, hits_7d=30,
            has_untriaged_label=True,
            assignees=[],
            human_comment_count=0,
            last_human_comment_days_ago=None,
        )
        score, _ = compute_neglect(issue, now)
        assert score >= 7.0

    # --- hits + no assignee signal ---------------------------------------

    def test_hits_no_assignee(self, make_parsed_issue, now):
        issue = make_parsed_issue(hits_24h=5, hits_7d=0, assignees=[])
        _, breakdown = compute_neglect(issue, now)
        assert breakdown["hits_no_assignee"]["value"] == pytest.approx(1.0)

    def test_hits_with_assignee(self, make_parsed_issue, now):
        issue = make_parsed_issue(hits_24h=5, hits_7d=0, assignees=["bob"])
        _, breakdown = compute_neglect(issue, now)
        assert breakdown["hits_no_assignee"]["value"] == pytest.approx(0.0)

    def test_no_hits_no_assignee(self, make_parsed_issue, now):
        """Zero hits + no assignee → value 0.0 (needs hits to count)."""
        issue = make_parsed_issue(hits_24h=0, hits_7d=0, assignees=[])
        _, breakdown = compute_neglect(issue, now)
        assert breakdown["hits_no_assignee"]["value"] == pytest.approx(0.0)

    # --- hits + no human comments ----------------------------------------

    def test_hits_no_human_comments(self, make_parsed_issue, now):
        """Active hits + zero human comment count → value 1.0."""
        issue = make_parsed_issue(
            hits_24h=3, hits_7d=10,
            human_comment_count=0,
        )
        _, breakdown = compute_neglect(issue, now)
        assert breakdown["hits_no_human_comments"]["value"] == pytest.approx(1.0)

    def test_hits_with_human_comments(self, make_parsed_issue, now):
        issue = make_parsed_issue(
            hits_24h=3, hits_7d=10,
            human_comment_count=2,
            last_human_comment_days_ago=1,
        )
        _, breakdown = compute_neglect(issue, now)
        assert breakdown["hits_no_human_comments"]["value"] == pytest.approx(0.0)

    def test_hits_no_comments_at_all(self, make_parsed_issue, now):
        issue = make_parsed_issue(hits_24h=3, hits_7d=10, human_comment_count=0)
        _, breakdown = compute_neglect(issue, now)
        assert breakdown["hits_no_human_comments"]["value"] == pytest.approx(1.0)

    def test_no_hits_no_human_comments(self, make_parsed_issue, now):
        """Zero hits + no comments → value 0.0 (no hits means no neglect signal)."""
        issue = make_parsed_issue(hits_24h=0, hits_7d=0, human_comment_count=0)
        _, breakdown = compute_neglect(issue, now)
        assert breakdown["hits_no_human_comments"]["value"] == pytest.approx(0.0)

    # --- high hits + untriaged -------------------------------------------

    def test_high_hits_untriaged(self, make_parsed_issue, now):
        """hits_7d > 20 AND has_untriaged_label → value 1.0."""
        issue = make_parsed_issue(
            hits_7d=25, has_untriaged_label=True,
            assignees=["x"], human_comment_count=1, last_human_comment_days_ago=1,
        )
        _, breakdown = compute_neglect(issue, now)
        assert breakdown["high_hits_untriaged"]["value"] == pytest.approx(1.0)

    def test_high_hits_triaged(self, make_parsed_issue, now):
        """hits_7d > 20 but no untriaged label → value 0.0."""
        issue = make_parsed_issue(
            hits_7d=25, has_untriaged_label=False,
            assignees=["x"], human_comment_count=1, last_human_comment_days_ago=1,
        )
        _, breakdown = compute_neglect(issue, now)
        assert breakdown["high_hits_untriaged"]["value"] == pytest.approx(0.0)

    def test_low_hits_untriaged(self, make_parsed_issue, now):
        """hits_7d ≤ 20 + untriaged → value 0.0 (threshold not met)."""
        issue = make_parsed_issue(
            hits_7d=20, has_untriaged_label=True,
            assignees=["x"], human_comment_count=1, last_human_comment_days_ago=1,
        )
        _, breakdown = compute_neglect(issue, now)
        assert breakdown["high_hits_untriaged"]["value"] == pytest.approx(0.0)

    # --- days since last human comment -----------------------------------

    @pytest.mark.parametrize(
        "days_ago, expected_value",
        [
            (1, 0.0),
            (3, 0.0),
            (4, 0.5),
            (7, 0.5),
            (8, 0.75),
            (14, 0.75),
            (15, 1.0),
            (60, 1.0),
        ],
    )
    def test_days_since_human_comment(
        self, make_parsed_issue, now, days_ago, expected_value
    ):
        issue = make_parsed_issue(
            hits_24h=1, assignees=["x"],
            area_label="area-GC",
            human_comment_count=1,
            last_human_comment_days_ago=days_ago,
        )
        _, breakdown = compute_neglect(issue, now)
        assert breakdown["days_since_human_comment"]["value"] == pytest.approx(
            expected_value, abs=0.01
        )

    def test_no_human_comments_ever(self, make_parsed_issue, now):
        """No human comments at all → value 1.0."""
        issue = make_parsed_issue(
            hits_24h=1, assignees=["x"],
            area_label="area-GC",
            human_comment_count=0,
            last_human_comment_days_ago=None,
        )
        _, breakdown = compute_neglect(issue, now)
        assert breakdown["days_since_human_comment"]["value"] == pytest.approx(1.0)

    # --- no area label ---------------------------------------------------

    def test_no_area_label(self, make_parsed_issue, now):
        """No area_label → value 1.0."""
        issue = make_parsed_issue(
            hits_24h=1, area_label=None,
            assignees=["x"], human_comment_count=1, last_human_comment_days_ago=1,
        )
        _, breakdown = compute_neglect(issue, now)
        assert breakdown["no_area_label"]["value"] == pytest.approx(1.0)

    def test_has_area_label(self, make_parsed_issue, now):
        """area_label present → value 0.0."""
        issue = make_parsed_issue(
            hits_24h=1, area_label="area-GC",
            assignees=["x"], human_comment_count=1, last_human_comment_days_ago=1,
        )
        _, breakdown = compute_neglect(issue, now)
        assert breakdown["no_area_label"]["value"] == pytest.approx(0.0)

    # --- breakdown structure ---------------------------------------------

    def test_breakdown_keys(self, make_parsed_issue, now):
        issue = make_parsed_issue(
            human_comment_count=1, last_human_comment_days_ago=1,
        )
        _, breakdown = compute_neglect(issue, now)
        expected_keys = {
            "hits_no_assignee",
            "hits_no_human_comments",
            "high_hits_untriaged",
            "days_since_human_comment",
            "no_area_label",
        }
        assert set(breakdown.keys()) == expected_keys

    def test_contribution_equals_value_times_weight(self, make_parsed_issue, now):
        issue = make_parsed_issue(
            hits_24h=5, hits_7d=25,
            has_untriaged_label=True, assignees=[],
            human_comment_count=1, last_human_comment_days_ago=10,
        )
        _, breakdown = compute_neglect(issue, now)
        for key, signal in breakdown.items():
            assert signal["contribution"] == pytest.approx(
                signal["value"] * signal["weight"], abs=0.001
            ), f"Mismatch for signal '{key}'"

    def test_total_matches_sum(self, make_parsed_issue, now):
        issue = make_parsed_issue(
            hits_24h=5, assignees=["x"],
            area_label="area-GC",
            human_comment_count=1, last_human_comment_days_ago=1,
        )
        score, breakdown = compute_neglect(issue, now)
        total = sum(s["contribution"] for s in breakdown.values())
        assert score == pytest.approx(min(total, 10.0), abs=0.01)

    def test_score_capped_at_10(self, make_parsed_issue, now):
        issue = make_parsed_issue(
            hits_24h=10, hits_7d=30,
            has_untriaged_label=True,
            assignees=[],
            human_comment_count=0,
            last_human_comment_days_ago=None,
        )
        score, _ = compute_neglect(issue, now)
        assert score <= 10.0


# =========================================================================
# BOT DETECTION (via analyse_comments)
# =========================================================================


class TestBotDetection:
    """Verify _is_human_comment logic through analyse_comments."""

    BOT_LOGINS = [
        "dotnet-issue-labeler",
        "msftbot",
        "dotnet-policy-service",
        "github-actions",
        "fabricbot",
    ]

    def _iso(self, days_ago=1):
        from datetime import datetime, timedelta, timezone
        return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()

    @pytest.mark.parametrize("bot_login", BOT_LOGINS)
    def test_known_bot_not_counted(self, bot_login):
        from scripts.fetch_issues import analyse_comments
        comments = [
            {
                "author": {"login": bot_login},
                "authorAssociation": "BOT",
                "createdAt": self._iso(),
            }
        ]
        total, human, _, _ = analyse_comments(comments)
        assert total == 1
        assert human == 0

    def test_bot_association_filters(self):
        from scripts.fetch_issues import analyse_comments
        comments = [
            {
                "author": {"login": "some-unknown-bot"},
                "authorAssociation": "BOT",
                "createdAt": self._iso(),
            }
        ]
        _, human, _, _ = analyse_comments(comments)
        assert human == 0

    def test_human_association_counts(self):
        from scripts.fetch_issues import analyse_comments
        comments = [
            {
                "author": {"login": "jkotas"},
                "authorAssociation": "MEMBER",
                "createdAt": self._iso(),
            }
        ]
        _, human, last_date, last_author = analyse_comments(comments)
        assert human == 1
        assert last_author == "jkotas"

    def test_mixed_bot_and_human(self):
        from scripts.fetch_issues import analyse_comments
        comments = [
            {
                "author": {"login": "msftbot"},
                "authorAssociation": "BOT",
                "createdAt": self._iso(3),
            },
            {
                "author": {"login": "alice"},
                "authorAssociation": "MEMBER",
                "createdAt": self._iso(1),
            },
        ]
        total, human, last_date, last_author = analyse_comments(comments)
        assert total == 2
        assert human == 1
        assert last_author == "alice"


# =========================================================================
# CROSS-SCORE INTEGRATION
# =========================================================================


class TestCrossScoreConsistency:
    """Verify that scores move in the expected direction for archetypal issues."""

    def test_urgent_issue_not_stale(self, sample_issue_data, now):
        urgency, _ = compute_urgency(sample_issue_data, now)
        staleness, _ = compute_staleness(sample_issue_data, now)
        assert urgency > staleness

    def test_stale_issue_not_urgent(self, sample_issue_data_stale, now):
        urgency, _ = compute_urgency(sample_issue_data_stale, now)
        staleness, _ = compute_staleness(sample_issue_data_stale, now)
        assert staleness > urgency

    def test_neglected_issue_high_neglect(self, sample_issue_data_neglected, now):
        neglect, _ = compute_neglect(sample_issue_data_neglected, now)
        assert neglect >= 6.0
