"""Amplitude product analytics CLI commands.

Provides commands to sync RHOAI usage data from Amplitude
and cross-reference with existing customer data.
"""

import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta

import click

logger = logging.getLogger(__name__)


@click.group("amplitude")
def amplitude_group():
    """Amplitude product analytics integration."""
    pass


@amplitude_group.command("sync")
@click.option("--days", default=30, help="Time period to query (days)")
@click.option("--dry-run", is_flag=True, help="Preview without writing data")
@click.option("--min-events", default=10, help="Minimum events to include a customer")
@click.option("--data-dir", default="data", help="Data directory", envvar="DATA_DIR")
def amplitude_sync(days, dry_run, min_events, data_dir):
    """Sync RHOAI customer usage data from Amplitude."""
    from src.extractors.amplitude_client import AmplitudeAuthError, AmplitudeClient
    from src.models.amplitude import AmplitudeProfile

    api_key = os.getenv("AMPLITUDE_API_KEY")
    secret_key = os.getenv("AMPLITUDE_SECRET_KEY")

    if not api_key or not secret_key:
        click.echo(
            "ERROR: AMPLITUDE_API_KEY and AMPLITUDE_SECRET_KEY must be set.",
            err=True,
        )
        sys.exit(1)

    click.echo(f"Amplitude sync: querying last {days} days...")

    try:
        client = AmplitudeClient(api_key=api_key, secret_key=secret_key)
        client.verify_auth()
        click.echo("  Authentication: OK")
    except AmplitudeAuthError as e:
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)

    # Fetch customer list
    click.echo("  Fetching customer list...")
    customers = client.get_customers(days=days)
    click.echo(f"  Found {len(customers)} customers")

    # Filter by minimum events
    customers = [c for c in customers if c["total_events"] >= min_events]
    click.echo(f"  After filtering (>= {min_events} events): {len(customers)}")

    # Fetch feature usage
    click.echo("  Fetching feature usage (this may take a minute)...")
    feature_usage = client.get_feature_usage(days=days)
    click.echo(f"  Feature usage data for {len(feature_usage)} customers")

    if dry_run:
        click.echo("\n--- DRY RUN: No data will be written ---\n")

    # Build profiles and save
    now = datetime.now().isoformat(timespec="seconds")
    end = datetime.now()
    start = end - timedelta(days=days)

    saved = 0
    for customer in customers:
        org_name = customer["org_name"]
        features = feature_usage.get(org_name, {})

        profile = AmplitudeProfile(
            org_name=org_name,
            unique_users=customer.get("unique_users", 0),
            total_events=customer.get("total_events", 0),
            feature_counts=features,
            fetched_at=now,
            period_days=days,
            period_start=start.strftime("%Y-%m-%d"),
            period_end=end.strftime("%Y-%m-%d"),
        )

        if not dry_run:
            # Save to data/amplitude/{normalized_name}.json
            amplitude_dir = os.path.join(data_dir, "amplitude")
            os.makedirs(amplitude_dir, exist_ok=True)
            filename = _normalize_name(org_name) + ".json"
            filepath = os.path.join(amplitude_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(profile.to_dict(), f, indent=2)
            saved += 1
        else:
            # Print summary in dry-run mode
            top_features = sorted(features.items(), key=lambda x: x[1], reverse=True)[:3]
            features_str = (
                ", ".join(f"{k}: {v}" for k, v in top_features) if top_features else "none"
            )
            click.echo(
                f"  {org_name}: {customer['unique_users']} users, "
                f"{customer['total_events']} events [{features_str}]"
            )

    if not dry_run:
        click.echo(f"\n  Saved {saved} profiles to {data_dir}/amplitude/")

    click.echo(f"\nAmplitude sync complete: {len(customers)} customers processed")


@amplitude_group.command("list")
@click.option("--days", default=30, help="Time period to query (days)")
@click.option("--limit", default=50, help="Max customers to display")
def amplitude_list(days, limit):
    """List all RHOAI customers from Amplitude."""
    from src.extractors.amplitude_client import AmplitudeAuthError, AmplitudeClient

    api_key = os.getenv("AMPLITUDE_API_KEY")
    secret_key = os.getenv("AMPLITUDE_SECRET_KEY")

    if not api_key or not secret_key:
        click.echo(
            "ERROR: AMPLITUDE_API_KEY and AMPLITUDE_SECRET_KEY must be set.",
            err=True,
        )
        sys.exit(1)

    try:
        client = AmplitudeClient(api_key=api_key, secret_key=secret_key)
        customers = client.get_customers(days=days)
    except AmplitudeAuthError as e:
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)

    click.echo(f"\nRHOAI Customers from Amplitude (last {days} days):\n")
    click.echo(f"{'#':>3}  {'Customer':<55} {'Users':>6} {'Events':>8}")
    click.echo("-" * 78)

    for i, c in enumerate(customers[:limit], 1):
        click.echo(
            f"{i:>3}  {c['org_name'][:55]:<55} {c['unique_users']:>6} {c['total_events']:>8}"
        )

    if len(customers) > limit:
        click.echo(f"\n... and {len(customers) - limit} more (use --limit to show all)")

    click.echo(f"\nTotal: {len(customers)} customers")


