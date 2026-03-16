"""
Tests for issue body parsing functionality.

Tests extraction of structured data from GitHub issue bodies in various formats,
including score fields, priority indicators, and tags. Covers both well-formed
and malformed inputs to ensure robustness.
"""

import pytest
from unittest.mock import MagicMock


# Mock the body parser module (implementation pending)
class BodyParser:
    """Mock body parser for testing. Replace with actual import when implemented."""
    
    @staticmethod
    def extract_score(body):
        """Extract score from issue body. Returns int or None."""
        if not body:
            return None
        
        # Handle markdown heading format
        if "### Score\n" in body:
            lines = body.split("\n")
            for i, line in enumerate(lines):
                if line.strip() == "### Score" and i + 1 < len(lines):
                    try:
                        return int(lines[i + 1].strip())
                    except ValueError:
                        return None
        
        # Handle bold format
        if "**Score:**" in body:
            parts = body.split("**Score:**")
            if len(parts) > 1:
                try:
                    return int(parts[1].strip().split()[0])
                except (ValueError, IndexError):
                    return None
        
        # Handle colon format
        if "Score:" in body:
            parts = body.split("Score:")
            if len(parts) > 1:
                value = parts[1].strip().split()[0]
                # Handle text values
                if value.lower() == "high":
                    return 8
                elif value.lower() == "low":
                    return 3
                elif value.lower() == "medium":
                    return 5
                try:
                    return int(value)
                except ValueError:
                    return None
        
        return None
    
    @staticmethod
    def extract_priority(body):
        """Extract priority from issue body."""
        if not body:
            return None
        
        patterns = ["**Priority:**", "Priority:", "### Priority\n"]
        for pattern in patterns:
            if pattern in body:
                if pattern.endswith("\n"):
                    lines = body.split("\n")
                    for i, line in enumerate(lines):
                        if line.strip() == pattern.strip() and i + 1 < len(lines):
                            return lines[i + 1].strip()
                else:
                    parts = body.split(pattern)
                    if len(parts) > 1:
                        return parts[1].strip().split()[0]
        return None
    
    @staticmethod
    def extract_tags(body):
        """Extract tags/labels from issue body."""
        if not body:
            return []
        
        tags = []
        patterns = ["**Tags:**", "Tags:", "### Tags\n"]
        
        for pattern in patterns:
            if pattern in body:
                if pattern.endswith("\n"):
                    lines = body.split("\n")
                    for i, line in enumerate(lines):
                        if line.strip() == pattern.strip() and i + 1 < len(lines):
                            tags_str = lines[i + 1].strip()
                            tags = [t.strip() for t in tags_str.split(",")]
                            break
                else:
                    parts = body.split(pattern)
                    if len(parts) > 1:
                        tags_str = parts[1].strip().split("\n")[0]
                        tags = [t.strip() for t in tags_str.split(",")]
                break
        
        return [tag for tag in tags if tag]
    
    @staticmethod
    def parse_issue_body(body):
        """Parse complete issue body and extract all fields."""
        return {
            "score": BodyParser.extract_score(body),
            "priority": BodyParser.extract_priority(body),
            "tags": BodyParser.extract_tags(body)
        }


@pytest.fixture
def markdown_heading_score_body():
    """Issue body with markdown heading format for score."""
    return """
## Issue Description
This is a test issue for parsing.

### Score
5

### Priority
High

Some additional content here.
"""


@pytest.fixture
def bold_score_body():
    """Issue body with bold markdown format for score."""
    return """
**Score:** 8
**Priority:** Medium

This issue needs attention.
"""


@pytest.fixture
def text_score_high_body():
    """Issue body with text-based score (High)."""
    return """
Score: High
Priority: Critical

Build is failing consistently.
"""


@pytest.fixture
def text_score_low_body():
    """Issue body with text-based score (Low)."""
    return """
Score: Low

Minor documentation issue.
"""


@pytest.fixture
def missing_score_body():
    """Issue body without any score field."""
    return """
## Description
This issue has no score field at all.

Priority: Medium
"""


@pytest.fixture
def malformed_score_body():
    """Issue body with malformed score value."""
    return """
### Score
not_a_number

Priority: High
"""


