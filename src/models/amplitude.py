"""Amplitude product analytics data models."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AmplitudeProfile:
    """Amplitude usage profile for a customer. Stored per customer as amplitude.json."""

    org_name: str
    ebs_id: Optional[str] = None
    unique_users: int = 0
    total_events: int = 0
    feature_counts: dict[str, int] = field(default_factory=dict)  # event_name -> count
    fetched_at: str = ""
    period_days: int = 30
    period_start: str = ""
    period_end: str = ""
    active_features: list[str] = field(default_factory=list)
    inactive_features: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    maturity_stage: str = ""
    is_daily_use: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "org_name": self.org_name,
            "ebs_id": self.ebs_id,
            "unique_users": self.unique_users,
            "total_events": self.total_events,
            "feature_counts": self.feature_counts,
            "fetched_at": self.fetched_at,
            "period_days": self.period_days,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "active_features": self.active_features,
            "inactive_features": self.inactive_features,
            "contradictions": self.contradictions,
            "maturity_stage": self.maturity_stage,
            "is_daily_use": self.is_daily_use,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AmplitudeProfile":
        """Create from dictionary."""
        return cls(
            org_name=data["org_name"],
            ebs_id=data.get("ebs_id"),
            unique_users=data.get("unique_users", 0),
            total_events=data.get("total_events", 0),
            feature_counts=data.get("feature_counts", {}),
            fetched_at=data.get("fetched_at", ""),
            period_days=data.get("period_days", 30),
            period_start=data.get("period_start", ""),
            period_end=data.get("period_end", ""),
            active_features=data.get("active_features", []),
            inactive_features=data.get("inactive_features", []),
            contradictions=data.get("contradictions", []),
            maturity_stage=data.get("maturity_stage", ""),
            is_daily_use=data.get("is_daily_use", False),
        )


@dataclass
class AmplitudeSyncResult:
    """Result of an Amplitude sync operation."""

    success: bool
    customers_found: int = 0
    customers_enriched: int = 0
    customers_new: int = 0
    patterns_created: int = 0
    errors: list[str] = field(default_factory=list)
