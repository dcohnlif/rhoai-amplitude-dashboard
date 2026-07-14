"""Tests for Amplitude customer trajectory-based classification."""

from src.analyzers.amplitude_classifier import (
    _normalize_events,
    _weekdays_in_month,
    classify_maturity,
    compute_trajectory,
    is_poc,
)
from src.models.amplitude import AmplitudeProfile


class TestWeekdayNormalization:
    def test_weekdays_in_february(self):
        # Feb 2026 has 20 weekdays
        assert _weekdays_in_month(2026, 2) == 20

    def test_weekdays_in_october(self):
        # Oct 2025 has 23 weekdays
        assert _weekdays_in_month(2025, 10) == 23

    def test_normalize_scales_short_month_up(self):
        # Feb (20 weekdays) should be scaled up to 22-day equivalent
        raw = [1000, 1000]  # Jan and Feb with same raw count
        labels = ["2026-01", "2026-02"]
        normalized = _normalize_events(raw, labels)
        assert normalized[1] > normalized[0]  # Feb scaled up

    def test_normalize_no_labels(self):
        raw = [100, 200, 300]
        normalized = _normalize_events(raw, None)
        assert normalized == raw  # Unchanged without labels

    def test_normalize_zero_stays_zero(self):
        raw = [0, 1000]
        labels = ["2026-01", "2026-02"]
        normalized = _normalize_events(raw, labels)
        assert normalized[0] == 0

    def test_normalize_prevents_false_decline(self):
        """A customer with flat daily usage should not appear as declining
        when comparing a 23-weekday month to a 20-weekday month."""
        # Same daily rate: 100 events per weekday
        jan_weekdays = _weekdays_in_month(2026, 1)  # 22
        feb_weekdays = _weekdays_in_month(2026, 2)  # 20
        raw = [jan_weekdays * 100, feb_weekdays * 100]  # 2200, 2000
        labels = ["2026-01", "2026-02"]
        normalized = _normalize_events(raw, labels)
        # After normalization, both should be ~2200 (22 * 100)
        assert abs(normalized[0] - normalized[1]) < 10


class TestComputeTrajectory:
    def test_growing(self):
        # Doubles over 6 months
        t = compute_trajectory([100, 120, 140, 160, 200, 250, 50])  # last is partial
        assert t["trend"] == "growing"
        assert t["change_pct"] > 50

    def test_stable(self):
        t = compute_trajectory([100, 110, 95, 105, 100, 105, 50])
        assert t["trend"] == "stable"

    def test_declining(self):
        t = compute_trajectory([1000, 900, 500, 300, 200, 100, 50])
        assert t["trend"] == "declining"
        assert t["change_pct"] < -50

    def test_churned(self):
        t = compute_trajectory([500, 600, 300, 100, 0, 0, 0])
        assert t["trend"] == "churned"
        assert t["recent_avg"] == 0

    def test_new_customer(self):
        t = compute_trajectory([0, 0, 0, 0, 0, 200, 50])
        assert t["trend"] == "new"

    def test_empty(self):
        t = compute_trajectory([0, 0, 0, 0, 0, 0, 0])
        assert t["trend"] == "churned"

    def test_single_month(self):
        """A single data point is classified as 'new' — not enough history."""
        t = compute_trajectory([100])
        assert t["trend"] == "new"

    def test_peak_tracking(self):
        t = compute_trajectory([100, 500, 200, 300, 150, 200, 50])
        assert t["peak"] == 500


