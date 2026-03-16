# Decisions

## Wave 1 Build Architecture

**Decision:** Parallel four-agent architecture for initial build.

**Reasoning:**
- Backend (fetch_issues.py), Frontend (html_template.py), Testing, and CI/CD are independent
- Allows maximum velocity during first wave
- No blocking dependencies between agents

**Date:** 2026-03-16T11:34  
**Approved by:** Scribe (on behalf of team)

## Post-Wave Repo Cleanup

**Decision:** Delete 9 stale files and 2 empty directories left behind by multi-agent build waves.

**By:** Keaton (Lead)  
**Date:** 2026-03-16T12:23

**Files Removed:**
- `BUILD_SUMMARY.md` — agent build artifact
- `FENSTER_COMPLETION_REPORT.md` — agent completion report
- `scripts/templates/report.html` + `scripts/templates/` — unused Jinja2 template (Decision #1: no Jinja2)
- `tests/TEST_COVERAGE_SUMMARY.md` — stale one-time test snapshot
- `tests/README.md` — referenced deleted files
- `tests/run_tests.sh` — redundant with `uv run pytest tests/`
- `docs/FRONTEND.md` — documented non-existent Jinja2 workflow
- `scripts/requirements.txt` — redundant with `pyproject.toml`
- `docs/runtime/` — empty directory

**Reasoning:** Multi-agent builds produce intermediate artifacts (reports, summaries, alternative implementations) that don't belong in final product. These files create confusion about what's canonical.

**Impact:** No code changes—only deletions of unused files. 167 tests pass. README updated to reflect accurate file tree.

## Computed Display Fields in scan.json

**By:** McManus  
**Date:** 2026-03-16  
**Affects:** Fenster (HTML templates), Hockney (tests), Keaton (pipeline)

### What

Added three computed display fields to `scan.json` output, calculated in `fetch_issues.py`:

1. **`age_days`** (int) — Days since issue creation
   - Computed from `created_at` ISO timestamp
   - Always present (defaults to 0 if parsing fails)

2. **`last_human_activity_days`** (int or null) — Days since last human comment
   - Computed from `last_human_comment_date` ISO timestamp
   - `null` if no human comments exist on the issue

3. **`assignee_display`** (string) — Comma-joined assignee names
   - Computed from `assignees` list
   - Empty string if no assignees

### Why

**Root cause:** Field name mismatch between data producer and consumer caused three dashboard columns to break:
- **Assignee** column read `issue.assignee` (string) but scan.json only had `assignees` (list)
- **Last Human Activity** column read `issue.last_human_activity_days` (int) but scan.json only had `last_human_comment_date` (ISO timestamp)
- **Age** column read `issue.age_days` (int) but scan.json only had `created_at` (ISO timestamp)

**Solution:** Pre-compute display-ready values at data generation time instead of forcing every consumer to parse dates and format lists.

### Principles

**Separation of concerns:** Data layer computes once, presentation layer displays directly.

**Single source of truth:** `_days_between()` logic lives in one place (fetch_issues.py), not duplicated in every consumer.

**Backward compatibility:** Raw fields remain in scan.json; new fields are additive; HTML template has fallback logic.

## Mobile Label List for Dashboard Filtering

**By:** Fenster  
**Date:** 2026-03-16

### What

Defined the canonical set of dotnet/runtime labels that identify mobile/mono/wasm platform issues for the dashboard "Hide mobile" filter toggle.

### Label Detection Strategy

Two-tier matching against issue labels (case-insensitive):

**Exact matches (lowercased):**
- `area-infrastructure-mono` — Mono runtime, used for mobile platforms
- `arch-wasm` — WebAssembly architecture
- `os-android`
- `os-ios`
- `os-tvos`
- `os-maccatalyst`
- `os-browser` — wasm/browser platform

**Keyword substring matches:**
Any label containing (case-insensitive): `android`, `ios`, `wasm`, `browser`, `mono`, `maccatalyst`, `tvos`

### Why

The keyword fallback catches variant labels like `mono-aot`, `area-Browser-Dom`, or any new mobile-related labels that follow dotnet/runtime naming conventions. The exact-match set ensures the common well-known labels are caught even if the keyword approach is later tightened.

### Impact

- **Fenster:** `_is_mobile_issue()` in `scripts/html_template.py` implements this logic. Rows get `data-mobile="true"` attribute.
- **JS:** `pages/shared-ui.js` uses `data-mobile` attribute to hide/show rows via checkbox.
- **If new mobile labels are added to dotnet/runtime:** Update `_MOBILE_LABELS_EXACT` or `_MOBILE_KEYWORDS` in `html_template.py`.
