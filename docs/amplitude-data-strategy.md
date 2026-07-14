# Amplitude Data Strategy — What, Why, and How

**Date**: June 16, 2026
**Ticket**: AIPCC-18285
**Status**: API access confirmed, implementation in progress

## Executive Summary

Amplitude tracks UI-level behavioral data from RHOAI dashboards on **connected** clusters. Our existing Jira/support case pipeline covers primarily **disconnected** customers. These are two largely separate populations.

Amplitude gives us three things we don't have today:
1. **Scale** — how many active users per customer, how often they use each feature
2. **Negative evidence** — which features customers do NOT use (impossible to infer from complaints)
3. **Workflow sequences** — the order in which users perform actions (journey paths)

### Critical Data Limitation: Telemetry Declining ≠ Product Declining

Per Cansu Cavili Oernek (Customer Adoption Innovation team, July 2026):

> "99% of the time, they either opt out sending the telemetry data or just in a disconnected env. The number of customers sending telemetry data from their actual prod clusters is quite low. Majority of the names here are providers (Cisco, Dell, Verizon, Wipro) so there is a chance that they are doing PoCs in connected environments and then move to the disconnected env."

**A decline in Amplitude data does NOT mean the customer stopped using RHOAI.** Common reasons for telemetry drops:
- Customer opted out of telemetry (privacy/security policy)
- Customer moved from connected POC cluster to disconnected production
- Production clusters have telemetry disabled by default
- Providers (SI/resellers) finish POC on connected cluster, deploy for end customer on disconnected

The report uses "Reduced Visibility" instead of "Declining" to reflect this — and the "Migrated" stage specifically flags customers whose telemetry dropped but who are still filing support cases.

We have working API access (API Key + Secret Key) and an authenticated MCP connection for interactive exploration.

---

## Part 1: What Data Is Available

### Two Amplitude Projects

| Project | App ID | Data Source | What it contains |
|---------|--------|------------|-----------------|
| **RHODS Instances** | `418474` | RHOAI dashboard JavaScript events (via Segment) | UI clicks: workbench ops, model deploy, pipeline runs, playground queries |
| **RHOAI Events** | `627029` | Custom events synced from RedShift | Enriched events: operator detection, usage detection, marketing interactions, trials, journey paths |

Both share the same customer identification via the **cluster-to-account lookup table** (lookup property ID `10895`): `clusterId → org_name, ebs_id, org_id`.

### Event Inventory

**173+ tracked events** across these categories:

| Category | Example Events | Value for Us |
|----------|---------------|-------------|
| **Workbenches** | Workbench Created, Opened, Started, Stopped, Updated | Core usage — every data scientist uses these |
| **Model Serving** | Model Deployed, Deleted, Updated, Model Server Added/Deleted | Production readiness indicator |
| **Pipelines** | Pipeline Imported, Run Triggered, Archived, Scheduled, Server Configured | ML automation maturity |
| **Model Registry** | Model Registered, Registry Created, Version management | MLOps maturity |
| **GenAI Playground** | Playground Query Submitted, RAG Upload, MCP Tools, Model Comparison | GenAI adoption |
| **Evaluations** | LM-Eval runs, MLflow experiments | Model quality practices |
| **RBAC** | Role management, permission changes | Enterprise governance |
| **Operator Detection** | GPU, RHOAI, Lightspeed, Watsonx, OpenDataHub detected | Infrastructure profile |
| **Usage Detection** | Workbench, Model Deployment, Pipelines usage detected | High-level feature presence |
| **Trials** | 30-day sandbox trial, 60-day product trial started | POC identification |
| **Marketing** | Page views, event attendance, collateral downloads | Pre-purchase engagement |

### Rich Event Properties

The `Workbench Created` event alone carries 17 properties:

