# Amplitude Data Dictionary — All Available Fields

**Source**: Amplitude "RHODS Instances" project (appId: 418474)
**Generated**: July 14, 2026
**Based on**: 21,564 raw events from Export API + Taxonomy API

## Overview

| Category | Field Count | Description |
|----------|-------------|-------------|
| Top-level event fields | 22 | Standard fields on every event (identity, timing, device) |
| Event properties | 214 | Context-specific fields that vary by event type |
| User properties | 61 | Persistent per-user fields |
| Lookup properties | 7 | OCM-derived fields from the cluster-to-account lookup table |

---

## Top-Level Event Fields (22)

Every Amplitude event has these fields regardless of event type.

| Field | Type | Description | Examples |
|-------|------|-------------|----------|
| `event_type` | string | What action was performed | `Page Viewed`, `Model Deployed`, `Workbench Created` |
| `event_time` | datetime | When the event occurred | `2026-07-10 00:25:58.914000` |
| `user_id` | string | Hashed user identity (SHA-256) | `d9a885818d9983d2bac8695a41e4e2e8c7e71191...` |
| `device_id` | UUID | Browser/device identifier | `6b5bd799-1130-42af-8bb7-ee2215671efc` |
| `amplitude_id` | number | Amplitude's internal user ID | `1635128631833` |
| `session_id` | number | Session identifier | `1783643158819` |
| `version_name` | string | **Dashboard JS bundle version** (NOT RHOAI product version) | `v3.4.0`, `v2.38.0`, `v2.35.0` |
| `start_version` | string | First JS version this user was seen on | `v3.4.0`, `v3.0.0` |
| `country` | string | GeoIP country | `Ireland`, `Turkey`, `Saudi Arabia` |
| `language` | string | Browser language | `English`, `Turkish` |
| `os_name` | string | Operating system | `Linux`, `Mac OS`, `Windows` |
| `device_family` | string | Device type | `Linux`, `Mac`, `Windows` |
| `device_type` | string | Device category | `Linux`, `Mac` |
| `platform` | string | Always "Web" | `Web` |
| `library` | string | Data pipeline | `segment` |
| `app` | number | Amplitude project ID | `418474` |
| `$insert_id` | UUID | Unique event identifier | `062055cd-c9cd-4665-9cfb-ac19b51dec1a` |
| `uuid` | UUID | Another unique identifier | `9152b19c-d8eb-4594-aa31-752b0115de76` |
| `event_id` | number | Sequential event ID | `855576451` |
| `client_event_time` | datetime | Client-side timestamp | `2026-07-10 00:25:58.914000` |
| `server_received_time` | datetime | Server-side receive time | `2026-07-10 00:26:04.683000` |
| `processed_time` | datetime | When Amplitude processed it | `2026-07-10 00:26:06.344000` |

---

## Event Properties (214 total, key ones listed)

These vary by event type. Only populated when relevant to the action.

### Identity & Navigation

| Field | Type | On Events | Examples |
|-------|------|-----------|----------|
| `clusterID` | string | ALL | `4250ce8c-0f08-4522-8592-001f1a8e983a` |
| `url` | string | Page Viewed | `https://rh-ai.apps.ocp-gb.ibm.redhataicatalyst.com/...` |
| `path` | string | Page Viewed | `/develop-train/mlflow/experiments/`, `/projects/dev-dai-evaluation` |
| `search` | string | Page Viewed | `?workspace=gpuaas-team-a-training`, `?section=workbenches` |
| `title` | string | Page Viewed | `Red Hat OpenShift AI` |
| `referrer` | string | Page Viewed | `https://oauth-openshift.apps.sks1a-tmp-oai1.sac.csda.gov.au/` |
| `from` | string | Navigation | `/`, `/ai-hub/models/deployments` |
| `to` | string | Navigation | `/projects/dev-dae-evaluation`, `/projects/serving-vllm` |
| `href` | string | Links | `https://console-openshift-console.apps.lan-tst-dc1-ocp.yapikredi.com.tr:` |

### Workbench Properties

