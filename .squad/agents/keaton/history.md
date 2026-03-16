# Keaton — History

## Project Context

- **Project:** KBE Issue Dashboard — Python-based dashboard monitoring GitHub "Known Build Error" issues in dotnet/runtime
- **Stack:** Python, GitHub GraphQL API, Jinja2 templates, HTML/CSS/JS, GitHub Actions
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
