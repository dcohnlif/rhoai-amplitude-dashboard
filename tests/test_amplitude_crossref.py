"""Tests for Amplitude customer cross-reference matching."""

import os

import pytest
import yaml

from src.extractors.amplitude_matcher import (
    find_customer_match,
    load_manual_mapping,
    normalize_name,
)


class TestNormalizeName:
    def test_basic_lowercase(self):
        assert normalize_name("Acme Corp") == "acme"

    def test_strip_legal_suffixes(self):
        assert normalize_name("Acme Corporation") == "acme"
        assert normalize_name("Beta Inc") == "beta"
        assert normalize_name("Gamma GmbH") == "gamma"
        assert normalize_name("Delta Ltd") == "delta"
        assert normalize_name("Epsilon LLC") == "epsilon"
        assert normalize_name("Zeta AG") == "zeta"

    def test_turkish_airline(self):
        result = normalize_name("TURK HAVA YOLLARI ANONIM ORTAKLIGI")
        assert result == "turk_hava_yollari"

    def test_unicode_normalization(self):
        result = normalize_name("Societe Generale")
        assert "societe" in result

    def test_punctuation_removed(self):
        result = normalize_name("Net-One Systems Co., Ltd.")
        assert "," not in result
        assert "." not in result

    def test_whitespace_collapsed(self):
        result = normalize_name("  Some   Business  Name  ")
        assert "  " not in result
        assert result == "some_business_name"

    def test_max_length(self):
        long_name = "A" * 100
        result = normalize_name(long_name)
        assert len(result) <= 80

    def test_empty_string(self):
        result = normalize_name("")
        assert result == ""

    def test_sa_suffix(self):
        # "S.A." (with dots) is stripped; "S A" (with space) is kept as separate words
        result = normalize_name("SANTANDER BANK POLSKA S.A.")
        assert "santander" in result
        assert result == "santander_bank_polska"


class TestFindCustomerMatch:
    @pytest.fixture
    def customers(self):
        return [
            {"customer_id": "turkish_airlines", "account_number": "12345"},
            {"customer_id": "ibm", "account_number": "67890"},
            {"customer_id": "cisco", "account_number": "11111"},
        ]

    def test_ebs_id_match(self, customers):
        result = find_customer_match(
            org_name="TURK HAVA YOLLARI",
            ebs_id="12345",
            existing_customers=customers,
            config_dir="/nonexistent",
        )
        assert result == "turkish_airlines"

    def test_manual_mapping_match(self, customers, tmp_path):
        # Create manual mapping file
        config_dir = str(tmp_path)
        mapping = {
            "mappings": {"TURK HAVA YOLLARI ANONIM ORTAKLIGI": "turkish_airlines"}
        }
        with open(
            os.path.join(config_dir, "amplitude_account_mapping.yaml"),
            "w",
            encoding="utf-8",
        ) as f:
            yaml.dump(mapping, f)

        result = find_customer_match(
            org_name="TURK HAVA YOLLARI ANONIM ORTAKLIGI",
            ebs_id=None,
            existing_customers=customers,
            config_dir=config_dir,
        )
        assert result == "turkish_airlines"

    def test_fuzzy_name_match(self, customers):
        # "Cisco" normalizes to "cisco", matching customer_id "cisco"
        result = find_customer_match(
            org_name="Cisco",
            ebs_id=None,
            existing_customers=customers,
            config_dir="/nonexistent",
        )
        assert result == "cisco"

    def test_no_match(self, customers):
        result = find_customer_match(
            org_name="Unknown Company XYZ",
            ebs_id=None,
            existing_customers=customers,
            config_dir="/nonexistent",
        )
        assert result is None

    def test_ebs_id_takes_priority_over_name(self, customers):
        """ebs_id match should win even if name would match differently."""
        result = find_customer_match(
            org_name="IBM Corporation",
            ebs_id="12345",  # Matches turkish_airlines, not ibm
            existing_customers=customers,
            config_dir="/nonexistent",
        )
        assert result == "turkish_airlines"

    def test_manual_mapping_priority_over_fuzzy(self, customers, tmp_path):
        config_dir = str(tmp_path)
        mapping = {"mappings": {"IBM": "ibm_special"}}
        with open(
            os.path.join(config_dir, "amplitude_account_mapping.yaml"),
            "w",
            encoding="utf-8",
        ) as f:
            yaml.dump(mapping, f)

        result = find_customer_match(
            org_name="IBM",
            ebs_id=None,
            existing_customers=customers,
            config_dir=config_dir,
        )
        assert result == "ibm_special"


class TestLoadManualMapping:
    def test_load_existing(self, tmp_path):
        mapping = {"mappings": {"Foo": "bar"}}
        path = tmp_path / "amplitude_account_mapping.yaml"
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(mapping, f)
        result = load_manual_mapping(str(tmp_path))
        assert result == {"Foo": "bar"}

    def test_missing_file(self, tmp_path):
        result = load_manual_mapping(str(tmp_path))
        assert result == {}

    def test_empty_file(self, tmp_path):
        path = tmp_path / "amplitude_account_mapping.yaml"
        path.write_text("", encoding="utf-8")
        result = load_manual_mapping(str(tmp_path))
        assert result == {}
