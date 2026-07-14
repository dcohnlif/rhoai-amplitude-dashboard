"""Amplitude REST API client for RHOAI product analytics.

Fetches customer usage data from the Amplitude "RHODS Instances" project
using the Event Segmentation API. Requires AMPLITUDE_API_KEY and
AMPLITUDE_SECRET_KEY environment variables.

API docs: https://amplitude.com/docs/en/apis/analytics/dashboard-rest
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta

import requests

logger = logging.getLogger(__name__)

# Default RHODS Instances project
DEFAULT_APP_ID = "418474"

# org_name lookup property ID in Amplitude
ORG_NAME_PROPERTY_ID = "10895"

# Key RHOAI events to track per customer.
# Must stay in sync with EVENT_TO_PATTERN in amplitude_mapper.py.
TRACKED_EVENTS = [
    # Workbenches
    "Workbench Opened",
    "Workbench Created",
    "Workbench Started",
    "Workbench Stopped",
    "Workbench Updated",
    "Workbench image updated",
    "Notebook Server Started",
    # Model Serving
    "Model Deployed",
    "Model Server Added",
    "Model Server Modified",
    "Model Deleted",
    "Model Updated",
    "Model Server Deleted",
    # Pipelines
    "Pipeline Run Triggered",
    "Pipeline Imported",
    "Pipeline Server Configured",
    "Pipeline Runs Archived",
    "Pipeline Deleted",
    "Pipeline Version Updated",
    # Model Registry
    "Model Registered",
    "Model Registry Created",
    "Model Version Archived",
    "Registered Model Archived",
    "Archived Model Version Restored",
    # RBAC
    "RBAC Role Management Opened",
    "RBAC Role Assignment Changes Saved",
    "RBAC Role Unassigned",
    "RBAC Role Details Clicked",
    # Available Endpoints / MaaS
    "Available Endpoints Endpoint Viewed",
    "Available Endpoints Create Endpoint Submitted",
    "Available Endpoints Vector Store Info Viewed",
    # Evaluations
    "Evaluations Evaluation Run Started",
    "Evaluations Evaluation Completed",
    "Evaluations Benchmark Run Selected",
    # Playground
    "Playground Query Submitted",
    "Playground Setup",
    "Playground RAG Upload File",
    "Playground RAG Toggle Selected",
    "Playground MCP Auth",
    "Playground Compare Mode Entered",
    # MLflow
    "MLflow Embedded View Opened",
    "MLflow Experiment Created",
    # Guardrails
    "Guardrail Activated",
    "Guardrails Enabled",
    # Experiments
    "Experiment Created",
    # Projects
    "NewProject Created",
    "Project Edited",
    "Project Deleted",
    # Model Catalog
    "Catalog Model Registered",
    # Application
    "Application Enabled",
]

# Filters to exclude Red Hat internal users and unmapped clusters
_EXCLUDE_INTERNAL_FILTERS = [
    {
        "subprop_type": "lookup",
        "subprop_key": ORG_NAME_PROPERTY_ID,
        "subprop_op": "does not contain",
        "subprop_value": ["RedHat", "Red Hat"],
    },
    {
        "subprop_type": "lookup",
        "subprop_key": ORG_NAME_PROPERTY_ID,
        "subprop_op": "is not",
        "subprop_value": ["(none)"],
    },
]


def _extract_label(label_entry) -> str:
    """Extract org_name from a seriesLabels entry.

    The API returns labels in two possible formats:
    - [index, "org_name"]  (plain string)
    - [index, {"label": "org_name"}]  (dict with label key)
    """
    if len(label_entry) < 2:
        return ""
    val = label_entry[1]
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        return val.get("label", "")
    return ""


class AmplitudeAuthError(Exception):
    """Raised when Amplitude API authentication fails (401/403)."""


class AmplitudeClient:
    """REST API client for Amplitude analytics.

    Uses the Event Segmentation API to query customer usage data.
    Auth: HTTP Basic with api_key:secret_key.
    """

    SEGMENTATION_URL = "https://amplitude.com/api/2/events/segmentation"
    TAXONOMY_URL = "https://amplitude.com/api/2/taxonomy/event"

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        app_id: str = DEFAULT_APP_ID,
        timeout: int = 60,
    ):
        self.api_key = api_key
        self.secret_key = secret_key
        self.app_id = app_id
        self.timeout = timeout
        self._session = requests.Session()
        self._session.auth = (api_key, secret_key)

    @classmethod
    def from_env(cls) -> "AmplitudeClient":
        """Create client from environment variables."""
        api_key = os.getenv("AMPLITUDE_API_KEY")
        secret_key = os.getenv("AMPLITUDE_SECRET_KEY")
        if not api_key or not secret_key:
            raise ValueError(
                "AMPLITUDE_API_KEY and AMPLITUDE_SECRET_KEY must be set. "
                "Get keys from Amplitude > Organization Settings > API Keys."
            )
        return cls(api_key=api_key, secret_key=secret_key)

    def verify_auth(self) -> bool:
        """Verify API key + secret key are valid."""
        try:
            response = self._session.get(
                self.TAXONOMY_URL,
                params={"limit": 1},
                timeout=self.timeout,
            )
            if response.status_code in (401, 403):
                raise AmplitudeAuthError(
                    f"Amplitude authentication failed ({response.status_code}). "
                    "Check AMPLITUDE_API_KEY and AMPLITUDE_SECRET_KEY."
                )
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            if isinstance(e, requests.HTTPError) and e.response is not None:
                if e.response.status_code in (401, 403):
                    raise AmplitudeAuthError(str(e)) from e
            raise

    def get_customers(self, days: int = 30) -> list[dict]:
        """Fetch all RHOAI customers with unique users and total events.

        Uses the Event Segmentation API grouped by org_name.
        Excludes Red Hat internal users and unmapped clusters.

        Returns list of dicts: [{org_name, unique_users, total_events}]
        """
        end = datetime.now()
        start = end - timedelta(days=days)

        # Query unique users by org_name
        users_data = self._query_segmentation(
            event_type="_all",
            metric="uniques",
            group_by_property=ORG_NAME_PROPERTY_ID,
            start=start.strftime("%Y%m%d"),
            end=end.strftime("%Y%m%d"),
            filters=_EXCLUDE_INTERNAL_FILTERS,
            interval=str(days),
        )

        time.sleep(0.5)  # Rate limiting

        # Query total events by org_name
        events_data = self._query_segmentation(
            event_type="_all",
            metric="totals",
            group_by_property=ORG_NAME_PROPERTY_ID,
            start=start.strftime("%Y%m%d"),
            end=end.strftime("%Y%m%d"),
            filters=_EXCLUDE_INTERNAL_FILTERS,
            interval=str(days),
        )

        # Parse and merge results
        customers: dict[str, dict] = {}

        # Build customer list from unique users query
        series_values = users_data.get("data", {}).get("series", [])
        series_labels = users_data.get("data", {}).get("seriesLabels", [])
        collapsed = users_data.get("data", {}).get("seriesCollapsed", [])
        for i, label_entry in enumerate(series_labels):
            org_name = _extract_label(label_entry)
            if not org_name:
                continue
            # Use seriesCollapsed for the deduped unique count (preferred),
            # fall back to first series value
            unique = 0
            if i < len(collapsed) and collapsed[i]:
                unique = (
                    collapsed[i][0].get("value", 0)
                    if isinstance(collapsed[i][0], dict)
                    else 0
                )
            elif i < len(series_values):
                values = [v for v in series_values[i] if isinstance(v, (int, float))]
                unique = values[0] if values else 0
            customers[org_name] = {
                "org_name": org_name,
                "unique_users": unique,
                "total_events": 0,
            }

        # Merge total events
        events_series = events_data.get("data", {}).get("series", [])
        events_labels = events_data.get("data", {}).get("seriesLabels", [])
        events_collapsed = events_data.get("data", {}).get("seriesCollapsed", [])
        for i, label_entry in enumerate(events_labels):
            org_name = _extract_label(label_entry)
            if not org_name:
                continue
            total = 0
            if i < len(events_collapsed) and events_collapsed[i]:
                total = (
                    events_collapsed[i][0].get("value", 0)
                    if isinstance(events_collapsed[i][0], dict)
                    else 0
                )
            elif i < len(events_series):
                total = sum(v for v in events_series[i] if isinstance(v, (int, float)))
            if org_name not in customers:
                customers[org_name] = {
                    "org_name": org_name,
                    "unique_users": 0,
                    "total_events": 0,
                }
            customers[org_name]["total_events"] = total

        return sorted(customers.values(), key=lambda c: c["total_events"], reverse=True)

    def get_feature_usage(self, days: int = 30) -> dict[str, dict[str, int]]:
        """Fetch per-customer event counts for key RHOAI features.

        Returns: {org_name: {event_name: count, ...}, ...}
        """
        end = datetime.now()
        start = end - timedelta(days=days)

        result: dict[str, dict[str, int]] = {}

        for event_type in TRACKED_EVENTS:
            time.sleep(0.5)  # Rate limiting
            try:
                data = self._query_segmentation(
                    event_type=event_type,
                    metric="totals",
                    group_by_property=ORG_NAME_PROPERTY_ID,
                    start=start.strftime("%Y%m%d"),
                    end=end.strftime("%Y%m%d"),
                    filters=_EXCLUDE_INTERNAL_FILTERS,
                    interval=str(days),
                )

                series_values = data.get("data", {}).get("series", [])
                series_labels = data.get("data", {}).get("seriesLabels", [])
                collapsed = data.get("data", {}).get("seriesCollapsed", [])

                for i, label_entry in enumerate(series_labels):
                    org_name = _extract_label(label_entry)
                    if not org_name:
                        continue
                    if org_name not in result:
                        result[org_name] = {}
                    # Use seriesCollapsed (preferred) or sum series values
                    total = 0
                    if i < len(collapsed) and collapsed[i]:
                        total = (
                            int(collapsed[i][0].get("value", 0))
                            if isinstance(collapsed[i][0], dict)
                            else 0
                        )
                    elif i < len(series_values):
                        total = int(
                            sum(
                                v
                                for v in series_values[i]
                                if isinstance(v, (int, float))
                            )
                        )
                    if total > 0:
                        result[org_name][event_type] = total

            except Exception as e:
                logger.warning("Failed to query event '%s': %s", event_type, e)

        return result

    def get_property_breakdown(
        self,
        event_type: str,
        property_name: str,
        property_type: str = "event",
        days: int = 30,
    ) -> dict[str, dict[str, int]]:
        """Get per-customer breakdown of an event property.

        Queries a specific event type grouped by both org_name and
        an event/user property to see, for example, which serving
        runtimes each customer uses.

        Args:
            event_type: Event to query (e.g., "Model Deployed")
            property_name: Property to break down (e.g., "servingRuntimeName")
            property_type: Type of property ("event" or "user")
            days: Time period in days

        Returns:
            {org_name: {property_value: count, ...}, ...}
        """
        from datetime import datetime, timedelta

        end = datetime.now()
        start = end - timedelta(days=days)

        try:
            # Build event spec with two group_by dimensions
            import json as json_mod

            event_spec = {
                "event_type": event_type,
                "filters": [f for f in _EXCLUDE_INTERNAL_FILTERS],
                "group_by": [
                    {
                        "type": "lookup",
                        "value": ORG_NAME_PROPERTY_ID,
                        "group_type": "User",
                    },
                    {"type": property_type, "value": property_name},
                ],
            }

            params = {
                "e": json_mod.dumps(event_spec),
                "m": "totals",
                "start": start.strftime("%Y%m%d"),
                "end": end.strftime("%Y%m%d"),
                "i": str(days),
                "limit": "500",
            }

            response = self._session.get(
                self.SEGMENTATION_URL,
                params=params,
                timeout=self.timeout,
            )
            if response.status_code in (401, 403):
                raise AmplitudeAuthError(
                    f"Amplitude API authentication failed ({response.status_code})"
                )
            response.raise_for_status()
            data = response.json()

            # Parse: labels are "org_name; property_value"
            result: dict[str, dict[str, int]] = {}
            labels = data.get("data", {}).get("seriesLabels", [])
            collapsed = data.get("data", {}).get("seriesCollapsed", [])
            series = data.get("data", {}).get("series", [])

            for i, label_entry in enumerate(labels):
                raw_label = _extract_label(label_entry)
                if not raw_label:
                    continue

                parts = raw_label.split("; ", 1)
                org_name = parts[0] if parts else ""
                prop_value = parts[1] if len(parts) > 1 else "(none)"

                if not org_name or prop_value == "(none)":
                    continue

                total = 0
                if i < len(collapsed) and collapsed[i]:
                    total = (
                        int(collapsed[i][0].get("value", 0))
                        if isinstance(collapsed[i][0], dict)
                        else 0
                    )
                elif i < len(series):
                    total = int(
                        sum(v for v in series[i] if isinstance(v, (int, float)))
                    )

                if total > 0:
                    if org_name not in result:
                        result[org_name] = {}
                    result[org_name][prop_value] = total

            return result

        except AmplitudeAuthError:
            raise
        except Exception as e:
            logger.warning(
                "Failed to query property breakdown for %s.%s: %s",
                event_type,
                property_name,
                e,
            )
            return {}

    def _query_segmentation(
        self,
        event_type: str,
        metric: str,
        group_by_property: str,
        start: str,
        end: str,
        filters: list[dict] | None = None,
        interval: str = "30",
    ) -> dict:
        """Query the Event Segmentation API.

        Args:
            event_type: Event to query (e.g., "Workbench Opened", "_all")
            metric: "uniques" or "totals"
            group_by_property: Property ID to group by (e.g., "10895" for org_name)
            start: Start date YYYYMMDD
            end: End date YYYYMMDD
            filters: Optional event filters
            interval: Interval in days for bucketing (default "30")

        Returns:
            Raw API response dict
        """
        event_spec: dict = {"event_type": event_type}
        if filters:
            event_spec["filters"] = [
                {
                    "subprop_type": f["subprop_type"],
                    "subprop_key": f["subprop_key"],
                    "subprop_op": f["subprop_op"],
                    "subprop_value": f["subprop_value"],
                }
                for f in filters
            ]
        event_spec["group_by"] = [
            {"type": "lookup", "value": group_by_property, "group_type": "User"}
        ]

        params = {
            "e": json.dumps(event_spec),
            "m": metric,
            "start": start,
            "end": end,
            "i": interval,
        }

        response = self._session.get(
            self.SEGMENTATION_URL,
            params=params,
            timeout=self.timeout,
        )

        if response.status_code in (401, 403):
            raise AmplitudeAuthError(
                f"Amplitude API authentication failed ({response.status_code})"
            )

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 5))
            logger.warning(
                "Rate limited by Amplitude API, retrying in %ds", retry_after
            )
            time.sleep(retry_after)
            response = self._session.get(
                self.SEGMENTATION_URL,
                params=params,
                timeout=self.timeout,
            )
            if response.status_code in (401, 403):
                raise AmplitudeAuthError(
                    f"Amplitude API authentication failed ({response.status_code})"
                )

        response.raise_for_status()
        return response.json()