| Property | What it reveals |
|----------|----------------|
| `notebookName` | What the data scientist is working on (e.g., "fraud-detection-model") |
| `imageName` | Which ML framework (PyTorch, TensorFlow, CUDA, Standard Data Science) |
| `projectName` | Which RHOAI project — can indicate team/department structure |
| `accelerator` | GPU type requested |
| `acceleratorCount` | GPU count — indicates workload scale |
| `lastSelectedSize` | Hardware profile — small experiment vs heavy training |
| `dataConnectionEnabled` | Whether external data (S3) is used |
| `storageType` / `storageDataSize` | Storage architecture |
| `outcome` | submit vs cancel — did they complete the wizard? |
| `success` | Did the creation actually succeed? |

Similar properties exist on `Model Deployed` (runtime, framework, model name) and `Pipeline Imported` (pipeline structure).

---

## Part 2: What We Can Learn

### 2.1 Customer Maturity Classification

Using Amplitude signals, classify each customer into maturity stages:

| Stage | Signals | Amplitude Indicators |
|-------|---------|---------------------|
| **Evaluating** | Trial started, low activity, few users | `Trial Started` events present, <5 users, <100 events/month |
| **Developing** | Active workbenches, no production serving | `Workbench Opened` high, `Model Deployed` = 0, 5-20 users |
| **Deploying** | Models being served, some pipelines | `Model Deployed` > 0, `Pipeline Run Triggered` occasional, 10-50 users |
| **Operating** | Full ML lifecycle, many users, daily activity | All feature categories active, 50+ users, consistent month-over-month |
| **Churned/Dormant** | Was active, now silent | Historical events present, last 30 days = 0 |

### 2.2 Prod vs Non-Prod Environment Detection

Cluster names aren't directly in Amplitude (only UUIDs), but we can infer environment type from behavioral signals:

| Signal | Prod indicator | Non-prod indicator |
|--------|---------------|-------------------|
| `Model Deployed` count | High, steady | Sporadic, experimental |
| Workbench Create/Open ratio | Low creates, high opens (established) | High creates, low opens (experimenting) |
| User count | Many users (team usage) | 1-3 users (individual exploration) |
| `Pipeline Run Triggered` | Scheduled, regular | Manual, irregular |
| `outcome: cancel` rate | Low (users know what to do) | High (users exploring the UI) |

**Better path**: Ask Heiko if the OCM lookup table includes cluster `display_name` or `managed` flag. Many customers name clusters like `prod-rhoai-01`, `dev-ml-cluster`. This would give definitive prod/non-prod classification.

### 2.3 What Data Scientists Are Building

From `notebookName` and `imageName` on `Workbench Created` events:

- **Workbench names** reveal use cases: "fraud-detection", "nlp-pipeline", "customer-churn", "recommendation-engine"
- **Image names** reveal ML frameworks: PyTorch → deep learning, TensorFlow → established ML, CUDA → GPU-heavy training, Standard Data Science → general analytics
- **Project names** reveal organizational structure: team names, department codes, project codenames

This lets us build a **use-case taxonomy** — not just "Customer X uses Workbenches" but "Customer X uses PyTorch workbenches for fraud detection models".

### 2.4 POC vs Daily Use Classification

| Metric | POC | Daily Use |
|--------|-----|-----------|
| Unique users (30d) | 1-3 | 10+ |
| Total events (30d) | <100 | 500+ |
| Workbench Open/Create ratio | <5 (few reuses) | >20 (heavily reused) |
| Month-over-month trend | Declining or flat | Stable or growing |
| Trial events present | Yes | No (or long ago) |
| Model Deployed | 0-2 | 5+ |
| Days with activity | <5 per month | 15+ per month |

### 2.5 Cross-Source Customer Profile

For customers appearing in **both** Jira and Amplitude:

