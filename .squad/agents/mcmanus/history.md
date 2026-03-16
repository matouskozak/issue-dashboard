# McManus — History

## Project Context

- **Project:** KBE Issue Dashboard — Python-based dashboard monitoring GitHub "Known Build Error" issues in dotnet/runtime
- **Stack:** Python, GitHub GraphQL API, Jinja2 templates, HTML/CSS/JS, GitHub Actions
- **User:** Matous Kozak
- **Architecture:** fetch_issues.py → scan.json → build_reports.py → HTML reports → build_index.py → index.html
- **Scoring:** Urgency (0-10), Staleness (0-10), Neglect (0-10) — each with weighted signal components
- **Reports:** needs-attention.html, unattended.html, stale.html, all.html
- **Deployment:** GitHub Pages via GitHub Actions (every 6 hours)

## Learnings

- **GraphQL vs REST:** Used GitHub GraphQL API (not REST) for fetching KBE issues — single query gets all needed fields including nested comments, labels, assignees, and reactions. Pagination via cursor-based `after` parameter, 50 issues per page.
- **Hit count table regex:** KBE issue bodies contain a markdown table with `|24-Hour Hit Count|7-Day Hit Count|1-Month Count|` header. Primary regex matches this header pattern; fallback regex matches any 3-column numeric table after a separator row.
- **Bot filtering:** Human comments identified by excluding `authorAssociation == "BOT"` AND known bot logins (dotnet-issue-labeler, msftbot, dotnet-policy-service, github-actions, fabricbot). Case-insensitive matching.
- **Scoring architecture:** Three scores (urgency, staleness, neglect), each 0–10, each composed of 5–6 weighted signals. Each signal produces value (0–1), multiplied by weight, summed and capped at 10.0. Breakdown stored per-issue for transparency.
- **Output path:** `docs/<repo>/scan.json` — directory auto-created if missing.
- **Real data:** 220 open KBE issues in dotnet/runtime as of March 2026. ~104 with active 7d hits, ~116 scoring high on staleness.
- **Key files:** `scripts/fetch_issues.py` (pipeline entry point), `scripts/requirements.txt` (just `requests`), `docs/runtime/scan.json` (output).

- **build_reports.py architecture:** Reads scan.json, applies four filter functions (needs-attention/unattended/stale/all), calls html_template.render_report() for each, writes meta.json with summary stats and counts dict, appends to history.json with 90-day retention. All scores thresholded at 5.0 for unattended/stale filters.
- **build_index.py is a verifier:** The existing index.html loads repos.json + meta.json dynamically via JS. build_index.py just validates that meta.json files exist for each repo in repos.json — no HTML generation needed.
- **regen_html.py:** Thin wrapper around build_reports.build_reports() — checks scan.json exists, then delegates. Dev convenience only.
- **uv migration:** pyproject.toml at repo root, workflow uses `pip install uv && uv sync`, scripts invoked via `uv run python`. requirements.txt kept as fallback.
- **Deleted build-dashboard.yml:** Was a stale v1 workflow referencing non-existent `src/`, `data/`, `build/` directories. Only `generate-reports.yml` is the real pipeline.
- **html_template.py already had filter logic in main():** build_reports.py duplicates the filter definitions intentionally — keeps the pipeline script self-contained and the template engine as a pure renderer.
- **Hit trend edge case (7d==0, 24h>0):** Spec says return 1.0 — hits appearing in the last 24h with no 7-day baseline is maximum acceleration. Division-by-zero guard must still return 1.0 when 24h > 0, not blanket 0.0.
- **Comma-formatted hit counts:** Real KBE issue bodies can have comma-formatted numbers like `|1,234|5,678|9,012|`. Regex must use `(\d[\d,]*)` instead of `(\d+)`, and `int()` calls must strip commas first via `.replace(",", "")`.

## Spec Deviations Fixed (2026-03-16T12:17Z)

**McManus background task outcome:** Both spec deviations in fetch_issues.py corrected:
1. **hit_trend 7d==0 edge case:** Now returns 1.0 when 24h > 0 (brand-new spike signal)
2. **Comma-formatted hit counts:** Regex updated to `(\d[\d,]*)` and int conversion strips commas
- Hockney verified: 167 tests pass, 0 xfailed. Both edge cases now pass.

## Cross-Team Impact (Wave 1)

- **Fenster (Frontend):** Consumes `scan.json` schema directly. Score breakdowns enable tooltip rendering.
- **Hockney (Tester):** Tests scoring functions imported from `fetch_issues.py`. Validates score consistency.
- **Keaton (Lead):** Orchestrates fetch_issues in CI/CD pipeline. Outputs staged to docs/ for Pages deployment.
