"""Shared fixtures for KBE Issue Dashboard tests.

Provides body-text fixtures for the parser tests and a factory fixture
(`make_parsed_issue`) that produces `ParsedIssue` dataclass instances
aligned with McManus's actual implementation in scripts/fetch_issues.py.
"""

import sys
import os
import pytest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scripts.fetch_issues import ParsedIssue, analyse_comments


# ---------------------------------------------------------------------------
# Issue body fixtures (strings for parse_hit_counts / parse_error_pattern / …)
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_issue_body_well_formed():
    """Realistic KBE issue body with summary table, error block, and build link."""
    return (
        "## Build Analysis\n"
        "\n"
        "### Summary\n"
        "\n"
        "|24-Hour Hit Count|7-Day Hit Count|1-Month Count|\n"
        "|---|---|---|\n"
        "|12|87|342|\n"
        "\n"
        "### Error Details\n"
        "\n"
        "```json\n"
        '{"ErrorMessage": "System.IO.IOException: The process cannot access the file.", "RetryCount": 3}\n'
        "```\n"
        "\n"
        "### Build Information\n"
        "\n"
        "Build link: https://dev.azure.com/dnceng/public/_build/results?buildId=12345\n"
        "\n"
        "### Timeline\n"
        "\n"
        "| Date | Hits |\n"
        "|---|---|\n"
        "| 2024-01-15 | 5 |\n"
        "| 2024-01-14 | 7 |\n"
    )


@pytest.fixture
def sample_issue_body_minimal():
    """Bare-minimum body: just the KBE hit count table."""
    return (
        "|24-Hour Hit Count|7-Day Hit Count|1-Month Count|\n"
        "|---|---|---|\n"
        "|5|42|180|\n"
    )


@pytest.fixture
def sample_issue_body_malformed():
    """Body with no recognisable KBE table — garbled content."""
    return (
        "This issue tracks flaky test failures.\n"
        "\n"
        "Some random data:\n"
        "- foo\n"
        "- bar\n"
        "\n"
        "No table here at all.\n"
    )


@pytest.fixture
def sample_issue_body_extra_whitespace():
    """Body with extra whitespace/padding in the hit count table."""
    return (
        "| 24-Hour Hit Count | 7-Day Hit Count | 1-Month Count |\n"
        "| --- | --- | --- |\n"
        "|  5  |  42  |  180  |\n"
    )


@pytest.fixture
def sample_issue_body_missing_column():
    """Body where the 1-Month Count column is missing — only 2 columns."""
    return (
        "|24-Hour Hit Count|7-Day Hit Count|\n"
        "|---|---|\n"
        "|5|42|\n"
    )


@pytest.fixture
def sample_issue_body_commas_in_counts():
    """Body with comma-formatted numbers in the hit count table."""
    return (
        "|24-Hour Hit Count|7-Day Hit Count|1-Month Count|\n"
        "|---|---|---|\n"
        "|1,234|5,678|12,345|\n"
    )


@pytest.fixture
def sample_issue_body_zero_counts():
    """Body with all-zero hit counts."""
    return (
        "|24-Hour Hit Count|7-Day Hit Count|1-Month Count|\n"
        "|---|---|---|\n"
        "|0|0|0|\n"
    )


@pytest.fixture
def sample_issue_body_with_error_block():
    """Body containing a JSON error block."""
    return (
        "|24-Hour Hit Count|7-Day Hit Count|1-Month Count|\n"
        "|---|---|---|\n"
        "|3|15|60|\n"
        "\n"
        "```json\n"
        '{"ErrorMessage": "System.IO.IOException: Unable to read data from the transport connection.", "RetryCount": 2}\n'
        "```\n"
    )


@pytest.fixture
def sample_issue_body_with_build_link():
    """Body containing an Azure DevOps build link."""
    return (
        "|24-Hour Hit Count|7-Day Hit Count|1-Month Count|\n"
        "|---|---|---|\n"
        "|3|15|60|\n"
        "\n"
        "Build: https://dev.azure.com/dnceng/public/_build/results?buildId=99999\n"
    )