@pytest.fixture
def empty_body():
    """Empty issue body."""
    return ""


@pytest.fixture
def multi_field_body():
    """Issue body with score, priority, and tags."""
    return """
### Score
7

**Priority:** High

**Tags:** bug, performance, regression

## Description
Multiple fields to extract.
"""


@pytest.fixture
def mixed_format_body():
    """Issue body with mixed formatting styles."""
    return """
Score: 6
**Priority:** Medium
### Tags
ci-failure, flaky-test
"""


class TestScoreExtraction:
    """Test suite for score extraction from issue bodies."""
    
    def test_extract_score_markdown_heading(self, markdown_heading_score_body):
        """
        Test extraction of score from markdown heading format.
        
        Format: ### Score\n5
        Expected: Returns integer 5
        """
        parser = BodyParser()
        score = parser.extract_score(markdown_heading_score_body)
        assert score == 5
        assert isinstance(score, int)
    
    def test_extract_score_bold_format(self, bold_score_body):
        """
        Test extraction of score from bold markdown format.
        
        Format: **Score:** 8
        Expected: Returns integer 8
        """
        parser = BodyParser()
        score = parser.extract_score(bold_score_body)
        assert score == 8
        assert isinstance(score, int)
    
    def test_extract_score_text_high(self, text_score_high_body):
        """
        Test extraction and mapping of text score "High".
        
        Format: Score: High
        Expected: Maps to numeric value 8
        """
        parser = BodyParser()
        score = parser.extract_score(text_score_high_body)
        assert score == 8
        assert isinstance(score, int)
    
    def test_extract_score_text_low(self, text_score_low_body):
        """
        Test extraction and mapping of text score "Low".
        
        Format: Score: Low
        Expected: Maps to numeric value 3
        """
        parser = BodyParser()
        score = parser.extract_score(text_score_low_body)
        assert score == 3
        assert isinstance(score, int)
    
    def test_extract_score_text_medium(self):
        """
        Test extraction and mapping of text score "Medium".
        
        Format: Score: Medium
        Expected: Maps to numeric value 5
        """
        body = "Score: Medium\n\nSome content"
        parser = BodyParser()
        score = parser.extract_score(body)
        assert score == 5
        assert isinstance(score, int)
    
    def test_missing_score_returns_none(self, missing_score_body):
        """
        Test handling of missing score field.
        
        Expected: Returns None when no score field is present
        """
        parser = BodyParser()
        score = parser.extract_score(missing_score_body)
        assert score is None
    
    def test_malformed_score_returns_none(self, malformed_score_body):
        """
        Test handling of malformed score value.
        
        Format: ### Score\nnot_a_number
        Expected: Returns None for invalid numeric value
        """
        parser = BodyParser()
        score = parser.extract_score(malformed_score_body)
        assert score is None
    
    def test_empty_body_returns_none(self, empty_body):
        """
        Test handling of empty issue body.
        
        Expected: Returns None for empty string
        """
        parser = BodyParser()
        score = parser.extract_score(empty_body)
        assert score is None
    
    def test_none_body_returns_none(self):
        """
        Test handling of None body.
        
        Expected: Returns None when body is None
        """
        parser = BodyParser()
        score = parser.extract_score(None)
        assert score is None
    
    def test_score_with_extra_whitespace(self):
        """
        Test score extraction with extra whitespace.
        
        Format: ### Score\n  5  
        Expected: Correctly parses and trims whitespace
        """
        body = "### Score\n  5  \n\nContent"
        parser = BodyParser()
        score = parser.extract_score(body)
        assert score == 5
    
    def test_score_colon_format(self):
        """
        Test score extraction from simple colon format.
        
        Format: Score: 9
        Expected: Returns integer 9
        """
        body = "Score: 9\nSome other content"
        parser = BodyParser()
        score = parser.extract_score(body)
        assert score == 9