| Field | Type | On Events | Examples |
|-------|------|-----------|----------|
| `notebookName` | string | Workbench Created/Opened | `prueba`, `capacity-report-nb`, `logistics`, `agdrp-wb-large` |
| `imageName` | string | Workbench Created | `pytorch`, `jupyter-pytorch-llmcompressor`, `s2i-generic-data-science-notebook` |
| `lastSelectedImage` | string | Workbench Created | `s2i-minimal-notebook:2025.2`, `registry.redhat.io/rhoai/odh-workbench-jupyter-pytorch-llmcompressor-cuda-py312-...` |
| `lastSelectedSize` | string | Workbench Created | `Small`, `SmallMedium` |
| `accelerator` | string | Workbench Created | `None` (sparse data) |
| `acceleratorCount` | number | Workbench Created | `0` |
| `containerResources` | string | Workbench Updated | `limits.cpu: 2,limits.memory: 8Gi, requests.cpu: 1,requests.memory: 8Gi` |
| `storageType` | string | Workbench Created | `new-persistent`, `existing-persistent` |
| `storageDataSize` | string | Workbench Created | `3Gi`, `20Gi`, `2Gi` |
| `dataConnectionEnabled` | boolean | Workbench Created | `False` |
| `dataConnectionCategory` | string | Workbench Created | (sparse) |
| `dataConnectionType` | string | Workbench Created | (sparse) |
| `wbName` | string | Workbench Opened | `custom-wb`, `Prueba`, `capacity-report-nb`, `AGDRP-wb` |
| `podSpecOptions` | JSON string | Workbench Created | `{"notebookSize":{"name":"Small","resources":{...}}` |

### Model Serving Properties

| Field | Type | On Events | Examples |
|-------|------|-----------|----------|
| `servingRuntimeName` | string | Model Deployed | `vllm-cuda-runtime`, `My vLLM CPU ServingRuntime for KServe` |
| `servingRuntimeFormat` | string | Model Deployed | `vLLM` |
| `runtime` | string | Model Deployed | `qwen3embed8b`, `qwen3-06b`, `test-model` |
| `isCustomRuntime` | boolean | Model Deployed | `True` |
| `numReplicas` | string | Model Deployed | `vllm-cuda-runtime` (bug? seems to contain runtime name not count) |
| `modelName` | string | Various | `maas-vllm-inference-1//mnt/models/model.gguf` |
| `modelType` | string | Various | `inference` |
| `modelId` | string | Various | (sparse) |

### Pipeline Properties

| Field | Type | On Events | Examples |
|-------|------|-----------|----------|
| `experimentName` | string | Pipeline/MLflow | `EvalHub` |
| `experimentSelection` | string | Pipeline | `default` |
| `experimentCount` | number | MLflow | `2`, `1` |
| `mode` | string | Pipeline Imported | `file`, `url` |
| `runType` | string | Pipeline Run | `single` |
| `runOutcome` | string | Pipeline Run | `completed`, `failed` |
| `scheduleType` | string | Pipeline | `periodic` |

### Playground / GenAI Properties

| Field | Type | On Events | Examples |
|-------|------|-----------|----------|
| `configID` | string | Playground Query | `0` |
| `compareID` | UUID | Playground Query | `ed359b2d-1139-42f4-bf64-54ae17305fbe` |
| `compareMode` | boolean | Playground Query | `False` |
| `guardrailOn` | boolean | Playground Query | `False` |
| `isStreaming` | boolean | Playground | `True` |
| `isRag` | boolean | Playground | `False` |
| `promptName` | string | Playground Query | `genai_customer_support_response`, `genai_incident_status_update` |
| `promptSource` | string | Playground Query | `default` |
| `promptVersion` | number | Playground Query | `0` |
| `ragSource` | string | Playground Query | (sparse) |
| `knowledgeSource` | string | Playground RAG | (sparse) |
| `chunkSize` | number | Playground RAG | `800` |
| `chunkOverlap` | number | Playground RAG | `400` |
| `delimiter` | string | Playground RAG Upload | (sparse) |
| `mcpServerName` | string | Playground MCP | `GitHub-MCP-Server` |
| `selectedToolsCount` | number | Playground MCP | `5`, `42`, `38` |
| `totalToolsCount` | number | Playground MCP | `5`, `44` |

### RBAC Properties

| Field | Type | On Events | Examples |
|-------|------|-----------|----------|
| `assigned_role_count` | number | RBAC | `2`, `3`, `1` |
| `cluster_role` | boolean | RBAC | (sparse) |
| `custom_ai_role_count` | number | RBAC | `0` |
| `custom_openshift_role_count` | number | RBAC | `0`, `1` |
| `custom_openshift_role_removed` | boolean | RBAC | `False` |
| `role_type` | string | RBAC | (sparse) |
| `subject_kind` | string | RBAC | `existing_user`, `existing_group`, `new_user`, `new_group` |
| `manage_permissions_button` | string | RBAC | `toolbar` |

### Evaluations / LM-Eval Properties

| Field | Type | On Events | Examples |
|-------|------|-----------|----------|
| `evaluationName` | string | Evaluations | `Jul 10, 2026, 2:24 PM` |
| `evaluationType` | string | Evaluations | `Benchmark` |
| `benchmarkName` | string | Evaluations | `Basic science Q&A` |
| `benchmarkTypes` | string/array | Evaluations | `["throughput"]`, `["arc_easy"]` |
| `metricName` | string | Evaluations | `acc` |
| `thresholdValue` | number | Evaluations | `26`, `27`, `43` |

### Available Endpoints Properties