@pytest.fixture
def sample_issue_body_no_build_link():
    """Body with hit table but no build link anywhere."""
    return (
        "|24-Hour Hit Count|7-Day Hit Count|1-Month Count|\n"
        "|---|---|---|\n"
        "|3|15|60|\n"
        "\n"
        "No links here.\n"
    )


@pytest.fixture
def sample_issue_body_multiple_tables():
    """Body with two tables — only the KBE summary table should be parsed."""
    return (
        "## Other Data\n"
        "\n"
        "| Metric | Value |\n"
        "|---|---|\n"
        "| CPU | 80% |\n"
        "\n"
        "## KBE Summary\n"
        "\n"
        "|24-Hour Hit Count|7-Day Hit Count|1-Month Count|\n"
        "|---|---|---|\n"
        "|8|55|200|\n"
        "\n"
        "## Timeline\n"
        "\n"
        "| Date | Hits |\n"
        "|---|---|\n"
        "| 2024-01-15 | 5 |\n"
    )


# ---------------------------------------------------------------------------
# ParsedIssue factory fixture
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc)


def _make_parsed_issue(
    *,
    hits_24h=0,
    hits_7d=0,
    hits_30d=0,
    labels=None,
    assignees=None,
    created_days_ago=10,
    updated_days_ago=1,
    human_comment_count=0,
    last_human_comment_days_ago=None,
    has_blocking_label=False,
    has_untriaged_label=False,
    area_label=None,
):
    """Build a ParsedIssue with sensible defaults for test isolation."""
    labels = labels or []
    assignees = assignees or []
    created = _NOW - timedelta(days=created_days_ago)
    updated = _NOW - timedelta(days=updated_days_ago)

    last_hc_date = None
    if last_human_comment_days_ago is not None:
        last_hc_date = (_NOW - timedelta(days=last_human_comment_days_ago)).isoformat()

    return ParsedIssue(
        number=12345,
        title="Test KBE issue",
        url="https://github.com/dotnet/runtime/issues/12345",
        state="OPEN",
        created_at=created.isoformat(),
        updated_at=updated.isoformat(),
        author="test-author",
        assignees=assignees,
        labels=labels,
        area_label=area_label,
        comment_count=0,
        human_comment_count=human_comment_count,
        last_human_comment_date=last_hc_date,
        last_human_comment_author=None,
        reactions_count=0,
        hits_24h=hits_24h,
        hits_7d=hits_7d,
        hits_30d=hits_30d,
        error_pattern=None,
        build_link=None,
        has_blocking_label=has_blocking_label,
        has_untriaged_label=has_untriaged_label,
    )


@pytest.fixture
def make_parsed_issue():
    """Factory fixture — call with keyword overrides to get a ParsedIssue."""
    return _make_parsed_issue


@pytest.fixture
def now():
    """Stable 'now' timestamp aligned with the ParsedIssue factory."""
    return _NOW


@pytest.fixture
def sample_issue_data(now):
    """Known-values issue for deterministic score verification — well-attended."""
    return _make_parsed_issue(
        hits_24h=12,
        hits_7d=87,
        hits_30d=342,
        labels=["known-build-error", "area-Infrastructure"],
        assignees=["alice"],
        created_days_ago=5,
        updated_days_ago=2,
        has_blocking_label=False,
        has_untriaged_label=False,
        area_label="area-Infrastructure",
        human_comment_count=1,
        last_human_comment_days_ago=1,
    )


@pytest.fixture
def sample_issue_data_neglected(now):
    """Issue with hits but no assignees and no human comments."""
    return _make_parsed_issue(
        hits_24h=8,
        hits_7d=30,
        hits_30d=100,
        labels=["known-build-error", "untriaged"],
        assignees=[],
        created_days_ago=20,
        updated_days_ago=15,
        has_untriaged_label=True,
        human_comment_count=0,
        last_human_comment_days_ago=None,
    )


@pytest.fixture
def sample_issue_data_stale(now):
    """Issue with zero hits and old timestamps."""
    return _make_parsed_issue(
        hits_24h=0,
        hits_7d=0,
        hits_30d=2,
        labels=["known-build-error", "area-Serialization"],
        assignees=["bob"],
        created_days_ago=90,
        updated_days_ago=45,
        area_label="area-Serialization",
        human_comment_count=1,
        last_human_comment_days_ago=40,
    )
