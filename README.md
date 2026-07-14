# RHOAI Customer Profiles Dashboard

Generates interactive HTML reports showing Red Hat OpenShift AI (RHOAI) customer adoption from Amplitude product analytics data.

## What It Shows

For each RHOAI customer on a connected cluster:

- **Adoption stage** — Scaling, Established, Expanding, Exploring, Reduced Visibility, Churned, or Migrated (based on 12-month usage trajectory)
- **Feature usage** — which RHOAI features are actively used (Workbenches, Model Serving, Pipelines, Playground, RBAC, etc.) and which are not
- **12-month sparkline** — monthly activity trend with weekday-normalized bars
- **Serving runtimes & models** — which models customers deploy (vLLM, OpenVINO, Caikit, custom)
- **Workbench images** — which ML frameworks are in use (PyTorch, TensorFlow, CUDA)
- **RHOAI version** — actual product version from OCM telemetry
- **POC detection** — identifies customers in proof-of-concept vs production use
- **Migration detection** — flags customers who moved from connected to disconnected clusters

The report is a single self-contained HTML file — no server needed, share via email or Slack.

## Quick Start

### 1. Install Python and uv

You need Python 3.11+ and [uv](https://docs.astral.sh/uv/getting-started/installation/):

```bash
# Install uv (if you don't have it)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone this repo

```bash
git clone https://github.com/dcohnlif/rhoai-amplitude-dashboard.git
cd rhoai-amplitude-dashboard
```

### 3. Install dependencies

```bash
uv sync
```

### 4. Set up your API keys

Copy the example env file and add your Amplitude credentials:

```bash
cp .env.example .env
```

Edit `.env` and replace the placeholder values with your real API keys:

```
export AMPLITUDE_API_KEY="your_api_key_here"
export AMPLITUDE_SECRET_KEY="your_secret_key_here"
```

**Where to get the keys**: Ask your Amplitude project Manager to generate them from Amplitude > Organization Settings > API Keys > select "RHODS Instances".

### 5. Generate historical data (first time only)

This fetches 12 months of monthly usage data for trajectory analysis:

```bash
source .env
uv run python main.py backfill
```

This takes ~30 seconds and creates `data/amplitude/historical_backfill.json`. Re-run quarterly to refresh.

### 6. Generate the report

```bash
source .env
uv run python main.py report --open
```

This queries Amplitude (takes ~3 minutes), generates the HTML report, and opens it in your browser.

## Commands

| Command | What it does |
|---------|-------------|
| `python main.py report --open` | Generate the HTML report and open in browser |
| `python main.py report --days 90` | Report with 90-day data window (default: 30) |
| `python main.py report --min-events 50` | Only include customers with 50+ events |
| `python main.py report --output my-report.html` | Custom output filename |
| `python main.py list` | List all RHOAI customers with user/event counts |
| `python main.py list --days 90 --limit 100` | List top 100 customers from last 90 days |
| `python main.py backfill` | Fetch 12-month historical data for trajectory analysis |
| `python main.py backfill --months 6` | Fetch 6 months instead of 12 |

## Report Features

### Adoption Stages

Customers are classified using **current usage level + 12-month trajectory** (direction of change):

| Stage | Criteria |
|-------|---------|
| **Scaling** | 1000+ events/month, growing or stable trend |
| **Established** | 100+ events/month, stable trend |
| **Expanding** | 100+ events/month, growing trend (>50% increase) |
| **Exploring** | <100 events/month, or new customer |
| **Reduced Visibility** | >50% telemetry drop — usually telemetry opt-out or move to disconnected, NOT reduced RHOAI usage |
| **Churned** | Was active, recent months are zero |
| **Migrated** | Telemetry declining but still filing support cases — confirmed move to disconnected clusters |

> **Important**: "Reduced Visibility" does NOT mean the customer stopped using RHOAI. Per the Customer Adoption Innovation team, ~99% of telemetry drops are caused by telemetry opt-out, move to disconnected environments, or production clusters without telemetry enabled.

### Feature Categories (12)

Workbenches, Model Serving, Data Science Pipelines, Model Registry, RBAC, Available Endpoints, Evaluations, Playground, Guardrails, Model Catalog, Projects, Application.

### Interactive Features

- **Search** — filter customers by name or feature
- **Stage filters** — click Scaling, Established, etc. to filter
- **Hover tooltips** — hover over any stage badge to see WHY that customer got that classification
- **Sparkline hover** — hover over monthly bars to see raw + normalized event counts
- **Expandable details** — click "▸ Details" to see serving runtimes, workbench images, RHOAI version

## Configuration

### `config/amplitude_account_mapping.yaml`

Maps Amplitude org_names to your internal customer IDs. Used for cross-referencing with Jira/support case data.

### `config/amplitude_blocklist.yaml`

Individual developer accounts (not real customers) to exclude from the report.

## Development

```bash
# Install dev dependencies
uv sync --extra dev

# Run tests
uv run pytest

# Format code
uv run ruff format .

# Lint
uv run ruff check .
```

## Data Sources

| Source | What it provides |
|--------|----------------|
| **Amplitude Event Segmentation API** | Customer list, feature usage counts, unique users |
| **Amplitude Property Breakdown API** | Serving runtimes, workbench images per customer |
| **OCM Lookup Table (via Amplitude)** | org_name, RHOAI version, ebs_account_number |
| **Historical backfill** (local JSON) | 12-month monthly event/user counts for trajectory |

## License

Apache-2.0