class TestPriorityExtraction:
    """Test suite for priority extraction from issue bodies."""
    
    def test_extract_priority_markdown_heading(self, markdown_heading_score_body):
        """
        Test extraction of priority from markdown heading format.
        
        Format: ### Priority\nHigh
        Expected: Returns "High"
        """
        parser = BodyParser()
        priority = parser.extract_priority(markdown_heading_score_body)
        assert priority == "High"
    
    def test_extract_priority_bold_format(self, bold_score_body):
        """
        Test extraction of priority from bold format.
        
        Format: **Priority:** Medium
        Expected: Returns "Medium"
        """
        parser = BodyParser()
        priority = parser.extract_priority(bold_score_body)
        assert priority == "Medium"
    
    def test_extract_priority_colon_format(self, text_score_high_body):
        """
        Test extraction of priority from colon format.
        
        Format: Priority: Critical
        Expected: Returns "Critical"
        """
        parser = BodyParser()
        priority = parser.extract_priority(text_score_high_body)
        assert priority == "Critical"
    
    def test_missing_priority_returns_none(self):
        """
        Test handling of missing priority field.
        
        Expected: Returns None when no priority is present
        """
        body = "### Score\n5\n\nNo priority here."
        parser = BodyParser()
        priority = parser.extract_priority(body)
        assert priority is None
    
    def test_empty_body_priority(self, empty_body):
        """
        Test priority extraction from empty body.
        
        Expected: Returns None for empty string
        """
        parser = BodyParser()
        priority = parser.extract_priority(empty_body)
        assert priority is None


class TestTagsExtraction:
    """Test suite for tags extraction from issue bodies."""
    
    def test_extract_tags_bold_format(self, multi_field_body):
        """
        Test extraction of comma-separated tags from bold format.
        
        Format: **Tags:** bug, performance, regression
        Expected: Returns list of three tags
        """
        parser = BodyParser()
        tags = parser.extract_tags(multi_field_body)
        assert tags == ["bug", "performance", "regression"]
        assert isinstance(tags, list)
    
    def test_extract_tags_markdown_heading(self, mixed_format_body):
        """
        Test extraction of tags from markdown heading format.
        
        Format: ### Tags\nci-failure, flaky-test
        Expected: Returns list of two tags
        """
        parser = BodyParser()
        tags = parser.extract_tags(mixed_format_body)
        assert tags == ["ci-failure", "flaky-test"]
    
    def test_missing_tags_returns_empty_list(self, markdown_heading_score_body):
        """
        Test handling of missing tags field.
        
        Expected: Returns empty list when no tags present
        """
        parser = BodyParser()
        tags = parser.extract_tags(markdown_heading_score_body)
        assert tags == []
        assert isinstance(tags, list)
    
    def test_empty_body_tags(self, empty_body):
        """
        Test tags extraction from empty body.
        
        Expected: Returns empty list for empty string
        """
        parser = BodyParser()
        tags = parser.extract_tags(empty_body)
        assert tags == []
    
    def test_single_tag(self):
        """
        Test extraction of single tag.
        
        Format: Tags: urgent
        Expected: Returns list with one tag
        """
        body = "Tags: urgent\n\nSome content"
        parser = BodyParser()
        tags = parser.extract_tags(body)
        assert tags == ["urgent"]
    
    def test_tags_with_whitespace(self):
        """
        Test tags extraction with inconsistent whitespace.
        
        Format: Tags: bug,  performance  , regression
        Expected: Correctly trims whitespace from each tag
        """
        body = "Tags: bug,  performance  , regression\n"
        parser = BodyParser()
        tags = parser.extract_tags(body)
        assert tags == ["bug", "performance", "regression"]


