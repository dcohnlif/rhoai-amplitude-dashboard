"""Tests for the Amplitude event-to-pattern mapper."""

from unittest.mock import MagicMock

from src.extractors.amplitude_mapper import (
    EVENT_TO_PATTERN,
    map_feature_usage_to_patterns,
)


class TestEventToPatternMapping:
    def test_all_tracked_events_have_required_fields(self):
        required_fields = {
            "component_hint",
            "stage",
            "pattern_title",
            "min_threshold",
            "evidence",
        }
        for event_name, mapping in EVENT_TO_PATTERN.items():
            for field in required_fields:
                assert field in mapping, f"Event '{event_name}' missing field '{field}'"

    def test_thresholds_are_positive(self):
        for event_name, mapping in EVENT_TO_PATTERN.items():
            assert mapping["min_threshold"] >= 1, (
                f"Event '{event_name}' has invalid threshold"
            )

    def test_evidence_values_are_valid(self):
        valid = {"low", "medium", "high"}
        for event_name, mapping in EVENT_TO_PATTERN.items():
            assert mapping["evidence"] in valid, (
                f"Event '{event_name}' has invalid evidence"
            )


class TestMapFeatureUsage:
    def test_basic_mapping(self):
        counts = {
            "Workbench Opened": 100,
            "Model Deployed": 5,
        }
        mappings = map_feature_usage_to_patterns(counts)
        assert len(mappings) == 2
        components = {m.component for m in mappings}
        assert "Workbenches" in components
        assert "Model Serving" in components

    def test_threshold_filtering(self):
        counts = {
            "Workbench Opened": 3,  # Below threshold of 5
            "Model Deployed": 1,  # At threshold of 1
        }
        mappings = map_feature_usage_to_patterns(counts)
        assert len(mappings) == 1
        assert mappings[0].component == "Model Serving"

    def test_empty_counts(self):
        mappings = map_feature_usage_to_patterns({})
        assert mappings == []

    def test_all_zeros(self):
        counts = {event: 0 for event in EVENT_TO_PATTERN}
        mappings = map_feature_usage_to_patterns(counts)
        assert mappings == []

    def test_unknown_events_ignored(self):
        counts = {
            "Unknown Event XYZ": 100,
            "Model Deployed": 5,
        }
        mappings = map_feature_usage_to_patterns(counts)
        assert len(mappings) == 1
        assert mappings[0].event_name == "Model Deployed"

    def test_mapping_fields(self):
        counts = {"Pipeline Run Triggered": 10}
        mappings = map_feature_usage_to_patterns(counts)
        assert len(mappings) == 1
        m = mappings[0]
        assert m.component == "Data Science Pipelines"
        assert m.stage == "ML Operations"
        assert m.pattern_title == "Pipeline Execution"
        assert m.event_count == 10
        assert m.evidence_strength == "high"

    def test_taxonomy_validation_warns_on_mismatch(self):
        mock_taxonomy = MagicMock()
        mock_taxonomy.get_all_components.return_value = [
            "Model Serving"
        ]  # Missing "Workbenches"

        counts = {"Workbench Opened": 100}
        # Should still return the mapping but log a warning
        mappings = map_feature_usage_to_patterns(counts, taxonomy_loader=mock_taxonomy)
        assert len(mappings) == 1
        assert mappings[0].component == "Workbenches"

    def test_taxonomy_loader_failure_handled(self):
        mock_taxonomy = MagicMock()
        mock_taxonomy.get_all_components.side_effect = Exception("taxonomy error")

        counts = {"Model Deployed": 5}
        # Should not raise
        mappings = map_feature_usage_to_patterns(counts, taxonomy_loader=mock_taxonomy)
        assert len(mappings) == 1

    def test_playground_higher_threshold(self):
        """Playground has min_threshold=3, requiring more usage to count."""
        counts = {"Playground Query Submitted": 2}  # Below 3
        mappings = map_feature_usage_to_patterns(counts)
        assert len(mappings) == 0

        counts = {"Playground Query Submitted": 3}  # At threshold
        mappings = map_feature_usage_to_patterns(counts)
        assert len(mappings) == 1


class TestAmplitudeProfile:
    def test_to_dict_from_dict_roundtrip(self):
        from src.models.amplitude import AmplitudeProfile

        profile = AmplitudeProfile(
            org_name="Test Corp",
            ebs_id="12345",
            unique_users=50,
            total_events=500,
            feature_counts={"Workbench Opened": 100, "Model Deployed": 5},
            fetched_at="2026-06-14T12:00:00",
            period_days=30,
            period_start="2026-05-15",
            period_end="2026-06-14",
        )
        data = profile.to_dict()
        restored = AmplitudeProfile.from_dict(data)
        assert restored.org_name == profile.org_name
        assert restored.ebs_id == profile.ebs_id
        assert restored.unique_users == profile.unique_users
        assert restored.total_events == profile.total_events
        assert restored.feature_counts == profile.feature_counts
        assert restored.fetched_at == profile.fetched_at
        assert restored.period_days == profile.period_days

    def test_from_dict_missing_optional_fields(self):
        from src.models.amplitude import AmplitudeProfile

        data = {"org_name": "Minimal Corp"}
        profile = AmplitudeProfile.from_dict(data)
        assert profile.org_name == "Minimal Corp"
        assert profile.ebs_id is None
        assert profile.unique_users == 0
        assert profile.feature_counts == {}