| Dimension | Jira gives us | Amplitude gives us | Combined insight |
|-----------|--------------|-------------------|-----------------|
| Features used | Inferred from complaints | Directly observed | Confirm or contradict Jira inferences |
| Scale | Unknown | User count, event volume | "105 users open workbenches daily" |
| Problems | Bug reports, config issues | `success: false`, `outcome: cancel` rates | Problem frequency vs complaint frequency |
| Tech stack | Models, runtimes, GPUs (from case text) | Images, accelerators, storage (from events) | Complete ML stack picture |
| Maturity | Version history, case sophistication | Feature breadth, user growth trend | Lifecycle stage classification |
| Workflow | Pattern co-occurrence | Event sequences (journey paths) | "They use A then B" not just "they use A and B" |

### 2.6 Amplitude vs OCP Telemetry — Do We Still Need Telemetry?

| Need | Amplitude covers it? | OCP Telemetry needed? |
|------|---------------------|----------------------|
| Feature usage | **Yes** — the primary signal | No |
| User counts | **Yes** | Redundant |
| RHOAI version | **Yes** (`version` user property) | Redundant |
| GPU presence | **Yes** (`Operator Detected - GPU`, `accelerator` property) | Redundant |
| GPU model/vendor (H100 vs T4 vs A100) | **No** — only presence | **Yes** — specific models |
| Cluster CPU/memory capacity | **No** | **Yes** |
| Node instance types (cloud VM sizes) | **No** | **Yes** |
| Cloud provider (AWS/GCP/Azure/bare metal) | **No** | **Yes** |
| Disconnected cluster data | **No** — connected only | **No** — connected only |

**Recommendation**: Focus on Amplitude (AIPCC-18285) for customer behavioral data. Deprioritize OCP telemetry (AIPCC-8709) — it adds infrastructure-level details (GPU models, cluster sizing) that are useful but lower priority than understanding what customers actually do.

---

## Part 3: How to Fetch During Sync

### 3.1 Architecture

Amplitude sync runs as a **separate weekly CI job**, not embedded in the Jira sync pipeline:

```
┌──────────────────────────────────────────────────┐
│  CI Job: amplitude-sync (weekly)                 │
│                                                   │
│  1. Authenticate (API Key + Secret Key)           │
│  2. Fetch customer list (org_name, users, events) │
│  3. Fetch feature usage per customer              │
│  4. Fetch workbench details (names, images)       │
│  5. Classify: maturity stage, POC vs daily use    │
│  6. Match to existing Jira customers              │
│  7. Enrich usage profiles                         │
│  8. Save amplitude.json per customer              │
│  9. Push to S3                                    │
└──────────────────────────────────────────────────┘
```

### 3.2 API Access

| Parameter | Value |
|-----------|-------|
| **API endpoint** | `https://amplitude.com/api/2/events/segmentation` |
| **Auth** | HTTP Basic with `AMPLITUDE_API_KEY:AMPLITUDE_SECRET_KEY` |
| **Project** | RHODS Instances (`418474`) for UI events |
| **Customer grouping** | Lookup property `10895` (`org_name`) |
| **Rate limit** | 360 requests/hour; 0.5s sleep between requests |
| **CI variables** | `AMPLITUDE_API_KEY`, `AMPLITUDE_SECRET_KEY` (masked) |

### 3.3 Queries to Run During Sync

**Query 1: Customer list with user counts and total events**
```
GET /api/2/events/segmentation
  e={"event_type":"_all", "group_by":[{"type":"lookup","value":"10895"}],
     "filters":[exclude Red Hat internal]}
  m=uniques (then totals in second call)
  start=YYYYMMDD  end=YYYYMMDD  i={days}
```

**Query 2: Feature usage per customer** (one call per tracked event)
```
For each of: Workbench Opened, Workbench Created, Model Deployed,
             Pipeline Run Triggered, Model Registered,
             Playground Query Submitted, NewProject Created, ...

GET /api/2/events/segmentation
  e={"event_type":"<event>", "group_by":[{"type":"lookup","value":"10895"}],
     "filters":[exclude internal]}
  m=totals
```

