# Hockney — History

## Project Context

- **Project:** KBE Issue Dashboard — Python-based dashboard monitoring GitHub "Known Build Error" issues in dotnet/runtime
- **Stack:** Python, GitHub GraphQL API, Jinja2 templates, HTML/CSS/JS, GitHub Actions
- **User:** Matous Kozak
- **Architecture:** fetch_issues.py → scan.json → build_reports.py → HTML reports → build_index.py → index.html
- **Scoring:** Urgency (0-10), Staleness (0-10), Neglect (0-10) — each with weighted signal components
- **Reports:** needs-attention.html, unattended.html, stale.html, all.html
- **Testing focus:** Scoring accuracy, body parsing robustness, pipeline integration, CI validation

## Learnings

- **Scoring functions** take `ParsedIssue` dataclass + `datetime`, return `(float, dict)` — not raw dicts
- **Function names**: `compute_urgency`, `compute_staleness`, `compute_neglect` (no `_score` suffix)
- **Parsing**: three separate functions — `parse_hit_counts(body)→HitCounts`, `parse_error_pattern(body)→Optional[str]`, `parse_build_link(body)→Optional[str]`
- **Signal key names** in breakdowns: `hits_24h`, `hits_7d`, `hit_trend`, `blocking_label`, `age_vs_hits`, `no_assignee` (urgency); `hits_24h_zero`, `hits_7d_zero`, `days_since_update`, `issue_age`, `monthly_count_low` (staleness); `hits_no_assignee`, `hits_no_human_comments`, `high_hits_untriaged`, `days_since_human_comment`, `no_area_label` (neglect)
- **Area label matching** is case-insensitive (`l.lower().startswith("area-")`) — done in `parse_issue_node`
- **Spec deviation found**: hit_trend signal — when 7d==0 and 24h>0, spec says value=1.0 (brand-new spike) but implementation returns 0.0. Marked as xfail.
- **Spec deviation found**: comma-separated numbers (e.g. `1,234`) in hit count table won't parse — regex uses `\d+` only. Marked as xfail.
- **Test file paths**: `tests/conftest.py`, `tests/test_scoring.py`, `tests/test_body_parsing.py`
- **Test count**: 167 passing, 0 xfailed (previously 165+2xfail)
- **McManus fixes verified (2026-03-16T12:17Z):** Both spec deviations resolved — `test_trend_7d_zero_24h_positive` (hit_trend returns 1.0 when 7d==0, 24h>0) and `test_commas_in_counts` (regex handles `|1,234|5,678|12,345|`) now pass. xfail markers removed. Full suite: 167 passed, 0 failed, 0 xfailed.

## Test Suite Updated (2026-03-16T12:17Z)

**Hockney background task outcome:** Removed xfail markers from both spec deviation tests. Full validation run:
- **Before:** 165 passed, 2 xfailed
- **After:** 167 passed, 0 failed, 0 xfailed
- All tests passing including previously-failing edge cases. Backend fixes verified by test suite.

## Cross-Team Impact (Wave 1)

- **McManus (Backend):** Provides `fetch_issues.py` with importable scoring functions. Tests validate these functions.
- **Fenster (Frontend):** Tests confirm `scan.json` schema matches expected structure. Breakdowns validated.
- **Keaton (Lead):** CI/CD pipeline runs tests on PR/push. Must pass before merge.
- **Test coverage:** 35 tests (scoring + body parsing) passed on first build.

## Computed Display Fields Tested (2026-03-16T14:30Z)

**Task:** Verify McManus's computed fields fix (`age_days`, `last_human_activity_days`, `assignee_display`)

**Tests written in `tests/test_computed_fields.py`:**
- `_days_between()` helper — 6 tests covering same-day, 5-day, 100-day, fractional, invalid, and None cases
- `age_days` computation — 3 tests (5 days, today, 100 days ago)
- `last_human_activity_days` computation — 4 tests (3 days ago, today, no human comments, no comments at all)
- `assignee_display` computation — 3 tests (single, multiple, no assignees)
- HTML template rendering — 7 tests verifying cells show correct values (not "—" or "never" when data exists)

**Edge cases discovered:**
1. `_days_between(None, now)` raises `AttributeError` (None.replace fails) — current implementation doesn't handle None input gracefully. Documented but not critical (GraphQL always returns strings).
2. Test data must include `authorAssociation` field for bot detection to work correctly — bot login names alone not sufficient.

**Results:**
- 23 new tests, all passing
- Full suite: **190 passed** (167 original + 23 new)
- Zero failures, zero xfails
- Computed fields work correctly: McManus's fix verified

**Impact:** Dashboard columns (Assignee, Last Human Activity, Age) will now display correctly instead of showing empty/zero values.

## Wave 2: Agent 18 (2026-03-16T1900Z)

**Task:** Test McManus's computed display fields fix.

**Work:** Created `tests/test_computed_fields.py` with 23 tests covering:
- `_days_between()` helper — 6 tests (same-day, 5-day, 100-day, fractional days, invalid dates, None handling)
- `age_days` computation — 3 tests (5 days ago, today, 100 days ago)
- `last_human_activity_days` computation — 4 tests (3 days ago, today, no human comments, all-bot comments)
- `assignee_display` computation — 3 tests (single, multiple, no assignees)
- HTML template rendering — 7 tests (verify cells display computed values vs. fallback dash/never text)

**Edge cases documented:**
- `_days_between(None, now)` raises AttributeError — not critical since GraphQL always returns strings
- Test data must include `authorAssociation` field for bot filtering to work

**Results:**
- **Before:** 167 tests pass
- **After:** 190 tests pass (167 original + 23 new computed field tests)
- Zero failures, zero xfails
- Backward compatibility verified — raw fields remain in scan.json, new fields are additive
