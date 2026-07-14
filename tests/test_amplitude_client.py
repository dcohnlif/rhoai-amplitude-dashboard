"""Tests for the Amplitude REST API client."""

from unittest.mock import MagicMock, patch

import pytest

from src.extractors.amplitude_client import (
    AmplitudeAuthError,
    AmplitudeClient,
    TRACKED_EVENTS,
)


@pytest.fixture
def client():
    """Create an AmplitudeClient with test credentials."""
    return AmplitudeClient(api_key="test_key", secret_key="test_secret")


class TestAmplitudeClientInit:
    def test_init_with_explicit_keys(self):
        client = AmplitudeClient(api_key="key", secret_key="secret")
        assert client.api_key == "key"
        assert client.secret_key == "secret"
        assert client.app_id == "418474"

    def test_init_custom_app_id(self):
        client = AmplitudeClient(api_key="k", secret_key="s", app_id="999")
        assert client.app_id == "999"

    def test_init_custom_timeout(self):
        client = AmplitudeClient(api_key="k", secret_key="s", timeout=120)
        assert client.timeout == 120

    @patch.dict(
        "os.environ",
        {"AMPLITUDE_API_KEY": "env_key", "AMPLITUDE_SECRET_KEY": "env_secret"},
    )
    def test_from_env(self):
        client = AmplitudeClient.from_env()
        assert client.api_key == "env_key"
        assert client.secret_key == "env_secret"

    @patch.dict("os.environ", {}, clear=True)
    def test_from_env_missing_keys(self):
        # Clear any existing env vars
        import os

        os.environ.pop("AMPLITUDE_API_KEY", None)
        os.environ.pop("AMPLITUDE_SECRET_KEY", None)
        with pytest.raises(ValueError, match="AMPLITUDE_API_KEY"):
            AmplitudeClient.from_env()


class TestVerifyAuth:
    def test_verify_auth_success(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._session, "get", return_value=mock_response):
            assert client.verify_auth() is True

    def test_verify_auth_401(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch.object(client._session, "get", return_value=mock_response):
            with pytest.raises(AmplitudeAuthError):
                client.verify_auth()

    def test_verify_auth_403(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 403

        with patch.object(client._session, "get", return_value=mock_response):
            with pytest.raises(AmplitudeAuthError):
                client.verify_auth()


class TestGetCustomers:
    def _make_segmentation_response(self, labels_and_values):
        """Build a mock segmentation API response."""
        series = []
        series_labels = []
        for i, (label, values) in enumerate(labels_and_values):
            series_labels.append([i, {"label": label}])
            series.append(values)
        return {"data": {"series": series, "seriesLabels": series_labels}}

    def test_get_customers_basic(self, client):
        # With interval=days, we get a single bucket per customer
        users_response = self._make_segmentation_response(
            [
                ("Acme Corp", [15]),
                ("Beta Inc", [5]),
            ]
        )
        events_response = self._make_segmentation_response(
            [
                ("Acme Corp", [150]),
                ("Beta Inc", [30]),
            ]
        )

        call_count = 0

        def mock_query(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return users_response
            return events_response

        with patch.object(client, "_query_segmentation", side_effect=mock_query):
            with patch("time.sleep"):  # Skip rate limiting in tests
                customers = client.get_customers(days=30)

        assert len(customers) == 2
        assert customers[0]["org_name"] == "Acme Corp"
        assert customers[0]["total_events"] == 150
        # unique_users takes the single deduped bucket value, not a sum
        assert customers[0]["unique_users"] == 15
        assert customers[1]["org_name"] == "Beta Inc"

    def test_get_customers_empty(self, client):
        empty_response = {"data": {"series": [], "seriesLabels": []}}

        with patch.object(client, "_query_segmentation", return_value=empty_response):
            with patch("time.sleep"):
                customers = client.get_customers(days=30)

        assert customers == []


class TestGetFeatureUsage:
    def _make_response(self, labels_and_values):
        series = []
        series_labels = []
        for i, (label, values) in enumerate(labels_and_values):
            series_labels.append([i, {"label": label}])
            series.append(values)
        return {"data": {"series": series, "seriesLabels": series_labels}}

    def test_get_feature_usage(self, client):
        response = self._make_response(
            [
                ("Acme Corp", [10]),
                ("Beta Inc", [5]),
            ]
        )

        with patch.object(client, "_query_segmentation", return_value=response):
            with patch("time.sleep"):
                usage = client.get_feature_usage(days=30)

        # Should have entries for both customers
        assert "Acme Corp" in usage
        assert "Beta Inc" in usage
        # Each customer should have counts for each tracked event
        for event in TRACKED_EVENTS:
            assert event in usage.get("Acme Corp", {})

    def test_get_feature_usage_handles_api_errors(self, client):
        """API errors for individual events should be logged, not raised."""
        call_count = 0

        def mock_query(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 3:
                raise Exception("API error")
            return {"data": {"series": [], "seriesLabels": []}}

        with patch.object(client, "_query_segmentation", side_effect=mock_query):
            with patch("time.sleep"):
                usage = client.get_feature_usage(days=30)

        # Should not raise, should return partial data
        assert isinstance(usage, dict)


class TestQuerySegmentation:
    def test_query_segmentation_auth_error(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "unauthorized"}

        with patch.object(client._session, "get", return_value=mock_response):
            with pytest.raises(AmplitudeAuthError):
                client._query_segmentation(
                    event_type="_all",
                    metric="uniques",
                    group_by_property="10895",
                    start="20260601",
                    end="20260614",
                )

    def test_query_segmentation_success(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"series": [], "seriesLabels": []}}
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            client._session, "get", return_value=mock_response
        ) as mock_get:
            result = client._query_segmentation(
                event_type="Workbench Opened",
                metric="totals",
                group_by_property="10895",
                start="20260601",
                end="20260614",
            )

        assert result == {"data": {"series": [], "seriesLabels": []}}
        # Verify the request was made with correct params
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args
        assert "params" in call_kwargs.kwargs or len(call_kwargs.args) > 1