class TestCompleteBodyParsing:
    """Test suite for complete issue body parsing."""
    
    def test_parse_multi_field_body(self, multi_field_body):
        """
        Test parsing body with multiple fields (score, priority, tags).
        
        Expected: Returns dict with all three fields populated
        """
        parser = BodyParser()
        result = parser.parse_issue_body(multi_field_body)
        
        assert result["score"] == 7
        assert result["priority"] == "High"
        assert result["tags"] == ["bug", "performance", "regression"]
    
    def test_parse_partial_body(self, markdown_heading_score_body):
        """
        Test parsing body with only some fields present.
        
        Expected: Returns dict with available fields, None/empty for missing
        """
        parser = BodyParser()
        result = parser.parse_issue_body(markdown_heading_score_body)
        
        assert result["score"] == 5
        assert result["priority"] == "High"
        assert result["tags"] == []
    
    def test_parse_empty_body(self, empty_body):
        """
        Test parsing completely empty body.
        
        Expected: Returns dict with all None/empty values
        """
        parser = BodyParser()
        result = parser.parse_issue_body(empty_body)
        
        assert result["score"] is None
        assert result["priority"] is None
        assert result["tags"] == []
    
    def test_parse_mixed_format_body(self, mixed_format_body):
        """
        Test parsing body with mixed formatting styles.
        
        Expected: Successfully extracts fields regardless of format variation
        """
        parser = BodyParser()
        result = parser.parse_issue_body(mixed_format_body)
        
        assert result["score"] == 6
        assert result["priority"] == "Medium"
        assert result["tags"] == ["ci-failure", "flaky-test"]


class TestEdgeCases:
    """Test suite for edge cases and boundary conditions."""
    
    def test_multiple_score_fields(self):
        """
        Test body with multiple score fields (malformed).
        
        Expected: Returns first encountered score
        """
        body = "### Score\n5\n\nScore: 8\n\n**Score:** 10"
        parser = BodyParser()
        score = parser.extract_score(body)
        assert score == 5
    
    def test_score_in_code_block(self):
        """
        Test that score inside code block is not extracted.
        
        Note: This is a specification decision - should we ignore
        scores in code blocks? Current implementation may extract them.
        Document behavior for future refinement.
        """
        body = """
Some text
```
### Score
999
```
**Score:** 5
"""
        parser = BodyParser()
        score = parser.extract_score(body)
        # Current implementation will find first match
        # Future: May want to skip code blocks
        assert score is not None
    
    def test_negative_score(self):
        """
        Test handling of negative score value.
        
        Format: Score: -5
        Expected: Returns -5 (validation happens in scoring logic)
        """
        body = "Score: -5"
        parser = BodyParser()
        score = parser.extract_score(body)
        assert score == -5
    
    def test_large_score(self):
        """
        Test handling of score > 10 (out of normal range).
        
        Format: Score: 100
        Expected: Returns 100 (validation happens in scoring logic)
        """
        body = "Score: 100"
        parser = BodyParser()
        score = parser.extract_score(body)
        assert score == 100
    
    def test_zero_score(self):
        """
        Test handling of zero score.
        
        Format: Score: 0
        Expected: Returns 0 (valid score)
        """
        body = "Score: 0"
        parser = BodyParser()
        score = parser.extract_score(body)
        assert score == 0
    
    def test_float_score(self):
        """
        Test handling of decimal score value.
        
        Format: Score: 5.7
        Expected: Parsing behavior depends on implementation
        """
        body = "Score: 5.7"
        parser = BodyParser()
        score = parser.extract_score(body)
        # May return None or truncated int depending on implementation
        assert score is None or isinstance(score, int)
    
    def test_unicode_in_tags(self):
        """
        Test tags with unicode characters.
        
        Expected: Correctly handles unicode in tag names
        """
        body = "Tags: bug🐛, performance⚡, regression"
        parser = BodyParser()
        tags = parser.extract_tags(body)
        assert "bug🐛" in tags
        assert "performance⚡" in tags
    
    def test_very_long_body(self):
        """
        Test parsing very long issue body.
        
        Expected: Parser handles large input without performance issues
        """
        body = "Score: 7\n" + ("A" * 10000) + "\nPriority: High"
        parser = BodyParser()
        result = parser.parse_issue_body(body)
        assert result["score"] == 7
        assert result["priority"] == "High"
    
    def test_case_insensitive_text_scores(self):
        """
        Test that text score mappings are case-insensitive.
        
        Format: Score: HIGH, Score: high, Score: HiGh
        Expected: All map to same numeric value
        """
        bodies = ["Score: HIGH", "Score: high", "Score: HiGh"]
        parser = BodyParser()
        scores = [parser.extract_score(body) for body in bodies]
        assert all(s == 8 for s in scores)