**Query 3: Workbench details** (names and images per customer)
```
GET /api/2/events/segmentation
  e={"event_type":"Workbench Created",
     "group_by":[{"type":"lookup","value":"10895"},
                 {"type":"event","value":"notebookName"},
                 {"type":"event","value":"imageName"}],
     "filters":[exclude internal]}
  m=totals
```

**Query 4: Trial/POC detection**
```
GET /api/2/events/segmentation
  e={"event_type":"Trial Started - 60 Day Product Trial of Red Hat OpenShift AI",
     "group_by":[{"type":"lookup","value":"10895"}]}
  m=uniques
```

### 3.4 Output Per Customer

Saved to `data/customers/{id}/amplitude.json` (for matched customers) or `data/amplitude/{normalized_name}.json` (for unmatched):

```json
{
  "org_name": "TURK HAVA YOLLARI ANONIM ORTAKLIGI",
  "ebs_id": null,
  "unique_users": 103,
  "total_events": 4262,
  "feature_counts": {
    "Workbench Opened": 997,
    "Workbench Created": 26,
    "Model Deployed": 29,
    "Pipeline Run Triggered": 0,
    "Playground Query Submitted": 0,
    "NewProject Created": 5,
    "Model Registered": 0
  },
  "workbench_details": [
    {"name": "fraud-detection-model", "image": "PyTorch", "count": 3},
    {"name": "llm-experiments", "image": "CUDA", "count": 1}
  ],
  "classification": {
    "maturity_stage": "deploying",
    "is_poc": false,
    "daily_use": true,
    "active_features": ["Workbenches", "Model Serving", "Projects"],
    "inactive_features": ["Data Science Pipelines", "Model Registry", "GenAI Playground"]
  },
  "fetched_at": "2026-06-16T12:00:00",
  "period_days": 30,
  "period_start": "2026-05-17",
  "period_end": "2026-06-16"
}
```

### 3.5 Usage Profile Enrichment

For customers matched to existing Jira customers, enrich `usage_profile.json`:

**Fill existing null fields:**
- `components_enabled` ← from `active_features`
- `using_model_registry` ← `true` if `Model Registered > 0`, `false` if `0`
- `registered_models_count` ← from `Model Registered` count

**Add new `amplitude` section:**
```json
{
  "amplitude": {
    "unique_users": 103,
    "total_events": 4262,
    "feature_counts": {"Workbench Opened": 997, ...},
    "active_features": ["Workbenches", "Model Serving"],
    "inactive_features": ["Pipelines", "Model Registry", "Playground"],
    "maturity_stage": "deploying",
    "is_daily_use": true,
    "workbench_images": ["PyTorch", "CUDA", "Standard Data Science"],
    "period_start": "2026-05-17",
    "period_end": "2026-06-16",
    "fetched_at": "2026-06-16T12:00:00"
  }
}
```

**Rule**: Amplitude can fill nulls and confirm existing values, but never downgrades a `true` to `false`. The 30-day window is too short to conclude a feature isn't used — Jira may reflect historical usage outside Amplitude's window.

### 3.6 Pattern Occurrence Creation

For features above threshold, create `UsagePatternOccurrence` entries:

| Amplitude Event | Pattern Component | Min Threshold | Evidence |
|----------------|-------------------|---------------|----------|
| Workbench Opened | Workbenches | 5 events | high |
| Model Deployed | Model Serving | 1 event | high |
| Pipeline Run Triggered | Data Science Pipelines | 1 event | high |
| Model Registered | Model Registry | 1 event | high |
| Playground Query Submitted | LLM Serving | 3 events | medium |

Occurrence metadata:
- `source_type = SourceType.AMPLITUDE`
- `issue_key = f"amplitude:{period_start}:{period_end}"` (enables period-keyed upsert)
- `evidence_strength` = scaled from event count
- `usage_status = "in_use"` (direct observation, not inference)

### 3.7 CI Job Configuration

