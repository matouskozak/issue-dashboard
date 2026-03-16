# Issue Dashboard v2

Automated dashboard for tracking **Known Build Error** (KBE) issues in `dotnet/runtime`. Fetches issue data via GitHub GraphQL API, scores issues by urgency/staleness/neglect, and generates an interactive HTML dashboard published via GitHub Pages.

## Pipeline

```
fetch_issues.py → scan.json → build_reports.py → HTML reports + meta.json + history.json → build_index.py → verify index
```

Runs every 6 hours via GitHub Actions (`generate-reports.yml`).

## Project Structure

```
issue-dashboard-v2/
├── scripts/
│   ├── fetch_issues.py       # Fetch KBE issues from GitHub GraphQL API
│   ├── build_reports.py      # Generate HTML reports + meta.json + history.json
│   ├── build_index.py        # Verify dashboard index data
│   ├── regen_html.py         # Dev convenience: regenerate HTML from cached data
│   └── html_template.py      # HTML report template engine
├── docs/
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

GitHub Actions (`generate-reports.yml`) runs every 6 hours:
1. Fetches KBE issues from dotnet/runtime
2. Builds HTML reports + metadata
3. Commits generated files to `docs/`
4. Served via GitHub Pages

## License

MIT
