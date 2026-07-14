"""Classify Amplitude customers by adoption stage using trajectory analysis.

Combines current-period usage (event volume, feature breadth) with
historical trajectory (6-month trend) to classify customers into
adoption stages: Scaling, Established, Expanding, Exploring, Declining,
Churned, or Unscored.

Monthly event counts are normalized by weekdays-per-month before
trajectory analysis to prevent false decline signals from short
months (February, holidays).
"""

import calendar
import json
import logging
import os
from typing import Optional

from src.models.amplitude import AmplitudeProfile

logger = logging.getLogger(__name__)

# Average weekdays per month (normalization baseline)
_AVG_WEEKDAYS = 22


def _weekdays_in_month(year: int, month: int) -> int:
    """Count weekdays (Mon-Fri) in a month."""
    days = calendar.monthrange(year, month)[1]
    return sum(1 for d in range(1, days + 1) if calendar.weekday(year, month, d) < 5)


def _normalize_events(
    monthly_events: list[int],
    month_labels: list[str] | None,
) -> list[int]:
    """Normalize monthly event counts by weekdays per month.

    Scales each month's events to a standard 22-weekday month equivalent,
    preventing short months (Feb=20 days) from appearing as declines.

    Args:
        monthly_events: Raw event counts per month
        month_labels: Month labels as "YYYY-MM" or "YYYY-MM-DD" strings.
            If None, returns raw events unchanged.

    Returns:
        Normalized event counts
    """
    if not month_labels or len(month_labels) != len(monthly_events):
        return monthly_events

    normalized = []
    for i, raw in enumerate(monthly_events):
        if raw == 0:
            normalized.append(0)
            continue
        try:
            year = int(month_labels[i][:4])
            month = int(month_labels[i][5:7])
            weekdays = _weekdays_in_month(year, month)
            if weekdays > 0:
                normalized.append(int(raw * _AVG_WEEKDAYS / weekdays))
            else:
                normalized.append(raw)
        except (ValueError, IndexError):
            normalized.append(raw)

    return normalized


def load_historical_data(
    data_dir: str = "data",
) -> dict:
    """Load historical backfill data for trajectory analysis.

    Args:
        data_dir: Path to the data directory

    Returns:
        Dict with 'months' list and 'customers' dict keyed by org_name,
        or empty dict if not available.
    """
    path = os.path.join(data_dir, "amplitude", "historical_backfill.json")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load historical backfill: %s", e)
        return {}


def compute_trajectory(
    monthly_events: list[int],
    month_labels: list[str] | None = None,
) -> dict:
    """Compute trajectory metrics from monthly event counts.

    Normalizes by weekdays-per-month before comparing, so short months
    (February, partial months) don't trigger false decline signals.

    Compares the average of the two most recent full months against
    the average of the first two active months to determine direction.

    Args:
        monthly_events: List of monthly event counts (oldest first).
            The last entry may be a partial month and is excluded.
        month_labels: Optional month labels ("YYYY-MM" or "YYYY-MM-DD")
            for weekday normalization. If None, uses raw values.

    Returns:
        Dict with: trend ("growing"/"stable"/"declining"/"churned"/"new"),
        change_pct, early_avg, recent_avg, first_active_index, peak
    """
    # Normalize by weekdays before analysis
    normalized = _normalize_events(monthly_events, month_labels)

    # Exclude the last month (likely partial)
    full_months = normalized[:-1] if len(normalized) > 1 else normalized

    if not full_months or sum(full_months) == 0:
        return {
            "trend": "churned",
            "change_pct": 0,
            "early_avg": 0,
            "recent_avg": 0,
            "first_active_index": None,
            "peak": 0,
        }

    # Find first non-zero month
    first_active = next((i for i, v in enumerate(full_months) if v > 0), None)

    # Recent = last 2 full months
    recent_avg = sum(full_months[-2:]) / 2 if len(full_months) >= 2 else full_months[-1]

    # Early = first 2 active months
    if first_active is not None and first_active < len(full_months) - 2:
        early_slice = full_months[first_active : first_active + 2]
        early_avg = sum(early_slice) / len(early_slice)
    else:
        early_avg = recent_avg

    # Compute change
    if early_avg > 0:
        change_pct = ((recent_avg - early_avg) / early_avg) * 100
    else:
        change_pct = 100 if recent_avg > 0 else 0

    # Determine trend
    is_new = first_active is not None and first_active >= len(full_months) - 2
    if recent_avg == 0 and early_avg > 0:
        trend = "churned"
    elif is_new:
        trend = "new"
    elif change_pct >= 50:
        trend = "growing"
    elif change_pct <= -50:
        trend = "declining"
    else:
        trend = "stable"

    return {
        "trend": trend,
        "change_pct": round(change_pct, 1),
        "early_avg": round(early_avg, 1),
        "recent_avg": round(recent_avg, 1),
        "first_active_index": first_active,
        "peak": max(full_months),
    }