```yaml
amplitude-sync:
  stage: sync
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"    # weekly
    - if: $CI_PIPELINE_SOURCE == "web"         # manual trigger
  resource_group: workflow-insights-data
  script:
    - |
      if [ -z "$AMPLITUDE_API_KEY" ] || [ -z "$AMPLITUDE_SECRET_KEY" ]; then
        echo "WARNING: Amplitude credentials not configured, skipping"
        exit 0
      fi
    - uv run python main.py data pull --customers --library
    - uv run python main.py amplitude sync --min-events 10
    - uv run python main.py data push --customers
  allow_failure: true
```

### 3.8 What We Do NOT Change

- **Existing user journeys are immutable** — Amplitude data does not modify journey specs, pattern assignments, or registry entries
- **Existing Jira-sourced patterns and occurrences are preserved** — Amplitude adds new occurrences, never modifies or deletes existing ones
- **Additive-only** — consistent with sync design principles

---

## Part 4: Implementation Phases

### Phase 1: Foundation (done)
- [x] Amplitude API client (`src/extractors/amplitude_client.py`)
- [x] Data models (`src/models/amplitude.py`)
- [x] Event-to-pattern mapper (`src/extractors/amplitude_mapper.py`)
- [x] CLI commands: `amplitude sync`, `amplitude list`
- [x] SourceType.AMPLITUDE enum value
- [x] CustomerMetadata.amplitude_org_name field
- [x] Unit tests (28 tests passing)
- [x] .env.example documentation

### Phase 2: Workbench Deep Dive (next)
- [ ] Query workbench names and images per customer
- [ ] Parse workbench names to extract use-case keywords
- [ ] Add workbench details to AmplitudeProfile model
- [ ] Store in amplitude.json

### Phase 3: Customer Classification
- [ ] Implement POC vs daily-use classifier from Amplitude signals
- [ ] Implement maturity stage classifier (evaluating → developing → deploying → operating)
- [ ] Add classification fields to amplitude.json

### Phase 4: Cross-Source Integration
- [ ] Match Amplitude org_name to Jira customer_id (by ebs_id or fuzzy name)
- [ ] Enrich usage_profile.json with Amplitude data (fill nulls + add section)
- [ ] Generate pattern occurrences from Amplitude feature usage
- [ ] Build overlap report: which customers appear in both sources

### Phase 5: CI Automation
- [ ] Add amplitude-sync job to .gitlab-ci.yml
- [ ] Add Amplitude section to sync report
- [ ] Add Amplitude data to web UI customer tab

### Phase 6: Advanced Analytics (future)
- [ ] Query RHOAI Events project (627029) for journey paths
- [ ] Analyze journey sequences to validate our journey specs
- [ ] Investigate prod/non-prod classification via OCM cluster display names
- [ ] Compare trial→conversion rates across customer segments

---

## Part 5: Export API Deep Analysis (Option 3)

The Amplitude Export API (`GET /api/2/export`) downloads the complete raw event stream as gzipped JSON lines inside a ZIP archive. This gives us every event, every property, every user — enabling deep slicing that the Segmentation API can't do.

### What Each Raw Event Contains (55 fields)