| Field | Type | On Events | Examples |
|-------|------|-----------|----------|
| `endpointOrigin` | string | Endpoints | `http://llama-32-1b-instruct-predictor.evalhub-test-2.svc.cluster.local:8080` |
| `endpointSource` | string | Endpoints | `maas`, `namespace` |
| `endpointType` | string | Endpoints | `external`, `model` |
| `collectionName` | string | Endpoints | `Toxicity and Ethical Principles`, `Open LLM Leaderboard v2` |

### Outcome & Error Properties

| Field | Type | On Events | Examples |
|-------|------|-----------|----------|
| `outcome` | enum | Most actions | `submit`, `cancel` |
| `success` | boolean | Most actions | `True`, `False` |
| `error` | string | On failures | `failed to connect to MCP server: ...`, `project already exists` |
| `errorName` | string | On failures | (sparse) |
| `error.statusObject.code` | number | K8s errors | `409` (AlreadyExists), `404` (NotFound) |
| `error.statusObject.reason` | string | K8s errors | `AlreadyExists`, `NotFound` |
| `error.statusObject.message` | string | K8s errors | Full error message |

### Other Properties

| Field | Type | On Events | Examples |
|-------|------|-----------|----------|
| `projectName` | string | Various | `agusrafafer-dev`, `telcel-capacity-forecast`, `researchteam` |
| `namespace` | string | Various | `language-models`, `ai-poc`, `ai-models`, `triage-assistant` |
| `GPU` | number | Various | (sparse) |
| `durationMs` | number | Various | `63000`, `61000`, `19000` |
| `assetId` | string | Catalog | `claude-haiku-4-5-20251001`, `qwen25-coder-15b-instruct-maas` |
| `assetType` | string | Catalog | `model` |
| `selectedModel` | string | Various | `llama-32-1b-instruct`, `Other (External endpoint)` |
| `copyTarget` | string | Copy actions | `endpoint`, `service_token` |

---

## User Properties (61 total, key ones listed)

Persistent per-user. Set once and carried forward on all subsequent events.

| Field | Type | Description | Examples |
|-------|------|-------------|----------|
| `gp:isAdmin` | boolean | Whether user is an RHOAI admin | `True`, `False` |
| `gp:canCreateProjects` | boolean | Permission to create projects | `True` |
| `gp:clusterID` | string | Cluster UUID (same as event property) | `4250ce8c-...` |
| `gp:projectCount` | number | Number of projects the user has | (number) |
| `gp:initial_referrer` | string | How the user first arrived | `https://oauth-openshift.apps...` |
| `gp:referrer` | string | Last referrer | `https://rh-ai.apps...` |
| `version` | string | **Dashboard JS version** (NOT RHOAI version) | `v3.4.0`, `v2.38.0` |
| `start_version` | string | First JS version seen | `v3.4.0` |
| `country` | string | GeoIP country | `Ireland`, `Turkey` |
| `language` | string | Browser language | `English` |
| `os` | string | Operating system | `Linux`, `Mac OS` |
| `platform` | string | Platform | `Web` |
| `gp:utm_*` | string | Marketing UTM parameters | (various campaign tracking) |
| `gp:initial_utm_*` | string | First-touch UTM parameters | (various) |

---

## Lookup Properties (7 — from OCM lookup table)

These are NOT on individual events — they're joined at query time via Amplitude's lookup table mechanism. Maintained by Heiko Rupp (hrupp@redhat.com) from OCM/Redshift data.

| Property ID | Name | Description | Examples |
|-------------|------|-------------|----------|
| `10895` | `org_name` | Organization name from OCM | `SAUDI ARABIAN OIL COMPANY`, `TURK HAVA YOLLARI ANONIM ORTAKLIGI` |
| `10896` | `org_id` | OCM organization ID | `17457657`, `4298439` |
| `10897` | `ebs_account_id` | EBS account ID | `11695061`, `626726` |
| `12654` | `rhsc_account_name` | Salesforce account name | `SAUDI ARABIAN OIL COMPANY` |
| `12655` | `openshift_customer` | OpenShift customer flag | `1` (boolean-like) |
| `12662` | `ebs_account_number` | EBS account number (sparse — 19/154 populated) | `626726`, `694995` |
| `14981` | `RHOAI-Version` | **Real RHOAI product version** | `3.4`, `3.3`, `2.22`, `2.19`, `2.16` |

### Important Notes on Lookup Properties

- `org_name` (10895) is the primary customer identifier — all Amplitude queries group by this
- `ebs_account_number` (12662) is sparse — only populated for ~19 customers. `ebs_account_id` (10897) has better coverage.
- `RHOAI-Version` (14981) shows the real RHOAI product version, unlike `version_name` on events which is the dashboard JS bundle version
- A single customer can have multiple `org_id`/`ebs_account_id` entries (multiple clusters)
- The lookup table is refreshed from OCM/Redshift by Heiko's pipeline — not real-time
