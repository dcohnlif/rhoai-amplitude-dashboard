"""Cross-reference Amplitude customers with existing Jira customers.

Provides name normalization and multi-strategy matching to link
Amplitude org_name to our customer_id.
"""

import logging
import os
import re
import unicodedata
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

# Legal suffixes to strip during normalization
_LEGAL_SUFFIXES = [
    r"\bcorporation\b",
    r"\bcorp\b",
    r"\bcompany\b",
    r"\bco\b",
    r"\blimited\b",
    r"\bltd\b",
    r"\binc\b",
    r"\bllp\b",
    r"\bllc\b",
    r"\bgmbh\b",
    r"\bag\b",
    r"\bplc\b",
    r"\bpjsc\b",
    r"\bholding\b",
    r"\bholdings\b",
    r"\banonim ortakligi\b",
    r"\banonim sirketi\b",
    r"\bs\.?a\.?\b",
    r"\ba\.?s\.?\b",
    r"\bd\.?o\.?o\.?\b",
    r"\bs\.?a\.?r\.?l\.?\b",
    r"\boyj\b",
    r"\bhf\b",
    r"\bab\b",
]


def normalize_name(name: str) -> str:
    """Normalize a company name to a canonical lowercase identifier.

    Applies Unicode NFKD normalization, strips legal suffixes,
    removes punctuation, and collapses whitespace to underscores.

    Args:
        name: Raw company/org name (e.g., "TURK HAVA YOLLARI ANONIM ORTAKLIGI")

    Returns:
        Normalized identifier (e.g., "turk_hava_yollari")
    """
    # Unicode NFKD normalization (e.g., e with accent -> e)
    nfkd = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in nfkd if not unicodedata.combining(c))

    # Lowercase
    text = text.lower().strip()

    # Remove legal suffixes
    for suffix in _LEGAL_SUFFIXES:
        text = re.sub(suffix, "", text)

    # Strip punctuation and collapse whitespace
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", "_", text.strip())

    return text.strip("_")[:80]


def load_manual_mapping(config_dir: str = "config") -> dict[str, str]:
    """Load the manual Amplitude org_name -> customer_id mapping.

    Args:
        config_dir: Path to the config directory

    Returns:
        Dict mapping org_name to customer_id
    """
    mapping_path = os.path.join(config_dir, "amplitude_account_mapping.yaml")
    if not os.path.exists(mapping_path):
        return {}
    try:
        with open(mapping_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
            return cfg.get("mappings", {})
    except Exception as e:
        logger.warning("Failed to load amplitude mapping: %s", e)
        return {}


def find_customer_match(
    org_name: str,
    ebs_id: Optional[str],
    existing_customers: list[dict],
    config_dir: str = "config",
) -> Optional[str]:
    """Find a matching customer_id for an Amplitude org_name.

    Matching strategy (in priority order):
    1. ebs_id matches existing customer account_number
    2. Manual mapping from config/amplitude_account_mapping.yaml
    3. Normalized name matches existing customer_id

    Args:
        org_name: Amplitude organization name
        ebs_id: EBS account ID from Amplitude lookup table (may be None)
        existing_customers: List of dicts with at least 'customer_id' key,
            optionally 'account_number'
        config_dir: Path to config directory for manual mapping

    Returns:
        Matched customer_id or None
    """
    # Strategy 1: ebs_id -> account_number
    if ebs_id:
        for c in existing_customers:
            if c.get("account_number") == ebs_id:
                logger.info("EBS match: '%s' -> '%s'", org_name, c["customer_id"])
                return c["customer_id"]

    # Strategy 2: Manual mapping
    manual = load_manual_mapping(config_dir)
    if org_name in manual:
        matched = manual[org_name]
        logger.info("Manual match: '%s' -> '%s'", org_name, matched)
        return matched

    # Strategy 3: Normalized name match
    norm_org = normalize_name(org_name)
    for c in existing_customers:
        if normalize_name(c["customer_id"]) == norm_org:
            logger.info("Fuzzy match: '%s' -> '%s'", org_name, c["customer_id"])
            return c["customer_id"]

    return None