def classify_maturity(
    profile: AmplitudeProfile,
    historical: Optional[dict] = None,
    has_recent_jira_activity: bool = False,
) -> str:
    """Classify customer adoption stage using current state + trajectory.

    Stages:
        Scaling:            High usage (1000+/month) + growing or stable trend
        Established:        Medium-high usage (100+/month) + stable trend
        Expanding:          Medium usage (100+/month) + growing trend
        Exploring:          Low usage (<100/month) or new customer
        Reduced Visibility: Telemetry declining >50% — likely telemetry opt-out,
                            move to disconnected env, or prod cluster without telemetry
        Churned:            Was active, recent months are zero
        Migrated:           Declining/Churned in Amplitude but still active in Jira/support
                            cases (confirmed move to disconnected clusters)
        Unscored:           Not enough data (<10 total events)

    Args:
        profile: AmplitudeProfile with current-period data
        historical: Optional dict with 'monthly_events' list for trajectory.
            If None, classification uses current-period only (no trend).
        has_recent_jira_activity: If True and the customer would be classified
            as Declining/Churned, classify as "Migrated" instead (indicates
            the customer moved to disconnected clusters).

    Returns:
        Adoption stage string
    """
    if profile.unique_users is None or profile.total_events is None:
        return "Unscored"

    if profile.total_events < 10:
        return "Unscored"

    # Get trajectory if historical data available (normalized by weekdays)
    if historical and "monthly_events" in historical:
        month_labels = historical.get("month_labels")
        traj = compute_trajectory(historical["monthly_events"], month_labels)
    else:
        traj = {"trend": "stable", "change_pct": 0, "recent_avg": profile.total_events}

    trend = traj["trend"]
    recent = traj["recent_avg"]

    # Churned or Declining — check if customer migrated to disconnected
    if trend == "churned" or trend == "declining":
        if has_recent_jira_activity:
            return "Migrated"
        return "Churned" if trend == "churned" else "Reduced Visibility"

    # Scaling: high usage + growing or stable
    if recent >= 1000 and trend in ("growing", "stable"):
        return "Scaling"

    # Established: medium-high usage + stable
    if recent >= 100 and trend == "stable":
        return "Established"

    # Expanding: medium usage + growing
    if recent >= 100 and trend in ("growing", "new"):
        return "Expanding"

    # Exploring: low usage, new, or anything else
    if recent < 100 or trend == "new":
        return "Exploring"

    # Fallback
    return "Exploring"


def is_poc(profile: AmplitudeProfile) -> bool:
    """Determine if a customer is in POC/exploration mode.

    POC indicators:
    - Very few users (<=3) with low event volume (<100)
    - High create-to-open ratio (creating more workbenches than reopening)

    Args:
        profile: AmplitudeProfile with current-period data

    Returns:
        True if customer appears to be in POC mode
    """
    if profile.unique_users is None or profile.total_events is None:
        return False

    # Few users + low volume = POC
    if profile.unique_users <= 3 and profile.total_events < 100:
        return True

    # High create-to-open ratio = exploration (only meaningful for smaller deployments)
    fc = profile.feature_counts
    created = fc.get("Workbench Created", 0)
    opened = fc.get("Workbench Opened", 0)
    if (
        profile.unique_users <= 20
        and opened > 0
        and created > 0
        and (created / opened) > 0.5
    ):
        return True

    return False
