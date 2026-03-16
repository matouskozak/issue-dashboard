# Squad Team

> KBE Issue Dashboard — issue-dashboard-v2

## Coordinator

| Name | Role | Notes |
|------|------|-------|
| Squad | Coordinator | Routes work, enforces handoffs and reviewer gates. |

## Members

| Name | Role | Charter | Status |
|------|------|---------|--------|
| 🏗️ Keaton | Lead | `.squad/agents/keaton/charter.md` | ✅ Active |
| 🔧 McManus | Backend Dev | `.squad/agents/mcmanus/charter.md` | ✅ Active |
| ⚛️ Fenster | Frontend Dev | `.squad/agents/fenster/charter.md` | ✅ Active |
| 🧪 Hockney | Tester | `.squad/agents/hockney/charter.md` | ✅ Active |
| 📋 Scribe | Session Logger | `.squad/agents/scribe/charter.md` | ✅ Active |
| 🔄 Ralph | Work Monitor | — | 🔄 Monitor |

## Project Context

- **Project:** KBE Issue Dashboard — Python-based dashboard monitoring GitHub "Known Build Error" issues in dotnet/runtime
- **User:** Matous Kozak
- **Stack:** Python, GitHub GraphQL API, Jinja2 templates, HTML/CSS/JS, GitHub Actions
- **Architecture:** fetch_issues.py → scan.json → build_reports.py → HTML reports → build_index.py → index.html
- **Scoring:** Urgency (0-10), Staleness (0-10), Neglect (0-10)
- **Reports:** needs-attention.html, unattended.html, stale.html, all.html
- **Deployment:** GitHub Pages (every 6 hours via GitHub Actions)
- **Created:** 2026-03-16