| Field | Example | Intelligence Value |
|-------|---------|-------------------|
| `event_type` | `Workbench Created`, `Model Deployed` | What they did |
| `event_time` | `2026-06-16 00:15:15` | When |
| `event_properties.clusterID` | `ecf551dd-...` | Which cluster |
| `event_properties.url` | `rh-ai.apps.gbocpank3rdaiprod1.fw.garanti.com.tr` | **Cluster hostname → customer, prod/non-prod, cloud/on-prem, region** |
| `event_properties.notebookName` | `fraud-detection-model` | What data scientists build |
| `event_properties.imageName` | `pytorch`, `minimal-gpu` | ML framework |
| `event_properties.servingRuntimeName` | `vllm-cuda-runtime` | Serving runtime |
| `event_properties.projectName` | `pa-ai--runtime-int` | Project structure |
| `event_properties.containerResources` | `requests.cpu: 2, limits.nvidia.com/gpu: 2` | **Exact compute: CPU, memory, GPU count** |
| `event_properties.accelerator` | `NVIDIA GPU (4x80G - H100)` | **GPU model** |
| `event_properties.success` | `true/false` | Success/failure |
| `event_properties.outcome` | `submit/cancel` | Completed or abandoned |
| `user_properties.isAdmin` | `true/false` | Admin vs data scientist |
| `version_name` | `v3.4.0` | **RHOAI version** |
| `country` | `Canada` | Geographic location |
| `os_name` | `Mac OS` | Developer OS |

### Hostname Analysis — Prod vs Non-Prod

The `event_properties.url` field contains the full RHOAI dashboard URL. Cluster hostnames reveal:

- **Prod vs Non-Prod**: keywords `prod`, `npr`, `dev`, `staging`, `test` in hostname
- **Cloud provider**: `.openshiftapps.com` (ROSA/AWS), `.containers.appdomain.cloud` (IBM Cloud), `.gcp.` (GCP)
- **On-prem**: `.local`, `.internal`, custom TLDs (`.com.tr`, `.com.au`)
- **Customer identity**: `garanti.com.tr`, `westpac.com.au`, `nti.internal`
- **Region**: `eu-de`, `stc-ai-e1` (Saudi), `ocp.mx` (Mexico)

Examples observed:
- `data-science-gateway.apps.stc-ai-e1-prod.rtc9.p1.openshiftapps.com` → STC/Saudi Telecom, PROD, ROSA
- `data-science-gateway.apps.ocp-rcc-npr-isd-100.npr.ocp.srv.westpac.com.au` → Westpac Bank, NON-PROD, on-prem
- `rh-ai.apps.gbocpank3rdaiprod1.fw.garanti.com.tr` → Garanti Bank Turkey, PROD, on-prem

### Volume Estimate

| Period | Events | Compressed Size |
|--------|--------|----------------|
| 1 hour | ~800 | 120 KB |
| 1 day | ~19,000 | 3.3 MB |
| 30 days | ~570,000 | ~98 MB |
| 90 days | ~1.7M | ~293 MB |

### Export Pipeline Architecture

```
Step 1: Export (curl /api/2/export → ZIP of gzipped JSON lines)
    │
    ▼
Step 2: Parse & enrich each event
    │   - Extract clusterID → org_name via lookup table
    │   - Parse hostname → prod/non-prod, cloud/on-prem
    │   - Parse containerResources → CPU, memory, GPU
    │   - Classify user: admin vs data scientist
    │
    ▼
Step 3: Aggregate per customer
    │   - Feature usage counts
    │   - Serving runtimes (from runtime names)
    │   - Workbench images (PyTorch, TensorFlow, CUDA)
    │   - Workbench names → use-case keywords
    │   - GPU types and counts
    │   - RHOAI versions
    │   - Failure rates
    │   - Activity timeline
    │   - Maturity classification
    │
    ▼
Step 4: Output per-customer profile
        data/amplitude/{customer}/profile.json
```

### New Files for Export Pipeline

| File | Purpose |
|------|---------|
| `src/extractors/amplitude_export.py` | Export API client: download ZIP, extract, stream JSON lines |
| `src/analyzers/amplitude_analyzer.py` | Per-customer aggregation from raw events |
| `src/analyzers/hostname_classifier.py` | Parse cluster hostnames → environment, cloud provider, region |
| `tests/unit/test_amplitude_export.py` | Tests with sample raw event fixtures |
| `tests/unit/test_hostname_classifier.py` | Hostname parsing tests |

---

## Part 6: Report Integration (Minimal Changes)

### Principle