class TestClassifyMaturity:
    def _profile(self, users=0, events=0, **feature_counts):
        return AmplitudeProfile(
            org_name="Test",
            unique_users=users,
            total_events=events,
            feature_counts=feature_counts,
        )

    def test_unscored_low_events(self):
        assert classify_maturity(self._profile(users=1, events=3)) == "Unscored"

    def test_unscored_none_users(self):
        p = AmplitudeProfile(org_name="Test")
        p.unique_users = None
        assert classify_maturity(p) == "Unscored"

    def test_scaling_with_trajectory(self):
        p = self._profile(users=80, events=5000)
        hist = {"monthly_events": [1000, 1500, 2000, 2500, 3000, 4000, 1000]}
        assert classify_maturity(p, historical=hist) == "Scaling"

    def test_established_with_trajectory(self):
        p = self._profile(users=50, events=3000)
        hist = {"monthly_events": [500, 500, 480, 510, 500, 520, 200]}
        assert classify_maturity(p, historical=hist) == "Established"

    def test_expanding_with_trajectory(self):
        p = self._profile(users=20, events=500)
        hist = {"monthly_events": [50, 80, 100, 150, 250, 400, 100]}
        assert classify_maturity(p, historical=hist) == "Expanding"

    def test_reduced_visibility_with_trajectory(self):
        p = self._profile(users=10, events=200)
        hist = {"monthly_events": [2000, 1800, 1000, 500, 300, 100, 50]}
        assert classify_maturity(p, historical=hist) == "Reduced Visibility"

    def test_churned_with_trajectory(self):
        p = self._profile(users=0, events=10)
        hist = {"monthly_events": [500, 600, 300, 100, 0, 0, 0]}
        assert classify_maturity(p, historical=hist) == "Churned"

    def test_migrated_declining_with_jira(self):
        """Declining Amplitude + active Jira = Migrated to disconnected."""
        p = self._profile(users=10, events=200)
        hist = {"monthly_events": [2000, 1800, 1000, 500, 300, 100, 50]}
        assert (
            classify_maturity(p, historical=hist, has_recent_jira_activity=True)
            == "Migrated"
        )

    def test_migrated_churned_with_jira(self):
        """Churned Amplitude + active Jira = Migrated to disconnected."""
        p = self._profile(users=0, events=10)
        hist = {"monthly_events": [500, 600, 300, 100, 0, 0, 0]}
        assert (
            classify_maturity(p, historical=hist, has_recent_jira_activity=True)
            == "Migrated"
        )

    def test_reduced_visibility_without_jira(self):
        """Reduced Visibility without Jira activity stays as-is (not Migrated)."""
        p = self._profile(users=10, events=200)
        hist = {"monthly_events": [2000, 1800, 1000, 500, 300, 100, 50]}
        assert (
            classify_maturity(p, historical=hist, has_recent_jira_activity=False)
            == "Reduced Visibility"
        )

    def test_exploring_without_trajectory(self):
        """Without historical data, low-usage customer gets Exploring."""
        p = self._profile(users=5, events=50)
        assert classify_maturity(p) == "Exploring"

    def test_established_without_trajectory(self):
        """Without historical data, medium-usage customer gets Established (stable default)."""
        p = self._profile(users=20, events=500)
        assert classify_maturity(p) == "Established"

    def test_scaling_without_trajectory(self):
        """Without historical data, high-usage customer gets Scaling (stable default)."""
        p = self._profile(users=50, events=5000)
        assert classify_maturity(p) == "Scaling"


class TestIsPoc:
    def _profile(self, users=0, events=0, **feature_counts):
        return AmplitudeProfile(
            org_name="Test",
            unique_users=users,
            total_events=events,
            feature_counts=feature_counts,
        )

    def test_few_users_low_events(self):
        assert is_poc(self._profile(users=2, events=30)) is True

    def test_many_users_not_poc(self):
        assert is_poc(self._profile(users=50, events=5000)) is False

    def test_high_create_to_open_ratio(self):
        p = self._profile(
            users=10,
            events=200,
            **{"Workbench Created": 20, "Workbench Opened": 30},
        )
        assert is_poc(p) is True

    def test_low_create_to_open_ratio(self):
        p = self._profile(
            users=10,
            events=200,
            **{"Workbench Created": 5, "Workbench Opened": 100},
        )
        assert is_poc(p) is False

    def test_none_values(self):
        p = AmplitudeProfile(org_name="Test")
        p.unique_users = None
        assert is_poc(p) is False

    def test_large_customer_high_ratio_not_poc(self):
        p = self._profile(
            users=100,
            events=50000,
            **{"Workbench Created": 60, "Workbench Opened": 100},
        )
        assert is_poc(p) is False
