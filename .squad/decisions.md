# Squad Decisions

## Active Decisions

### 1. Use `uv` for Python Environment Management

**By:** Matous Kozak (via Copilot)  
**Date:** 2026-03-16T11:40Z  
**What:** Use `uv` for virtual environment creation and Python dependency management instead of pip.  
**Why:** User directive — captured for team memory and consistency across all agents.  
**Impact:** All Python workflows (fetch_issues, html_template, testing) use `uv`.

---

### 2. scan.json Schema and Scoring API

**By:** McManus  
**Date:** 2026-03-16  
**Affects:** Fenster (HTML templates consume scan.json), Hockney (tests validate scoring), Keaton (architecture)

**What:** `scan.json` output schema is finalized. Each issue object contains:
- Flat fields: `number`, `title`, `url`, `state`, `created_at`, `updated_at`, `author`, `assignees[]`, `labels[]`, `area_label`, `comment_count`, `human_comment_count`, `last_human_comment_date`, `last_human_comment_author`, `reactions_count`, `hits_24h`, `hits_7d`, `hits_30d`, `error_pattern`, `build_link`, `has_blocking_label`, `has_untriaged_label`
- Score fields: `urgency_score`, `staleness_score`, `neglect_score` (all 0–10 floats)
- Breakdown dicts: `urgency_breakdown`, `staleness_breakdown`, `neglect_breakdown` — each maps signal name → `{value, weight, contribution}`

Top-level: `repo`, `org`, `generated_at`, `issue_count`, `issues[]`.

**Why:** Downstream consumers (build_reports.py, HTML templates) need a stable contract. Score breakdowns enable the UI to show *why* an issue is scored a certain way.

**Impact:**
- **Fenster:** Can now build templates that read `scan.json` fields. Score breakdowns available for tooltip/detail views.
- **Hockney:** Can write unit tests against the scoring functions (importable from `scripts/fetch_issues.py`).
- **Usage:** `python scripts/fetch_issues.py runtime` → outputs `docs/runtime/scan.json`.

---

### 3. No Jinja2 — Pure Python Templates

**By:** Fenster  
**Date:** 2026-03-16

**Context:** The original `html_template.py` stub used Jinja2 for rendering. The task spec explicitly requires no external template deps.

**Decision:** Replaced Jinja2 with Python f-string based rendering. `render_report()` builds the full HTML string using internal helper functions. Zero pip dependencies for the template engine.

**Impact:**
- **McManus / pipeline scripts:** `render_report()` API signature changed. New signature: `render_report(report_type, issues, repo, generated_at, meta=None) -> str`. Returns HTML string (no longer writes to disk).
- **CLI usage:** `python scripts/html_template.py <scan.json> <output_dir> [repo]` generates all 4 reports + `meta.json`.
- **Keaton / scoring:** Score breakdowns expected as `{score_type}_breakdown` list in each issue dict. Format: `[{name, raw, weight, value}, ...]`.
- **Report asset paths:** Reports at `docs/{repo}/*.html` reference shared assets via `../shared-styles.css` and `../shared-ui.js`.

### 4. Two Spec Deviations Found in fetch_issues.py

**By:** Hockney (Tester)  
**Date:** 2026-03-16

**What:** During testing, identified two places where McManus's implementation diverges from spec:

1. **Hit Trend 7d==0 + 24h>0 edge case** — Spec says 1.0, implementation returns 0.0
2. **Comma-separated hit counts** — Spec expects `|1,234|5,678|`, regex only captures `1`

**Why:** Ensures test clarity and marks known issues explicitly.

**Impact:**
- Both marked `@pytest.mark.xfail(strict=True)` — fail loudly if fixed without tests
- McManus to decide: fix implementation or update spec

---

### 5. Delete build-dashboard.yml, Keep generate-reports.yml

**By:** McManus  
**Date:** 2026-03-16

**What:** Deleted stale `build-dashboard.yml`. Two workflows existed:
- `generate-reports.yml` — real pipeline (fetch → build_reports → build_index, every 6h)
- `build-dashboard.yml` — v1 orphan (broken paths, stale scripts)

**Why:** One pipeline, one workflow. Single source of truth.

**Impact:** No functional change; `build-dashboard.yml` would fail on every run.

---

## Governance

- All meaningful changes require team consensus
- Document architectural decisions here
- Keep history focused on work, decisions focused on direction