@amplitude_group.command("backfill")
@click.option("--months", default=12, help="Number of months of history to fetch")
def amplitude_backfill(months):
    """Fetch historical monthly data for trajectory analysis.

    Downloads monthly event counts and user counts for all customers
    and saves to data/amplitude/historical_backfill.json. This enables
    the trajectory-based adoption stage classification (Scaling,
    Established, Expanding, Exploring, Reduced Visibility, etc.).

    Run this once before generating your first report. Re-run quarterly
    to refresh the historical data.
    """
    import time

    import requests

    from src.extractors.amplitude_client import AmplitudeAuthError, AmplitudeClient

    api_key = os.getenv("AMPLITUDE_API_KEY")
    secret_key = os.getenv("AMPLITUDE_SECRET_KEY")

    if not api_key or not secret_key:
        click.echo(
            "ERROR: AMPLITUDE_API_KEY and AMPLITUDE_SECRET_KEY must be set.",
            err=True,
        )
        sys.exit(1)

    try:
        client = AmplitudeClient(api_key=api_key, secret_key=secret_key)
        client.verify_auth()
        click.echo("Authentication: OK")
    except AmplitudeAuthError as e:
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)

    end = datetime.now()
    start = end - timedelta(days=months * 30)
    click.echo(
        f"Fetching {months} months of history "
        f"({start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')})..."
    )

    # Fetch monthly event totals
    click.echo("  Fetching monthly event totals...")
    session = requests.Session()
    session.auth = (api_key, secret_key)

    events_resp = session.get(
        "https://amplitude.com/api/2/events/segmentation",
        params={
            "e": json.dumps(
                {
                    "event_type": "_all",
                    "group_by": [{"type": "lookup", "value": "10895", "group_type": "User"}],
                    "filters": [
                        {
                            "subprop_type": "lookup",
                            "subprop_key": "10895",
                            "subprop_op": "does not contain",
                            "subprop_value": ["RedHat", "Red Hat"],
                        },
                        {
                            "subprop_type": "lookup",
                            "subprop_key": "10895",
                            "subprop_op": "is not",
                            "subprop_value": ["(none)"],
                        },
                    ],
                }
            ),
            "m": "totals",
            "start": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
            "i": "30",
            "limit": "300",
        },
        timeout=120,
    )
    events_resp.raise_for_status()
    events_data = events_resp.json()

    click.echo("  Fetching monthly user counts...")
    time.sleep(1)
    users_resp = session.get(
        "https://amplitude.com/api/2/events/segmentation",
        params={
            "e": json.dumps(
                {
                    "event_type": "_all",
                    "group_by": [{"type": "lookup", "value": "10895", "group_type": "User"}],
                    "filters": [
                        {
                            "subprop_type": "lookup",
                            "subprop_key": "10895",
                            "subprop_op": "does not contain",
                            "subprop_value": ["RedHat", "Red Hat"],
                        },
                        {
                            "subprop_type": "lookup",
                            "subprop_key": "10895",
                            "subprop_op": "is not",
                            "subprop_value": ["(none)"],
                        },
                    ],
                }
            ),
            "m": "uniques",
            "start": start.strftime("%Y%m%d"),
            "end": end.strftime("%Y%m%d"),
            "i": "30",
            "limit": "300",
        },
        timeout=120,
    )
    users_resp.raise_for_status()
    users_data = users_resp.json()

    from src.extractors.amplitude_client import _extract_label

    # Build backfill structure
    xvals = events_data["data"]["xValues"]
    backfill = {
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "months": xvals,
        "customers": {},
    }

    for i, label in enumerate(events_data["data"]["seriesLabels"]):
        org = _extract_label(label)
        if not org:
            continue
        backfill["customers"][org] = {
            "monthly_events": events_data["data"]["series"][i],
        }

    for i, label in enumerate(users_data["data"]["seriesLabels"]):
        org = _extract_label(label)
        if org in backfill["customers"]:
            backfill["customers"][org]["monthly_users"] = users_data["data"]["series"][i]

    # Add derived fields
    for org, cdata in backfill["customers"].items():
        events = cdata["monthly_events"]
        first_active = next((j for j, v in enumerate(events) if v > 0), None)
        cdata["first_active_month"] = xvals[first_active] if first_active is not None else None
        cdata["total_events_12mo"] = sum(events)
        cdata["peak_month_events"] = max(events) if events else 0

    os.makedirs("data/amplitude", exist_ok=True)
    with open("data/amplitude/historical_backfill.json", "w", encoding="utf-8") as f:
        json.dump(backfill, f, indent=2)

    click.echo(
        f"\nSaved {len(backfill['customers'])} customers, "
        f"{len(xvals)} months to data/amplitude/historical_backfill.json"
    )


