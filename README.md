# Issue Dashboard

Automated dashboard for tracking **Known Build Error** (KBE) issues in `dotnet/runtime`. Fetches issue data via GitHub GraphQL API, scores issues by urgency/staleness/neglect, and generates an interactive HTML dashboard published via GitHub Pages.

## **[Issue Dashboard](https://matouskozak.github.io/issue-dashboard/)**

## **[PR Dashboard](https://danmoseley.github.io/pr-dashboard/)**

## Pipeline

```
fetch_issues.py → scan.json → build_reports.py → HTML reports + meta.json + history.json → build_index.py → verify index
```

Runs every hour via GitHub Actions (`generate-reports.yml`).

## Project Structure

```
issue-dashboard-v2/
├── scripts/
│   ├── fetch_issues.py       # Fetch KBE issues from GitHub GraphQL API
│   ├── build_reports.py      # Generate HTML reports + meta.json + history.json
│   ├── build_index.py        # Verify dashboard index data
│   ├── notify_high_impact.py # Create high impact mono/mobile alerts
│   ├── regen_html.py         # Dev convenience: regenerate HTML from cached data
│   └── html_template.py      # HTML report template engine
├── pages/
│   ├── index.html            # Dashboard landing page (loads data dynamically)
│   ├── repos.json            # Repo configuration
│   ├── shared-styles.css     # Shared CSS
│   ├── shared-ui.js          # Shared JS (sorting, filtering, sparklines)
│   └── runtime/
│       ├── scan.json          # Raw issue data (generated)
│       ├── meta.json          # Summary stats (generated)
│       ├── history.json       # Trend data (generated)
│       ├── needs-attention.html
│       ├── unattended.html
│       ├── stale.html
│       └── all.html
├── tests/
│   └── test_*.py             # Unit tests
├── pyproject.toml            # Python project config (uv)
└── .github/workflows/
    └── generate-reports.yml  # GitHub Actions pipeline
```

## Setup

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- GitHub personal access token

### Local Development

```bash
git clone https://github.com/your-org/issue-dashboard-v2.git
cd issue-dashboard-v2
uv sync
export GITHUB_TOKEN=your_token

# Full pipeline
uv run python scripts/fetch_issues.py runtime
uv run python scripts/build_reports.py runtime
uv run python scripts/build_index.py

# Regenerate HTML from cached data (skip fetch)
uv run python scripts/regen_html.py runtime
```

### Running Tests

```bash
uv sync --group dev
uv run pytest tests/
```

## Reports

| Report | Description |
|--------|-------------|
| **Needs Attention** | All issues, sorted by urgency score (highest first) |
| **Unattended** | Issues with neglect score > 5.0 |
| **Stale** | Issues with staleness score > 5.0 |
| **All** | All open KBE issues, sorted by issue number |

## Deployment

GitHub Actions (`generate-reports.yml`) runs every hour:
1. Fetches KBE issues from dotnet/runtime
2. Builds HTML reports + metadata
3. Commits generated files to `pages/`
4. Deployed via GitHub Pages (Actions deployment)

## High Impact Alerts

After a successful scan on the default branch, a separate job checks open KBE
issues with **at least 7 failures in 24 hours**. It uses the dashboard's existing
mono/mobile label filter: mono, Android, iOS, tvOS, and MacCatalyst. Issues with
wasm, browser, or WASI labels are excluded, even if they also have mobile labels.
Counts come from the source issue's KBE summary, not directly from CI runs.

Each qualifying source issue gets an alert in `matouskozak/issue-dashboard`,
assigned to `matouskozak`. The source issue in `dotnet/runtime` is not changed.
Source links use `redirect.github.com` to avoid backlinks in the source issue's
timeline. There are no repeat alerts while an alert is open. If a qualifying
open alert loses its assignment, the job restores it on the same issue and
verifies the result. Other assignees and notes are kept. A failed repair remains
an error on later runs; it does not create a duplicate alert.

**Close an alert to pause notifications for that source issue for 7 days.**
The pause starts at the closure time in UTC. After the pause, the next successful
hourly check creates a **new issue** if the count is still at least 7. If the count
is lower, it waits until the threshold is reached again. The old alert stays
closed. Keep the hidden source marker in alert bodies; it links each alert to its
source and prevents duplicates.
Only alerts created by `github-actions[bot]` control this history. Copies of a
marker in issues from other authors cannot stop notifications or start a pause.

The job uses the repository `GITHUB_TOKEN` with `contents: read` and
`issues: write`. No personal token is needed in Actions. Alert errors fail the
notification job but do not block dashboard deployment. GitHub notification
settings control email delivery.

To preview actions locally, set `GITHUB_TOKEN` for read access to alert history:

```bash
uv run python -m scripts.notify_high_impact pages/runtime/scan.json \
  --target-repo matouskozak/issue-dashboard --assignee matouskozak \
  --threshold 7 --dry-run
```

The preview reads the saved scan and makes no GitHub writes. It prints proposed
issue content for eligible alerts and logs open or paused alerts. If no source
issues meet the threshold, it makes no API requests. Missing assignments are
reported in the preview, but are not changed.

## License

MIT
