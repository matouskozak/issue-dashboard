# Keaton — History

## Project Context

- **Project:** KBE Issue Dashboard — Python-based dashboard monitoring GitHub "Known Build Error" issues in dotnet/runtime
- **Stack:** Python, GitHub GraphQL API, pure Python templates, HTML/CSS/JS, GitHub Actions
- **User:** Matous Kozak
- **Architecture:** fetch_issues.py → scan.json → build_reports.py → HTML reports → build_index.py → index.html
- **Scoring:** Urgency (0-10), Staleness (0-10), Neglect (0-10) — each with weighted signal components
- **Reports:** needs-attention.html, unattended.html, stale.html, all.html
- **Deployment:** GitHub Pages via GitHub Actions (every 6 hours)

## Learnings

- Created `.github/workflows/generate-reports.yml` with 6-hour cadence and workflow_dispatch trigger
- Created README.md with architecture diagram, scoring explanation, and dev setup instructions
- Confirmed existing squad workflows (heartbeat, issue-assign, triage, sync-labels) remain untouched
- GitHub Actions runs full pipeline: fetch → scan.json → build reports → index → git push to docs/
- GITHUB_TOKEN secret used for GraphQL API auth in fetch_issues and build_reports steps

## Cross-Team Impact (Wave 1)

- **McManus (Backend):** Produces `scan.json` via fetch_issues.py. CI orchestrates this step.
- **Fenster (Frontend):** Renders HTML reports from scan.json. Runs after fetch in pipeline.
- **Hockney (Tester):** Tests run as validation gate. Must pass before reports published.
- **Architecture:** Clean pipeline: GitHub API → Python fetch → JSON schema → Python render → HTML → Pages.

## Repo Cleanup (Post-Wave Audit)

Deleted 9 stale files left behind by multi-agent build waves:

- **Agent reports:** `BUILD_SUMMARY.md`, `FENSTER_COMPLETION_REPORT.md` — build artifacts from Fenster, not project docs
- **Jinja2 template:** `scripts/templates/report.html` + directory — team decided pure Python templates (Decision #3), zero code references
- **Stale test docs:** `tests/TEST_COVERAGE_SUMMARY.md`, `tests/README.md`, `tests/run_tests.sh` — one-time snapshots with outdated info; `uv run pytest tests/` is the canonical runner
- **Redundant docs:** `docs/FRONTEND.md` — documented Jinja2 workflow that doesn't exist; README covers the project
- **Redundant deps:** `scripts/requirements.txt` — `pyproject.toml` is canonical; removed README reference
- **Empty dir:** `docs/runtime/` — empty directory from test generation

**Kept:** All core scripts, test files (test_*.py, conftest.py, __init__.py), docs/ assets, pyproject.toml, README.md, uv.lock.
**Verification:** 167 tests pass after cleanup.
