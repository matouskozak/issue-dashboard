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

- **Score Guide section:** Added collapsible `<details>` "Score Guide" between stats bar and filter/table in every report. Implemented via `_render_score_guide()` in `scripts/html_template.py`, with a new `{score_guide}` placeholder in `_PAGE_TEMPLATE`. CSS in `pages/shared-styles.css` (`.score-guide*` rules). Uses a 3-card grid explaining Urgency, Neglect, and Staleness scores — what they measure, their input signals, and interpretation hints.
- **Actual asset path:** Shared assets live in `pages/` not `docs/` (e.g. `pages/shared-styles.css`). History references to `docs/` are legacy naming.
- **Mobile filter toggle:** Added a "Hide mobile/mono/wasm issues" checkbox to the filter bar. Python-side: `_is_mobile_issue()` helper in `html_template.py` checks labels against a known set of mobile-related labels (exact matches + keyword substring matching). Adds `data-mobile="true"` attribute to `<tr>` elements. JS-side: `initMobileFilter()` in `pages/shared-ui.js` reads/persists toggle state via localStorage key `kbe-hide-mobile`. Unified `applyFilters()` function ensures text filter and mobile filter compose correctly. CSS: `.mobile-filter-toggle` styled inline with the filter bar in `pages/shared-styles.css`.

## Cross-Team Impact (Wave 1)

- **McManus (Backend):** Delivers `scan.json` schema with score breakdowns. Fenster templates consume this directly.
- **Hockney (Tester):** Tests validate breakdown structure matches spec. Fenster rendering depends on accurate data.
- **Keaton (Lead):** Orchestrates render pipeline. HTML output staged to GitHub Pages.
- **Decision:** Pure Python f-string rendering adopted (no Jinja2) — noted in team decisions.md.

## Wave 2: Agents 19–20 (2026-03-16T1900Z)

**Agent 19 Task:** Add collapsible Score Guide section to HTML reports.

**Implementation:**
- `scripts/html_template.py`: Added `_render_score_guide()` function and `{score_guide}` placeholder in `_PAGE_TEMPLATE`
- `pages/shared-styles.css`: Added `.score-guide*` styling for collapsible `<details>` element
- Content explains Urgency, Neglect, and Staleness scores with 3-card grid layout

**Impact:** Users can toggle visibility to understand scoring methodology without cluttering report.

---

**Agent 20 Task:** Add mobile/mono/wasm issue filter toggle with localStorage persistence.

**Implementation:**
- `scripts/html_template.py`: Added `_is_mobile_issue()` function with two-tier label detection (exact matches + keyword substring). Sets `data-mobile="true"` on `<tr>` elements.
- `pages/shared-ui.js`: Added `initMobileFilter()` with checkbox event handler and localStorage key `kbe-hide-mobile` for persistence.
- `pages/shared-styles.css`: Styled `.mobile-filter-toggle` toggle inline with filter bar, hidden rows via `display: none`.

**Label strategy:**
- **Exact matches:** area-infrastructure-mono, arch-wasm, os-android, os-ios, os-tvos, os-maccatalyst, os-browser
- **Substring keywords:** android, ios, wasm, browser, mono, maccatalyst, tvos

**Impact:** Users can hide mobile/mono/wasm issues. Preference persists across page reloads via localStorage.