@amplitude_group.command("report")
@click.option("--days", default=30, help="Time period to query (days)")
@click.option("--min-events", default=10, help="Minimum events to include a customer")
@click.option(
    "--output",
    default="amplitude-customer-profiles.html",
    help="Output HTML file path",
)
@click.option("--open", "open_browser", is_flag=True, help="Open report in browser")
def amplitude_report(days, min_events, output, open_browser):
    """Generate an HTML customer profiles report from Amplitude data."""
    from src.analyzers.amplitude_classifier import (
        classify_maturity,
        compute_trajectory,
        is_poc,
        load_historical_data,
    )
    from src.extractors.amplitude_client import AmplitudeAuthError, AmplitudeClient
    from src.extractors.amplitude_mapper import build_active_inactive_features
    from src.models.amplitude import AmplitudeProfile

    api_key = os.getenv("AMPLITUDE_API_KEY")
    secret_key = os.getenv("AMPLITUDE_SECRET_KEY")

    if not api_key or not secret_key:
        click.echo(
            "ERROR: AMPLITUDE_API_KEY and AMPLITUDE_SECRET_KEY must be set.",
            err=True,
        )
        sys.exit(1)

    click.echo(f"Amplitude report: querying last {days} days...")

    try:
        client = AmplitudeClient(api_key=api_key, secret_key=secret_key)
        client.verify_auth()
        click.echo("  Authentication: OK")
    except AmplitudeAuthError as e:
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)

    # Fetch data
    click.echo("  Fetching customer list...")
    customers = client.get_customers(days=days)
    total_raw = len(customers)
    click.echo(f"  Found {total_raw} customers")

    # Filter: blocklist, zero-user, min-events — in that order
    blocklist = _load_blocklist()
    customers = [
        c
        for c in customers
        if c["org_name"] not in blocklist
        and c.get("unique_users", 0) > 0
        and c["total_events"] >= min_events
    ]
    filtered_out = total_raw - len(customers)
    click.echo(
        f"  After filtering: {len(customers)} customers "
        f"({filtered_out} excluded: {len(blocklist)} blocklisted individuals, "
        f"plus entries with 0 users or <{min_events} events)"
    )

    click.echo("  Fetching feature usage (this may take a few minutes)...")
    feature_usage = client.get_feature_usage(days=days)
    click.echo(f"  Feature usage data for {len(feature_usage)} customers")

    # Fetch per-customer detail breakdowns
    click.echo("  Fetching customer details (runtimes, images, versions)...")
    runtime_breakdown = client.get_property_breakdown(
        "Model Deployed", "servingRuntimeName", days=days
    )
    image_breakdown = client.get_property_breakdown("Workbench Created", "imageName", days=days)
    # RHOAI-Version from OCM lookup table (property 14981) — real product version
    rhoai_version_breakdown = client.get_property_breakdown(
        "_all", "14981", property_type="lookup", days=days
    )
    click.echo(
        f"  Details: {len(runtime_breakdown)} with runtimes, "
        f"{len(image_breakdown)} with images, "
        f"{len(rhoai_version_breakdown)} with RHOAI versions"
    )

    # Load historical backfill for trajectory analysis
    historical = load_historical_data()
    if historical:
        click.echo(
            f"  Loaded historical data: {len(historical.get('customers', {}))} customers, "
            f"{len(historical.get('months', []))} months"
        )
    else:
        click.echo("  No historical backfill found — using current-period classification only")

    # Build Jira activity lookup for "Migrated" detection
    jira_active_orgs = _build_jira_activity_lookup()
    if jira_active_orgs:
        click.echo(f"  Loaded Jira activity for {len(jira_active_orgs)} customers")

    # Build profiles
    now = datetime.now()
    start = now - timedelta(days=days)
    profiles = []
    trajectory_matched = 0
    migrated_count = 0

    for c in customers:
        org_name = c["org_name"]
        fc = feature_usage.get(org_name, {})
        active, inactive = build_active_inactive_features(fc)

        p = AmplitudeProfile(
            org_name=org_name,
            unique_users=c.get("unique_users", 0),
            total_events=c.get("total_events", 0),
            feature_counts=fc,
            fetched_at=now.isoformat(timespec="seconds"),
            period_days=days,
            period_start=start.strftime("%Y-%m-%d"),
            period_end=now.strftime("%Y-%m-%d"),
            active_features=active,
            inactive_features=inactive,
        )

        # Get historical data for this customer if available
        hist_customer = historical.get("customers", {}).get(org_name)
        if hist_customer:
            trajectory_matched += 1
            # Attach month labels for weekday normalization in trajectory
            if "month_labels" not in hist_customer:
                hist_customer["month_labels"] = [m[:7] for m in historical.get("months", [])]

        # Check if this customer has recent Jira/support case activity
        has_jira = org_name in jira_active_orgs

        p.maturity_stage = classify_maturity(
            p, historical=hist_customer, has_recent_jira_activity=has_jira
        )
        # POC is incompatible with Scaling/Established/Expanding — override
        if p.maturity_stage in ("Scaling", "Established", "Expanding"):
            p.is_daily_use = True
        else:
            p.is_daily_use = not is_poc(p)
        if p.maturity_stage == "Migrated":
            migrated_count += 1

        # Attach detail breakdowns
        p._runtimes = runtime_breakdown.get(org_name, {})  # type: ignore[attr-defined]
        p._images = image_breakdown.get(org_name, {})  # type: ignore[attr-defined]
        p._rhoai_versions = rhoai_version_breakdown.get(org_name, {})  # type: ignore[attr-defined]

        # Attach monthly history for sparkline (normalized by weekdays)
        if hist_customer and "monthly_events" in hist_customer:
            raw_monthly = hist_customer["monthly_events"]
            month_labels = [m[:7] for m in historical.get("months", [])]
            normalized, is_partial = _normalize_monthly_events(raw_monthly, month_labels)
            p._monthly_events = raw_monthly  # type: ignore[attr-defined]
            p._monthly_normalized = normalized  # type: ignore[attr-defined]
            p._monthly_labels = month_labels  # type: ignore[attr-defined]
            p._monthly_partial = is_partial  # type: ignore[attr-defined]
        else:
            p._monthly_events = []  # type: ignore[attr-defined]
            p._monthly_normalized = []  # type: ignore[attr-defined]
            p._monthly_labels = []  # type: ignore[attr-defined]
            p._monthly_partial = []  # type: ignore[attr-defined]

        # Compute trajectory reason for tooltip
        if hist_customer and "monthly_events" in hist_customer:
            traj = compute_trajectory(
                hist_customer["monthly_events"],
                hist_customer.get("month_labels"),
            )
            p._stage_reason = _build_stage_reason(  # type: ignore[attr-defined]
                p.maturity_stage, traj, has_jira, p.unique_users, p.total_events
            )
        else:
            p._stage_reason = _build_stage_reason(  # type: ignore[attr-defined]
                p.maturity_stage, None, has_jira, p.unique_users, p.total_events
            )

        profiles.append(p)

    profiles.sort(key=lambda p: p.total_events, reverse=True)
    migrated_msg = f", {migrated_count} migrated to disconnected" if migrated_count else ""
    click.echo(
        f"  Built {len(profiles)} customer profiles "
        f"({trajectory_matched} with trajectory data{migrated_msg})"
    )

    # Generate HTML
    html = _generate_report_html(
        profiles=profiles,
        period_start=start.strftime("%Y-%m-%d"),
        period_end=now.strftime("%Y-%m-%d"),
        generated_at=now.strftime("%Y-%m-%d %H:%M"),
        days=days,
        filtered_out=filtered_out,
    )

    with open(output, "w", encoding="utf-8") as f:
        f.write(html)

    click.echo(f"\nReport saved to {output} ({len(html):,} bytes)")

    if open_browser:
        import subprocess

        try:
            subprocess.Popen(["xdg-open", output])  # noqa: S603
        except FileNotFoundError:
            try:
                subprocess.Popen(["open", output])  # noqa: S603
            except FileNotFoundError:
                click.echo(f"  Could not open browser. Open manually: {output}")