class TestDetectContradictions:
    def test_no_profile(self):
        from src.extractors.amplitude_mapper import detect_contradictions

        result = detect_contradictions({"Pipeline Run Triggered": 0}, None)
        assert result == []

    def test_empty_profile(self):
        from src.extractors.amplitude_mapper import detect_contradictions

        result = detect_contradictions({"Pipeline Run Triggered": 0}, {})
        assert result == []

    def test_pipeline_contradiction(self):
        from src.extractors.amplitude_mapper import detect_contradictions

        profile = {"using_dsp": True}
        counts = {"Pipeline Run Triggered": 0, "Pipeline Imported": 0}
        result = detect_contradictions(counts, profile)
        assert len(result) == 1
        assert "Pipelines" in result[0]

    def test_no_pipeline_contradiction_when_events_exist(self):
        from src.extractors.amplitude_mapper import detect_contradictions

        profile = {"using_dsp": True}
        counts = {"Pipeline Run Triggered": 5, "Pipeline Imported": 0}
        result = detect_contradictions(counts, profile)
        assert result == []

    def test_model_registry_discovery(self):
        from src.extractors.amplitude_mapper import detect_contradictions

        profile = {"using_model_registry": None}
        counts = {"Model Registered": 10}
        result = detect_contradictions(counts, profile)
        assert len(result) == 1
        assert "Model Registry" in result[0]
        assert "10 registrations" in result[0]

    def test_no_registry_contradiction_when_jira_knows(self):
        from src.extractors.amplitude_mapper import detect_contradictions

        profile = {"using_model_registry": True}
        counts = {"Model Registered": 10}
        result = detect_contradictions(counts, profile)
        assert result == []

    def test_multiple_contradictions(self):
        from src.extractors.amplitude_mapper import detect_contradictions

        profile = {"using_dsp": True, "using_model_registry": None}
        counts = {
            "Pipeline Run Triggered": 0,
            "Pipeline Imported": 0,
            "Model Registered": 5,
        }
        result = detect_contradictions(counts, profile)
        assert len(result) == 2


class TestBuildActiveInactiveFeatures:
    def test_basic(self):
        from src.extractors.amplitude_mapper import build_active_inactive_features

        counts = {
            "Workbench Opened": 100,
            "Model Deployed": 5,
            "Pipeline Run Triggered": 0,
        }
        active, inactive = build_active_inactive_features(counts)
        assert "Workbenches" in active
        assert "Model Serving" in active
        assert "Data Science Pipelines" in inactive

    def test_empty_counts(self):
        from src.extractors.amplitude_mapper import build_active_inactive_features

        active, inactive = build_active_inactive_features({})
        assert active == []
        assert len(inactive) > 0  # All features are inactive

    def test_component_with_multiple_events(self):
        """A component is active if ANY of its events exceeds threshold."""
        from src.extractors.amplitude_mapper import build_active_inactive_features

        # Workbench Opened threshold=5, Workbench Created threshold=1
        counts = {"Workbench Opened": 2, "Workbench Created": 3}
        active, inactive = build_active_inactive_features(counts)
        # Workbench Created >= 1 threshold, so Workbenches is active
        assert "Workbenches" in active
        assert "Workbenches" not in inactive

    def test_below_threshold_is_not_active(self):
        from src.extractors.amplitude_mapper import build_active_inactive_features

        counts = {"Workbench Opened": 3}  # Below threshold of 5
        active, inactive = build_active_inactive_features(counts)
        # Workbench Opened is below threshold but not zero, so check behavior
        # It has a count but below threshold — it's NOT active
        assert "Workbenches" not in active


class TestComputeEvidenceLevel:
    def test_low(self):
        from src.extractors.amplitude_mapper import compute_evidence_level

        assert compute_evidence_level(1) == "low"
        assert compute_evidence_level(5) == "low"

    def test_medium(self):
        from src.extractors.amplitude_mapper import compute_evidence_level

        assert compute_evidence_level(6) == "medium"
        assert compute_evidence_level(20) == "medium"

    def test_high(self):
        from src.extractors.amplitude_mapper import compute_evidence_level

        assert compute_evidence_level(21) == "high"
        assert compute_evidence_level(1000) == "high"
