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
