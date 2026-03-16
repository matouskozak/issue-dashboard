# Fenster — History

## Project Context

- **Project:** KBE Issue Dashboard — Python-based dashboard monitoring GitHub "Known Build Error" issues in dotnet/runtime
- **Stack:** Python (no Jinja2 — uses f-string templates), HTML/CSS/JS, GitHub Actions
- **User:** Matous Kozak
- **Architecture:** fetch_issues.py → scan.json → build_reports.py → HTML reports → build_index.py → index.html
- **Scoring:** Urgency (0-10), Staleness (0-10), Neglect (0-10) — each with weighted signal components
- **Reports:** needs-attention.html, unattended.html, stale.html, all.html
- **Deployment:** GitHub Pages via GitHub Actions (every 6 hours)
- **Key UX:** Sortable/resizable tables, severity color coding, score tooltip breakdowns, sparklines

## Learnings

- **No Jinja2:** Replaced Jinja2 template engine with pure Python f-string rendering in `html_template.py`. Zero external deps.
- **Report path convention:** Reports live in `docs/{repo}/` (e.g. `docs/runtime/needs-attention.html`). Shared assets at `docs/` root, linked via `../shared-styles.css`.
- **Score severity mapping:** `severity-{round(score)}` classes, 0-10 scale mapped to green→red CSS variables.
- **Tooltip pattern:** Breakdown data stored in issue dict as `{score_type}_breakdown` list of `{name, raw, weight, value}` dicts. Rendered as tree-style text in monospace tooltip.
- **meta.json:** Written by CLI alongside reports. Contains `counts` dict and `generated_at`. Consumed by `index.html` for nav badges and timestamp.
- **index.html:** Fetches `repos.json` + per-repo `meta.json` at runtime. Shows sparklines if `meta.history` exists.
- **Column widths persisted:** `shared-ui.js` saves to localStorage keyed by report type.
- **Key files:**
  - `scripts/html_template.py` — render_report() API + CLI entry point
  - `docs/shared-styles.css` — CSS variables, severity scale, dark mode
  - `docs/shared-ui.js` — sort, resize, filter, tooltips, keyboard nav
  - `docs/index.html` — landing page, reads repos.json + meta.json
  - `docs/repos.json` — monitored repos config

## Cross-Team Impact (Wave 1)

- **McManus (Backend):** Delivers `scan.json` schema with score breakdowns. Fenster templates consume this directly.
- **Hockney (Tester):** Tests validate breakdown structure matches spec. Fenster rendering depends on accurate data.
- **Keaton (Lead):** Orchestrates render pipeline. HTML output staged to GitHub Pages.
- **Decision:** Pure Python f-string rendering adopted (no Jinja2) — noted in team decisions.md.
