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

## Cross-Team Impact (Wave 1)

- **Fenster (Frontend):** Consumes `scan.json` schema directly. Score breakdowns enable tooltip rendering.
- **Hockney (Tester):** Tests scoring functions imported from `fetch_issues.py`. Validates score consistency.
- **Keaton (Lead):** Orchestrates fetch_issues in CI/CD pipeline. Outputs staged to docs/ for Pages deployment.