def _build_jira_activity_lookup() -> set[str]:
    """Build a set of Amplitude org_names that have recent Jira/support case activity.

    Cross-references the manual mapping YAML with customer support case data
    to find customers who filed cases in the last 90 days.

    Returns:
        Set of Amplitude org_names with recent Jira activity
    """
    import yaml

    result = set()

    # Load manual mapping (org_name -> customer_id)
    mapping_path = os.path.join("config", "amplitude_account_mapping.yaml")
    if not os.path.isfile(mapping_path):
        return result
    try:
        with open(mapping_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
            mapping = cfg.get("mappings", {})
    except Exception:
        return result

    # For each mapped customer, check if they have support cases
    customers_dir = os.path.join("data", "customers")
    for org_name, customer_id in mapping.items():
        cases_path = os.path.join(customers_dir, customer_id, "support_cases", "cases.json")
        if not os.path.isfile(cases_path):
            continue
        try:
            with open(cases_path, "r", encoding="utf-8") as f:
                cases_data = json.load(f)
            case_count = cases_data.get("filtered_count", 0)
            if case_count and case_count > 0:
                result.add(org_name)
        except (json.JSONDecodeError, OSError):
            pass

    return result


def _load_blocklist() -> set[str]:
    """Load the Amplitude org_name blocklist.

    Returns set of org_names to exclude (individuals, not customers).
    """
    import yaml

    path = os.path.join("config", "amplitude_blocklist.yaml")
    if not os.path.isfile(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
            return set(cfg.get("blocklist", []))
    except Exception:
        return set()


def _weekdays_in_month(year: int, month: int, up_to_day: int | None = None) -> int:
    """Count weekdays (Mon-Fri) in a month, optionally up to a specific day.

    Args:
        year: Year
        month: Month (1-12)
        up_to_day: If set, count weekdays only up to this day (for partial months)

    Returns:
        Number of weekdays
    """
    import calendar

    last_day = up_to_day or calendar.monthrange(year, month)[1]
    return sum(1 for d in range(1, last_day + 1) if calendar.weekday(year, month, d) < 5)


# Average weekdays per month (for normalization baseline)
_AVG_WEEKDAYS = 22


def _normalize_monthly_events(
    raw_events: list[int],
    month_labels: list[str],
) -> tuple[list[int], list[bool]]:
    """Normalize monthly event counts by weekdays per month.

    Adjusts for months with different numbers of working days (Feb=20 vs Oct=23)
    and marks the current (partial) month.

    Args:
        raw_events: Raw monthly event counts
        month_labels: Month labels as "YYYY-MM" strings

    Returns:
        Tuple of (normalized_events, is_partial_flags)
    """
    from datetime import datetime

    now = datetime.now()
    current_month = now.strftime("%Y-%m")
    normalized = []
    is_partial = []

    for i, raw in enumerate(raw_events):
        if i >= len(month_labels):
            normalized.append(raw)
            is_partial.append(False)
            continue

        label = month_labels[i]
        try:
            year = int(label[:4])
            month = int(label[5:7])
        except (ValueError, IndexError):
            normalized.append(raw)
            is_partial.append(False)
            continue

        partial = label == current_month
        is_partial.append(partial)

        if raw == 0:
            normalized.append(0)
            continue

        if partial:
            # Partial month: normalize by elapsed weekdays
            weekdays = _weekdays_in_month(year, month, up_to_day=now.day)
        else:
            weekdays = _weekdays_in_month(year, month)

        if weekdays > 0:
            # Scale to a standard 22-weekday month
            normalized.append(int(raw * _AVG_WEEKDAYS / weekdays))
        else:
            normalized.append(raw)

    return normalized, is_partial


def _build_stage_reason(
    stage: str,
    trajectory: dict | None,
    has_jira: bool,
    users: int,
    events: int,
) -> str:
    """Build a human-readable explanation of why a customer got this stage.

    Args:
        stage: The assigned adoption stage
        trajectory: Dict from compute_trajectory() or None
        has_jira: Whether the customer has recent Jira/support case activity
        users: Unique user count for the period
        events: Total event count for the period

    Returns:
        Tooltip text explaining the classification
    """
    if trajectory:
        change = trajectory["change_pct"]
        early = trajectory["early_avg"]
        recent = trajectory["recent_avg"]
        peak = trajectory["peak"]
        trend_desc = (
            f"Trend: {change:+.0f}% "
            f"(early avg {early:,.0f} → recent avg {recent:,.0f}/month, peak {peak:,.0f})"
        )
    else:
        trend_desc = "No historical data — classified on current period only"

    reasons = {
        "Scaling": f"High usage ({events:,} events, {users} users) with growing/stable trend. {trend_desc}",
        "Established": f"Steady usage ({events:,} events, {users} users) with stable trend. {trend_desc}",
        "Expanding": f"Growing usage ({events:,} events, {users} users). {trend_desc}",
        "Exploring": f"Low usage ({events:,} events, {users} users) or new customer. {trend_desc}",
        "Reduced Visibility": f"Telemetry declining — likely telemetry opt-out, move to disconnected environment, or production cluster without telemetry enabled. Does NOT necessarily mean the customer stopped using RHOAI. {trend_desc}",
        "Churned": f"Was active but recent months show zero events. {trend_desc}",
        "Migrated": (
            f"Amplitude usage declining but still filing support cases — "
            f"likely moved to disconnected/air-gapped clusters. {trend_desc}"
        ),
        "Unscored": f"Not enough data ({events:,} events, {users} users).",
    }
    return reasons.get(stage, f"{stage}: {trend_desc}")


def _normalize_name(name: str) -> str:
    """Normalize an org name to a filesystem-safe identifier."""
    normalized = re.sub(r"[^\w\s-]", "", name.lower())
    normalized = re.sub(r"[\s-]+", "_", normalized.strip())
    return normalized[:80]  # Cap length


def _generate_report_html(
    profiles: list,
    period_start: str,
    period_end: str,
    generated_at: str,
    days: int = 30,
    filtered_out: int = 0,
) -> str:
    """Generate an HTML customer profiles report from Amplitude data.

    Args:
        profiles: List of AmplitudeProfile objects (with maturity_stage and is_daily_use set)
        period_start: Start date string (YYYY-MM-DD)
        period_end: End date string (YYYY-MM-DD)
        generated_at: ISO timestamp of report generation
        days: Number of days in the query period
        filtered_out: Number of entries excluded (individuals, automated-only)

    Returns:
        Complete HTML string
    """
    from src.extractors.amplitude_mapper import EVENT_TO_PATTERN

    total = len(profiles)
    stages: dict[str, int] = {}
    for p in profiles:
        s = p.maturity_stage or "unknown"
        # Normalize EoA labels for badge CSS classes
        stages[s] = stages.get(s, 0) + 1

    total_users = sum(p.unique_users for p in profiles)
    total_events = sum(p.total_events for p in profiles)

    # All defined categories (from EVENT_TO_PATTERN component_hints)
    all_categories = sorted({v["component_hint"] for v in EVENT_TO_PATTERN.values()})

    feature_adoption: dict[str, int] = {cat: 0 for cat in all_categories}
    for p in profiles:
        for f in p.active_features:
            if f in feature_adoption:
                feature_adoption[f] += 1
            else:
                feature_adoption[f] = 1
    feature_adoption_sorted = sorted(feature_adoption.items(), key=lambda x: -x[1])

    # Build adoption pills — show all categories including 0%
    adoption_html = ""
    for feat, count in feature_adoption_sorted:
        pct = count / total * 100 if total > 0 else 0
        cls = "pill-high" if pct > 40 else ("pill-med" if pct > 15 else "pill-low")
        if count == 0:
            cls = "pill-zero"
        adoption_html += (
            f'  <span class="adoption-pill {cls}">{feat}<br>{count} ({pct:.0f}%)</span>\n'
        )

    # Build customer cards
    cards_html = ""
    for p in profiles:
        # Map stage to CSS class and filter value
        raw_stage = p.maturity_stage or "Unscored"
        stage_slug = raw_stage.lower().replace(" ", "-")
        badge_cls = f"badge-{stage_slug}"
        filter_stage = stage_slug
        display_stage = raw_stage

        # Get tooltip reason (set during profile building)
        stage_reason = getattr(p, "_stage_reason", "")
        # Escape quotes for HTML attribute
        stage_tooltip = stage_reason.replace('"', "&quot;").replace("'", "&#39;")

        poc_badge = '<span class="card-badge badge-poc">POC</span>' if not p.is_daily_use else ""

        # Top features by count (non-zero only)
        top_fc = sorted(
            [(k, v) for k, v in p.feature_counts.items() if v > 0],
            key=lambda x: -x[1],
        )[:6]

        fc_html = ""
        if top_fc:
            fc_html = '<div class="top-features">\n'
            for fname, fcount in top_fc:
                short = (
                    fname.replace("Available Endpoints ", "AE: ")
                    .replace("Evaluations ", "Eval: ")
                    .replace("Playground ", "")
                    .replace("RBAC Role ", "RBAC: ")
                )
                fc_html += (
                    f'  <span class="top-feat">'
                    f'<span class="top-feat-name">{short}</span>'
                    f'<span class="top-feat-count">{fcount:,}</span>'
                    f"</span>\n"
                )
            fc_html += "</div>\n"

        active_tags = "".join(f'<span class="tag tag-active">{f}</span>' for f in p.active_features)
        inactive_tags = "".join(
            f'<span class="tag tag-inactive">{f}</span>' for f in p.inactive_features
        )
        features_text = " ".join(p.active_features + p.inactive_features).lower()

        tracked_events = sum(p.feature_counts.values())

        # Build sparkline (monthly history bar chart, normalized by weekdays)
        raw_monthly = getattr(p, "_monthly_events", [])
        norm_monthly = getattr(p, "_monthly_normalized", [])
        hist_months = getattr(p, "_monthly_labels", [])
        partial_flags = getattr(p, "_monthly_partial", [])
        sparkline_html = ""
        if norm_monthly and len(norm_monthly) >= 3:
            peak = max(norm_monthly) if max(norm_monthly) > 0 else 1
            bars = ""
            for j, norm_val in enumerate(norm_monthly):
                raw_val = raw_monthly[j] if j < len(raw_monthly) else 0
                is_partial = partial_flags[j] if j < len(partial_flags) else False
                height_pct = max(2, int(norm_val / peak * 100))

                if is_partial:
                    color = "#3a3a5a"  # Blue-ish for partial
                    style = f"height:{height_pct}%;background:repeating-linear-gradient(45deg,{color},{color} 2px,#2a2a3a 2px,#2a2a3a 4px)"
                elif norm_val == 0:
                    color = "#2a2a2a"
                    style = f"height:{height_pct}%;background:{color}"
                elif j >= len(norm_monthly) - 2:
                    style = f"height:{height_pct}%;background:#4a7a4a"
                else:
                    style = f"height:{height_pct}%;background:#3a3a3a"

                month_label = hist_months[j] if j < len(hist_months) else f"M{j}"
                partial_note = " (partial)" if is_partial else ""
                norm_note = f" (adj: {norm_val:,})" if norm_val != raw_val else ""
                bars += (
                    f'<span class="sparkline-bar" style="{style}">'
                    f'<span class="spark-tip">{month_label}: {raw_val:,}{norm_note}{partial_note}</span></span>'
                )
            first_month = hist_months[0] if hist_months else ""
            last_month = hist_months[-1] if hist_months else ""
            sparkline_html = (
                f'<div class="sparkline">{bars}</div>'
                f'<div class="sparkline-label"><span>{first_month}</span><span>{last_month}</span></div>'
            )

        # Build expandable details section
        runtimes = getattr(p, "_runtimes", {})
        images = getattr(p, "_images", {})
        rhoai_versions = getattr(p, "_rhoai_versions", {})
        has_details = runtimes or images or rhoai_versions

        details_html = ""
        if has_details:
            sections = ""

            if rhoai_versions:
                ver_items = ", ".join(
                    f"RHOAI {v} ({c} users)"
                    for v, c in sorted(rhoai_versions.items(), key=lambda x: -x[1])
                )
                sections += (
                    f'<div class="detail-section">'
                    f'<div class="detail-label">RHOAI Version</div>'
                    f'<div class="detail-items">{ver_items}</div></div>\n'
                )

            if runtimes:
                rt_items = sorted(runtimes.items(), key=lambda x: -x[1])
                rt_html = "<br>".join(f"{name} ({count})" for name, count in rt_items[:10])
                if len(rt_items) > 10:
                    rt_html += f"<br><em>+{len(rt_items) - 10} more</em>"
                sections += (
                    f'<div class="detail-section">'
                    f'<div class="detail-label">Serving Runtimes / Models</div>'
                    f'<div class="detail-items">{rt_html}</div></div>\n'
                )

            if images:
                img_items = ", ".join(
                    f"{name} ({count})"
                    for name, count in sorted(images.items(), key=lambda x: -x[1])[:8]
                )
                sections += (
                    f'<div class="detail-section">'
                    f'<div class="detail-label">Workbench Images</div>'
                    f'<div class="detail-items">{img_items}</div></div>\n'
                )

            detail_parts = []
            if rhoai_versions:
                detail_parts.append(f"{len(rhoai_versions)} version(s)")
            if runtimes:
                detail_parts.append(f"{len(runtimes)} runtimes")
            if images:
                detail_parts.append(f"{len(images)} images")
            detail_summary = ", ".join(detail_parts)

            details_html = (
                f'<div class="details">'
                f'<span class="details-toggle" onclick="this.nextElementSibling.classList.toggle(\'open\')">'
                f"▸ Details ({detail_summary})</span>"
                f'<div class="details-content">{sections}</div></div>\n'
            )

        cards_html += f'''<div class="card" data-stage="{filter_stage}" data-name="{p.org_name.lower()} {features_text}">
  <div class="card-header">
    <span class="card-name">{p.org_name}</span>
    <div class="card-badges"><span class="card-badge badge-stage {badge_cls}">{display_stage}<span class="tooltip">{stage_tooltip}</span></span>{poc_badge}</div>
  </div>
  <div class="card-metrics">
    <span class="metric"><span class="metric-label">Users:</span> <span class="metric-value">{p.unique_users}</span></span>
    <span class="metric"><span class="metric-label">Events:</span> <span class="metric-value">{p.total_events:,}</span></span>
    <span class="metric"><span class="metric-label">Tracked:</span> <span class="metric-value">{tracked_events:,}</span></span>
  </div>
  {fc_html}
  <div class="features-row">
    <div class="features-label">Active</div>
    <div class="tags">{active_tags or '<span style="color:#444;font-size:10px;">none detected</span>'}</div>
  </div>
  <div class="features-row" style="margin-top:4px;">
    <div class="features-label">Not Used</div>
    <div class="tags">{inactive_tags or '<span style="color:#444;font-size:10px;">&mdash;</span>'}</div>
  </div>
  {sparkline_html}
  {details_html}
</div>
'''

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>RHOAI Customer Profiles &mdash; Amplitude Data</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #111; color: #e0e0e0; padding: 32px; line-height: 1.5; }}
h1 {{ font-size: 24px; font-weight: 600; margin-bottom: 4px; }}
h2 {{ font-size: 18px; font-weight: 600; margin: 24px 0 12px; color: #ccc; }}
.subtitle {{ color: #888; font-size: 13px; margin-bottom: 24px; }}
.stats {{ display: grid; grid-template-columns: repeat(7, 1fr); gap: 12px; margin-bottom: 24px; }}
.stat {{ background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 16px; }}
.stat {{ display: flex; flex-direction: column-reverse; }}
.stat-value {{ font-size: 28px; font-weight: 700; color: #fff; }}
.stat-label {{ font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px; }}
.adoption {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 24px; justify-content: center; }}
.adoption-pill {{ padding: 6px 14px; border-radius: 16px; font-size: 12px; font-weight: 500; text-align: center; line-height: 1.4; }}
.pill-high {{ background: #1a3a1a; color: #6fcf6f; border: 1px solid #2a5a2a; }}
.pill-med {{ background: #2a2a1a; color: #cfcf6f; border: 1px solid #4a4a2a; }}
.pill-low {{ background: #2a1a1a; color: #cf6f6f; border: 1px solid #4a2a2a; }}
.pill-zero {{ background: #1a1a1a; color: #555; border: 1px solid #333; }}
hr {{ border: none; border-top: 1px solid #333; margin: 20px 0; }}
.search {{ width: 100%; padding: 10px 14px; border-radius: 6px; border: 1px solid #333; background: #1a1a1a; color: #e0e0e0; font-size: 14px; margin-bottom: 8px; }}
.search:focus {{ outline: none; border-color: #555; }}
.search::placeholder {{ color: #555; }}
.filters {{ display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }}
.filter-btn {{ padding: 5px 12px; border-radius: 14px; font-size: 12px; cursor: pointer; border: 1px solid #444; background: transparent; color: #aaa; }}
.filter-btn:hover {{ border-color: #666; color: #fff; }}
.filter-btn.active {{ background: #e0e0e0; color: #111; border-color: #e0e0e0; font-weight: 600; }}
.count {{ font-size: 12px; color: #666; margin-bottom: 12px; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 16px; }}
.card {{ background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 8px; padding: 16px; }}
.card:hover {{ border-color: #444; }}
.card-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px; }}
.card-name {{ font-size: 14px; font-weight: 600; color: #fff; max-width: 65%; }}
.card-badges {{ display: flex; gap: 4px; flex-shrink: 0; }}
.card-badge {{ font-size: 10px; padding: 3px 8px; border-radius: 10px; font-weight: 600; text-transform: uppercase; white-space: nowrap; }}
.badge-scaling {{ background: #1a3a1a; color: #6fcf6f; }}
.badge-established {{ background: #1a2a3a; color: #6fafcf; }}
.badge-expanding {{ background: #1a3a2a; color: #6fcfaf; }}
.badge-exploring {{ background: #2a2a1a; color: #cfcf6f; }}
.badge-declining {{ background: #3a2a1a; color: #cf8f6f; }}
.badge-reduced-visibility {{ background: #2a2a1a; color: #cfaf6f; }}
.badge-churned {{ background: #3a1a1a; color: #cf6f6f; }}
.badge-migrated {{ background: #2a1a3a; color: #af8fcf; }}
.badge-unscored {{ background: #2a2a2a; color: #888; }}
.badge-poc {{ background: #3a2a1a; color: #cfa06f; }}
.badge-stage {{ position: relative; cursor: help; }}
.badge-stage .tooltip {{ visibility: hidden; opacity: 0; position: absolute; bottom: 125%; right: 0; background: #333; color: #e0e0e0; padding: 8px 12px; border-radius: 6px; font-size: 11px; font-weight: 400; text-transform: none; letter-spacing: 0; white-space: normal; width: 300px; line-height: 1.5; z-index: 10; box-shadow: 0 2px 8px rgba(0,0,0,0.4); transition: opacity 0.15s; }}
.badge-stage:hover .tooltip {{ visibility: visible; opacity: 1; }}
.sparkline {{ display: flex; align-items: flex-end; gap: 2px; height: 32px; margin-top: 8px; }}
.sparkline-bar {{ flex: 1; min-width: 4px; border-radius: 2px 2px 0 0; transition: opacity 0.15s; position: relative; }}
.sparkline-bar:hover {{ opacity: 0.8; }}
.sparkline-bar .spark-tip {{ visibility: hidden; opacity: 0; position: absolute; bottom: 105%; left: 50%; transform: translateX(-50%); background: #333; color: #e0e0e0; padding: 3px 6px; border-radius: 4px; font-size: 9px; white-space: nowrap; z-index: 5; }}
.sparkline-bar:hover .spark-tip {{ visibility: visible; opacity: 1; }}
.sparkline-label {{ display: flex; justify-content: space-between; font-size: 9px; color: #555; margin-top: 2px; }}
.details {{ margin-top: 8px; border-top: 1px solid #2a2a2a; padding-top: 8px; }}
.details-toggle {{ font-size: 11px; color: #666; cursor: pointer; user-select: none; }}
.details-toggle:hover {{ color: #aaa; }}
.details-content {{ display: none; margin-top: 6px; }}
.details-content.open {{ display: block; }}
.detail-section {{ margin-bottom: 6px; }}
.detail-label {{ font-size: 10px; color: #555; text-transform: uppercase; letter-spacing: 0.5px; }}
.detail-items {{ font-size: 11px; color: #bbb; line-height: 1.6; }}
.card-metrics {{ display: flex; gap: 16px; margin-bottom: 10px; }}
.metric {{ font-size: 12px; }}
.metric-label {{ color: #666; }}
.metric-value {{ color: #ccc; font-weight: 500; }}
.tags {{ display: flex; gap: 4px; flex-wrap: wrap; }}
.tag {{ font-size: 10px; padding: 2px 8px; border-radius: 8px; }}
.tag-active {{ background: #1a2a1a; color: #8fcf8f; }}
.tag-inactive {{ background: #1a1a1a; color: #555; text-decoration: line-through; }}
.features-row {{ margin-top: 8px; }}
.features-label {{ font-size: 10px; color: #555; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }}
.top-features {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 4px 12px; margin-bottom: 8px; }}
.top-feat {{ font-size: 11px; display: flex; justify-content: space-between; }}
.top-feat-name {{ color: #999; }}
.top-feat-count {{ color: #ccc; font-weight: 500; font-variant-numeric: tabular-nums; }}
.callout {{ margin-top: 24px; padding: 14px 16px; border-radius: 8px; background: #1a2a3a; border-left: 3px solid #4a9eff; }}
.callout-title {{ font-size: 13px; font-weight: 600; color: #7ab8ff; margin-bottom: 4px; }}
.callout-body {{ font-size: 12px; color: #99c4e8; line-height: 1.6; }}
.brand-bar {{ display: flex; align-items: center; gap: 12px; padding: 12px 0; margin-bottom: 20px; border-bottom: 2px solid #e00; }}
.brand-logo {{ height: 28px; }}
.brand-text {{ display: flex; flex-direction: column; gap: 1px; }}
.brand-team {{ font-size: 11px; color: #999; text-transform: uppercase; letter-spacing: 0.5px; }}
.brand-tool {{ font-size: 14px; font-weight: 600; color: #e0e0e0; }}
@media (max-width: 768px) {{ body {{ padding: 16px; }} .stats {{ grid-template-columns: repeat(3, 1fr); }} .cards {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<div class="brand-bar">
  <img src="https://www.redhat.com/profiles/rh/themes/redhatdotcom/img/logo.svg" alt="Red Hat" class="brand-logo" onerror="this.style.display='none'">
  <div class="brand-text">
    <span class="brand-team">Workflow Validation Team</span>
    <span class="brand-tool">RHOAI Customer Profiles &mdash; Amplitude Data</span>
  </div>
</div>
<p class="subtitle">Generated: {generated_at}</p>

<div class="callout" style="margin-bottom:20px;">
  <div class="callout-body" style="font-size:13px;">
    <strong>Data period: {period_start} to {period_end}</strong> ({days} days) &mdash; adoption stages use <strong>12-month trajectory</strong> (historical backfill).<br>
    <strong>Source</strong>: Amplitude "RHODS Instances" project &middot; tracking 12 RHOAI feature areas (Workbenches, Model Serving, Data Science Pipelines, RBAC, Playground, Evaluations, Model Registry, Available Endpoints, Guardrails, Model Catalog, Projects, Application).<br>
    <strong>Connected clusters only</strong> &mdash; customers on disconnected/air-gapped clusters are not visible.<br>
    <strong>Important</strong>: "Reduced Visibility" does NOT mean the customer stopped using RHOAI. Per the Customer Adoption Innovation team, ~99% of telemetry drops are caused by telemetry opt-out, move to disconnected environments, or production clusters without telemetry enabled. Many customers (especially providers like Cisco, Dell, Wipro) do POCs on connected clusters then deploy on disconnected.<br>
    <strong>Multinational companies</strong> (Cisco, IBM, Dell) may appear multiple times &mdash; Red Hat tracks each subsidiary or country office as a separate account.<br>
    <strong>Events vs Tracked</strong>: "Events" = all Amplitude events (incl. page views). "Tracked" = sum of the 49 feature events we map to categories.<br>
    <strong>Filtered</strong>: {filtered_out} entries excluded (individual developer accounts, automated-only clusters with no interactive users).
  </div>
</div>

<div class="stats">
  <div class="stat"><span class="stat-value">{total}</span><span class="stat-label">Customers</span></div>
  <div class="stat"><span class="stat-value">{total_users:,}</span><span class="stat-label">Total Users</span></div>
  <div class="stat"><span class="stat-value">{total_events:,}</span><span class="stat-label">Total Events ({days}d)</span></div>
  <div class="stat"><span class="stat-value">{stages.get("Scaling", 0) + stages.get("Established", 0) + stages.get("Expanding", 0)}</span><span class="stat-label">Active</span></div>
  <div class="stat"><span class="stat-value">{stages.get("Exploring", 0) + stages.get("Unscored", 0)}</span><span class="stat-label">Exploring</span></div>
  <div class="stat"><span class="stat-value">{stages.get("Reduced Visibility", 0) + stages.get("Churned", 0)}</span><span class="stat-label">Reduced Visibility</span></div>
  <div class="stat"><span class="stat-value">{stages.get("Migrated", 0)}</span><span class="stat-label">Migrated</span></div>
</div>

<h2>Feature Adoption ({len(feature_adoption_sorted)} categories)</h2>
<div class="adoption">
{adoption_html}</div>
<hr>

<input type="text" class="search" id="search" placeholder="Search by customer name or feature...">
<div class="filters">
  <span style="font-size:12px;color:#666;margin-right:4px;">Stage:</span>
  <button class="filter-btn active" data-filter="all">All</button>
  <button class="filter-btn" data-filter="scaling">Scaling</button>
  <button class="filter-btn" data-filter="established">Established</button>
  <button class="filter-btn" data-filter="expanding">Expanding</button>
  <button class="filter-btn" data-filter="exploring">Exploring</button>
  <button class="filter-btn" data-filter="reduced-visibility">Reduced Visibility</button>
  <button class="filter-btn" data-filter="churned">Churned</button>
  <button class="filter-btn" data-filter="migrated">Migrated</button>
</div>
<p class="count" id="count"></p>

<div class="cards" id="cards">
{cards_html}</div>

<div class="callout">
  <div class="callout-title">Adoption stage definitions</div>
  <div class="callout-body">
    Stages combine <strong>current monthly usage</strong> with <strong>12-month trajectory</strong> (direction of change):<br>
    <strong>Scaling</strong> &mdash; 1000+ events/month, growing or stable trend.<br>
    <strong>Established</strong> &mdash; 100+ events/month, stable trend.<br>
    <strong>Expanding</strong> &mdash; 100+ events/month, growing trend (&gt;50% increase).<br>
    <strong>Exploring</strong> &mdash; &lt;100 events/month, or new customer (first appeared in the last 2 months).<br>
    <strong>Reduced Visibility</strong> &mdash; &gt;50% telemetry drop from earlier months. Usually telemetry opt-out, disconnected migration, or prod cluster without telemetry &mdash; NOT necessarily reduced RHOAI usage.<br>
    <strong>Churned</strong> &mdash; was active, recent months are zero, no Jira/support case activity.<br>
    <strong>Migrated</strong> &mdash; telemetry declining but still filing Jira/support cases. Confirmed move from connected to disconnected/air-gapped clusters.<br>
    <br>
    <strong>POC</strong> tag &mdash; added alongside the stage when the customer appears to be evaluating rather than in production use. Criteria: &le;3 unique users with &lt;100 events, or high workbench create-to-open ratio (&gt;50%, indicating exploration rather than established workflows) with &le;20 users. POC is never applied to Scaling, Established, or Expanding customers.
  </div>
</div>

<script>
const cards = document.querySelectorAll('.card');
const search = document.getElementById('search');
const countEl = document.getElementById('count');
let activeFilter = 'all';

function update() {{
  const q = search.value.toLowerCase();
  let shown = 0;
  cards.forEach(c => {{
    const matchStage = activeFilter === 'all' || c.dataset.stage === activeFilter;
    const matchSearch = !q || c.dataset.name.includes(q);
    c.style.display = matchStage && matchSearch ? '' : 'none';
    if (matchStage && matchSearch) shown++;
  }});
  countEl.textContent = `Showing ${{shown}} of {total} customers`;
}}

document.querySelectorAll('.filter-btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeFilter = btn.dataset.filter;
    update();
  }});
}});
search.addEventListener('input', update);
update();
</script>
</body>
</html>"""