The existing customer insights report has a clear structure: Executive Summary → Stats Grid → Usage Profile → Components → Patterns Table → Documents. We don't redesign it. We **add one new section** and **enrich existing fields**.

### Change 1: Stats Grid — Add Amplitude Users Card

Currently 3 cards: `total_documents`, `total_issues`, `rhoai_patterns`. Add a 4th conditional card showing Amplitude unique users when data exists.

| File | Change | Lines |
|------|--------|-------|
| `src/reports/templates/index.html` | Add `{% if report.amplitude %}` card | ~5 |
| `src/reports/models.py` | Add `amplitude_users: Optional[int]` to `ReportSummary` | ~2 |
| `src/reports/generator.py` | Load `amplitude.json` in `_build_summary()` | ~5 |

### Change 2: Enrich Usage Profile Fields

Amplitude fills existing null fields — **no template changes needed**:

| Profile Field | Amplitude Source |
|--------------|-----------------|
| `workbench_images` | `imageName` from `Workbench Created` |
| `serving_runtimes` | `servingRuntimeName` from `Model Deployed` |
| `components_enabled` | Active features from event counts |
| `using_model_registry` | `true`/`false` from `Model Registered` count |
| `gpu_types` | `accelerator` property + hostname parsing |

Rule: Amplitude fills nulls, never overwrites existing Jira-sourced values.

| File | Change | Lines |
|------|--------|-------|
| `src/reports/generator.py` | New `_enrich_profile_with_amplitude()` method | ~30 |

### Change 3: "Connected Cluster Activity" Section in Profile

Add at the bottom of `profile_section.html`, only rendered when Amplitude data exists:

- Active users count + total events
- Maturity classification (evaluating/developing/deploying/operating)
- Cluster count with prod/non-prod breakdown
- Active vs inactive feature tags (green vs gray)
- Observed serving runtimes (from Amplitude)
- Contradictions callout (Jira says X, Amplitude shows Y)

| File | Change | Lines |
|------|--------|-------|
| `src/reports/templates/profile_section.html` | Add `{% if amplitude %}` block | ~40 |
| `src/reports/models.py` | Add `AmplitudeReportSection` dataclass | ~25 |
| `src/reports/generator.py` | New `_load_amplitude_data()` + `_detect_contradictions()` | ~50 |

### Change 4: Markdown Report

Append a brief "Connected Cluster Activity" section to the shareable `.md` report when Amplitude data exists.

| File | Change | Lines |
|------|--------|-------|
| `src/reports/generator.py` | Extend `_render_markdown()` | ~15 |

### Change 5: Streamlit Web UI

Add an "Amplitude Activity" expander in the Usage Profiles tab with `st.metric()` cards and feature tags.

| File | Change | Lines |
|------|--------|-------|
| `src/web/tabs/customers_tab.py` | Add expander in `_render_usage_profiles()` | ~30 |

### What Does NOT Change

- Executive Summary (AI-generated from Jira/support cases)
- Patterns Table (Amplitude patterns appear with `amplitude` source badge)
- Documents Table
- Issue detail pages
- Pattern detail pages
- Report generation flow (Amplitude is optional enrichment at the end)
- Template CSS (reuse existing classes; add only `.tag-active` and `.tag-inactive`)

### Total Impact

**~186 lines added across 6 files.** No existing functionality removed or modified.

---

## Open Questions

| # | Question | Who to ask |
|---|----------|-----------|
| 1 | Does the OCM lookup table include cluster display_name? | Heiko Rupp |
| 2 | Can we get ebs_id from the lookup table via API? | Heiko Rupp |
| 3 | Is there a way to query the RHOAI Events project (627029) with the same API key? | Yahav Manor |
| 4 | How far back does Amplitude retain data? | Yahav Manor |
| 5 | Are workbench names PII? Do we need to sanitize them? | Legal/compliance |
| 6 | Can project names (from `event_properties.projectName`) reveal sensitive customer info? | Legal/compliance |
