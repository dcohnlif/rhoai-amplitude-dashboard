"""Map Amplitude events to RHOAI usage pattern taxonomy.

Provides a deterministic mapping from Amplitude UI events to
the project's usage pattern components. No LLM calls needed.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PatternMapping:
    """A mapping from an Amplitude event to a usage pattern component."""

    component: str
    stage: str
    pattern_title: str
    event_name: str
    event_count: int
    evidence_strength: str  # "low", "medium", "high"


# Maps Amplitude event names to pattern taxonomy components.
# component_hint is validated against TaxonomyLoader at runtime.
# Source: Amplitude RHODS Instances project (appId 418474) event taxonomy,
# cross-referenced with Yahav Manor's "User Patterns x Amplitude Events" doc.
EVENT_TO_PATTERN: dict[str, dict] = {
    # --- Workbenches (7 events) ---
    "Workbench Opened": {
        "component_hint": "Workbenches",
        "stage": "Development",
        "pattern_title": "Workbench Usage",
        "min_threshold": 5,
        "evidence": "high",
    },
    "Workbench Created": {
        "component_hint": "Workbenches",
        "stage": "Development",
        "pattern_title": "Workbench Provisioning",
        "min_threshold": 1,
        "evidence": "high",
    },
    "Workbench Started": {
        "component_hint": "Workbenches",
        "stage": "Development",
        "pattern_title": "Workbench Usage",
        "min_threshold": 3,
        "evidence": "high",
    },
    "Workbench Stopped": {
        "component_hint": "Workbenches",
        "stage": "Development",
        "pattern_title": "Workbench Usage",
        "min_threshold": 3,
        "evidence": "medium",
    },
    "Workbench Updated": {
        "component_hint": "Workbenches",
        "stage": "Development",
        "pattern_title": "Workbench Management",
        "min_threshold": 1,
        "evidence": "medium",
    },
    "Workbench image updated": {
        "component_hint": "Workbenches",
        "stage": "Development",
        "pattern_title": "Custom Workbench Image",
        "min_threshold": 1,
        "evidence": "medium",
    },
    "Notebook Server Started": {
        "component_hint": "Workbenches",
        "stage": "Development",
        "pattern_title": "Workbench Usage",
        "min_threshold": 1,
        "evidence": "medium",
    },
    # --- Model Serving (6 events) ---
    "Model Deployed": {
        "component_hint": "Model Serving",
        "stage": "Serving",
        "pattern_title": "Model Deployment",
        "min_threshold": 1,
        "evidence": "high",
    },
    "Model Server Added": {
        "component_hint": "Model Serving",
        "stage": "Serving",
        "pattern_title": "Model Serving Infrastructure",
        "min_threshold": 1,
        "evidence": "high",
    },
    "Model Server Modified": {
        "component_hint": "Model Serving",
        "stage": "Serving",
        "pattern_title": "Model Serving Management",
        "min_threshold": 1,
        "evidence": "medium",
    },
    "Model Deleted": {
        "component_hint": "Model Serving",
        "stage": "Serving",
        "pattern_title": "Model Serving Management",
        "min_threshold": 1,
        "evidence": "medium",
    },
    "Model Updated": {
        "component_hint": "Model Serving",
        "stage": "Serving",
        "pattern_title": "Model Serving Management",
        "min_threshold": 1,
        "evidence": "medium",
    },
    "Model Server Deleted": {
        "component_hint": "Model Serving",
        "stage": "Serving",
        "pattern_title": "Model Serving Management",
        "min_threshold": 1,
        "evidence": "medium",
    },
    # --- Data Science Pipelines (6 events) ---
    "Pipeline Run Triggered": {
        "component_hint": "Data Science Pipelines",
        "stage": "ML Operations",
        "pattern_title": "Pipeline Execution",
        "min_threshold": 1,
        "evidence": "high",
    },
    "Pipeline Imported": {
        "component_hint": "Data Science Pipelines",
        "stage": "ML Operations",
        "pattern_title": "Pipeline Development",
        "min_threshold": 1,
        "evidence": "medium",
    },
    "Pipeline Server Configured": {
        "component_hint": "Data Science Pipelines",
        "stage": "ML Operations",
        "pattern_title": "Pipeline Server Configuration",
        "min_threshold": 1,
        "evidence": "high",
    },
    "Pipeline Runs Archived": {
        "component_hint": "Data Science Pipelines",
        "stage": "ML Operations",
        "pattern_title": "Pipeline Execution",
        "min_threshold": 1,
        "evidence": "medium",
    },
    "Pipeline Deleted": {
        "component_hint": "Data Science Pipelines",
        "stage": "ML Operations",
        "pattern_title": "Pipeline Development",
        "min_threshold": 1,
        "evidence": "medium",
    },
    "Pipeline Version Updated": {
        "component_hint": "Data Science Pipelines",
        "stage": "ML Operations",
        "pattern_title": "Pipeline Development",
        "min_threshold": 1,
        "evidence": "medium",
    },
    # --- Model Registry (5 events) ---
    "Model Registered": {
        "component_hint": "Model Registry",
        "stage": "ML Operations",
        "pattern_title": "Model Registration",
        "min_threshold": 1,
        "evidence": "high",
    },
    "Model Registry Created": {
        "component_hint": "Model Registry",
        "stage": "ML Operations",
        "pattern_title": "Model Registry Management",
        "min_threshold": 1,
        "evidence": "high",
    },
    "Model Version Archived": {
        "component_hint": "Model Registry",
        "stage": "ML Operations",
        "pattern_title": "Model Versioning",
        "min_threshold": 1,
        "evidence": "medium",
    },
    "Registered Model Archived": {
        "component_hint": "Model Registry",
        "stage": "ML Operations",
        "pattern_title": "Model Versioning",
        "min_threshold": 1,
        "evidence": "medium",
    },
    "Archived Model Version Restored": {
        "component_hint": "Model Registry",
        "stage": "ML Operations",
        "pattern_title": "Model Versioning",
        "min_threshold": 1,
        "evidence": "medium",
    },
    # --- RBAC (4 events) ---
    "RBAC Role Management Opened": {
        "component_hint": "RBAC",
        "stage": "Governance",
        "pattern_title": "RBAC Management",
        "min_threshold": 1,
        "evidence": "medium",
    },
    "RBAC Role Assignment Changes Saved": {
        "component_hint": "RBAC",
        "stage": "Governance",
        "pattern_title": "RBAC Role Assignment",
        "min_threshold": 1,
        "evidence": "high",
    },
    "RBAC Role Unassigned": {
        "component_hint": "RBAC",
        "stage": "Governance",
        "pattern_title": "RBAC Role Assignment",
        "min_threshold": 1,
        "evidence": "high",
    },
    "RBAC Role Details Clicked": {
        "component_hint": "RBAC",
        "stage": "Governance",
        "pattern_title": "RBAC Management",
        "min_threshold": 3,
        "evidence": "low",
    },
    # --- Available Endpoints / MaaS (3 events) ---
    "Available Endpoints Endpoint Viewed": {
        "component_hint": "Available Endpoints",
        "stage": "Serving",
        "pattern_title": "Endpoint Management",
        "min_threshold": 1,
        "evidence": "medium",
    },
    "Available Endpoints Create Endpoint Submitted": {
        "component_hint": "Available Endpoints",
        "stage": "Serving",
        "pattern_title": "Endpoint Creation",
        "min_threshold": 1,
        "evidence": "high",
    },
    "Available Endpoints Vector Store Info Viewed": {
        "component_hint": "Available Endpoints",
        "stage": "Serving",
        "pattern_title": "Vector Store Usage",
        "min_threshold": 1,
        "evidence": "medium",
    },
    # --- Evaluations / LM-Eval (3 events) ---
    "Evaluations Evaluation Run Started": {
        "component_hint": "Evaluations",
        "stage": "ML Operations",
        "pattern_title": "Model Evaluation",
        "min_threshold": 1,
        "evidence": "high",
    },
    "Evaluations Evaluation Completed": {
        "component_hint": "Evaluations",
        "stage": "ML Operations",
        "pattern_title": "Model Evaluation",
        "min_threshold": 1,
        "evidence": "high",
    },
    "Evaluations Benchmark Run Selected": {
        "component_hint": "Evaluations",
        "stage": "ML Operations",
        "pattern_title": "Model Benchmarking",
        "min_threshold": 1,
        "evidence": "medium",
    },
    # --- Playground (6 events — subset of 39 total) ---
    "Playground Query Submitted": {
        "component_hint": "Playground",
        "stage": "Exploration",
        "pattern_title": "GenAI Playground Chat",
        "min_threshold": 3,
        "evidence": "medium",
    },
    "Playground Setup": {
        "component_hint": "Playground",
        "stage": "Exploration",
        "pattern_title": "Playground Configuration",
        "min_threshold": 1,
        "evidence": "high",
    },
    "Playground RAG Upload File": {
        "component_hint": "Playground",
        "stage": "Exploration",
        "pattern_title": "RAG Stack Usage",
        "min_threshold": 1,
        "evidence": "high",
    },
    "Playground RAG Toggle Selected": {
        "component_hint": "Playground",
        "stage": "Exploration",
        "pattern_title": "RAG Stack Usage",
        "min_threshold": 1,
        "evidence": "medium",
    },
    "Playground MCP Auth": {
        "component_hint": "Playground",
        "stage": "Exploration",
        "pattern_title": "Agentic AI (MCP)",
        "min_threshold": 1,
        "evidence": "high",
    },
    "Playground Compare Mode Entered": {
        "component_hint": "Playground",
        "stage": "Exploration",
        "pattern_title": "Model Comparison",
        "min_threshold": 1,
        "evidence": "medium",
    },
    # --- MLflow (2 events — categorized under Evaluations per Yahav's mapping) ---
    "MLflow Embedded View Opened": {
        "component_hint": "Evaluations",
        "stage": "ML Operations",
        "pattern_title": "Experiment Tracking",
        "min_threshold": 1,
        "evidence": "medium",
    },
    "MLflow Experiment Created": {
        "component_hint": "Evaluations",
        "stage": "ML Operations",
        "pattern_title": "Experiment Tracking",
        "min_threshold": 1,
        "evidence": "high",
    },
    # --- Guardrails (2 events) ---
    "Guardrail Activated": {
        "component_hint": "Guardrails",
        "stage": "Governance",
        "pattern_title": "Content Safety",
        "min_threshold": 1,
        "evidence": "high",
    },
    "Guardrails Enabled": {
        "component_hint": "Guardrails",
        "stage": "Governance",
        "pattern_title": "Content Safety",
        "min_threshold": 1,
        "evidence": "high",
    },
    # --- Experiments (1 event — categorized under Data Science Pipelines per Yahav's mapping) ---
    "Experiment Created": {
        "component_hint": "Data Science Pipelines",
        "stage": "ML Operations",
        "pattern_title": "Pipeline Experiments",
        "min_threshold": 1,
        "evidence": "high",
    },
    # --- Projects (3 events) ---
    "NewProject Created": {
        "component_hint": "Projects",
        "stage": "Setup",
        "pattern_title": "Project Management",
        "min_threshold": 1,
        "evidence": "low",
    },
    "Project Edited": {
        "component_hint": "Projects",
        "stage": "Setup",
        "pattern_title": "Project Management",
        "min_threshold": 1,
        "evidence": "low",
    },
    "Project Deleted": {
        "component_hint": "Projects",
        "stage": "Setup",
        "pattern_title": "Project Management",
        "min_threshold": 1,
        "evidence": "low",
    },
    # --- Model Catalog (1 event) ---
    "Catalog Model Registered": {
        "component_hint": "Model Catalog",
        "stage": "ML Operations",
        "pattern_title": "Model Catalog Usage",
        "min_threshold": 1,
        "evidence": "high",
    },
    # --- Application (1 event — from Yahav's mapping) ---
    "Application Enabled": {
        "component_hint": "Application",
        "stage": "Setup",
        "pattern_title": "Platform Feature Governance",
        "min_threshold": 1,
        "evidence": "medium",
    },
}


def map_feature_usage_to_patterns(
    feature_counts: dict[str, int],
    taxonomy_loader=None,
) -> list[PatternMapping]:
    """Map Amplitude feature usage counts to pattern components.

    Args:
        feature_counts: {event_name: count} from AmplitudeClient
        taxonomy_loader: Optional TaxonomyLoader for component validation

    Returns:
        List of PatternMapping for events above their threshold
    """
    # Get valid components for validation
    valid_components: set[str] | None = None
    if taxonomy_loader:
        try:
            valid_components = set(taxonomy_loader.get_all_components())
        except Exception as e:
            logger.warning("Failed to load taxonomy components: %s", e)

    mappings = []
    for event_name, count in feature_counts.items():
        mapping_def = EVENT_TO_PATTERN.get(event_name)
        if not mapping_def:
            continue  # Unknown event, skip

        # Check threshold
        if count < mapping_def["min_threshold"]:
            continue

        component = mapping_def["component_hint"]

        # Validate against taxonomy if available
        if valid_components and component not in valid_components:
            logger.warning(
                "Amplitude event '%s' maps to component '%s' which is not in taxonomy",
                event_name,
                component,
            )

        mappings.append(
            PatternMapping(
                component=component,
                stage=mapping_def["stage"],
                pattern_title=mapping_def["pattern_title"],
                event_name=event_name,
                event_count=count,
                evidence_strength=mapping_def["evidence"],
            )
        )

    return mappings


def compute_evidence_level(event_count: int) -> str:
    """Map event count to evidence strength string.

    Args:
        event_count: Number of events observed

    Returns:
        "low", "medium", or "high"
    """
    if event_count <= 5:
        return "low"
    if event_count <= 20:
        return "medium"
    return "high"


def build_active_inactive_features(
    feature_counts: dict[str, int],
) -> tuple[list[str], list[str]]:
    """Build lists of active and inactive features from event counts.

    Active: components where at least one event is above its threshold.
    Inactive: components where ALL events have zero counts.

    A component with some events below threshold but > 0 is considered
    "inconclusive" and appears in neither list.

    Args:
        feature_counts: {event_name: count}

    Returns:
        Tuple of (active_features, inactive_features) as component names
    """
    # Aggregate per component: track whether any event is active, any has data
    component_active: dict[str, bool] = {}  # True if any event above threshold
    component_has_any_data: dict[str, bool] = {}  # True if any event count > 0

    for event_name, mapping_def in EVENT_TO_PATTERN.items():
        component = mapping_def["component_hint"]
        count = feature_counts.get(event_name, 0)

        if component not in component_active:
            component_active[component] = False
            component_has_any_data[component] = False

        if count >= mapping_def["min_threshold"]:
            component_active[component] = True
        if count > 0:
            component_has_any_data[component] = True

    active = sorted(c for c, is_active in component_active.items() if is_active)
    inactive = sorted(
        c
        for c, is_active in component_active.items()
        if not is_active and not component_has_any_data[c]
    )

    return active, inactive


def detect_contradictions(
    feature_counts: dict[str, int],
    usage_profile: dict | None,
) -> list[str]:
    """Detect contradictions between Amplitude data and Jira-sourced usage profile.

    A contradiction is when Jira says a feature is used but Amplitude shows
    zero activity, or vice versa.

    Args:
        feature_counts: Amplitude event counts {event_name: count}
        usage_profile: Existing usage_profile.json data (may be None)

    Returns:
        List of contradiction description strings
    """
    if not usage_profile:
        return []

    contradictions = []

    # Jira says using_dsp=true but Amplitude shows 0 pipeline events
    pipeline_count = feature_counts.get(
        "Pipeline Run Triggered", 0
    ) + feature_counts.get("Pipeline Imported", 0)
    if usage_profile.get("using_dsp") is True and pipeline_count == 0:
        contradictions.append(
            "Pipelines: claimed in Jira but 0 pipeline events in Amplitude (last 30d)"
        )

    # Amplitude shows model registry activity but Jira doesn't mention it
    registry_count = feature_counts.get("Model Registered", 0)
    if usage_profile.get("using_model_registry") is None and registry_count > 0:
        contradictions.append(
            f"Model Registry: active in Amplitude ({registry_count} registrations) "
            "but not mentioned in Jira"
        )

    # Jira has serving_runtimes but Amplitude shows additional ones
    # (This would need serving runtime data from Amplitude — defer to Export API phase)

    return contradictions
