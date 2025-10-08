"""Time-based rollups and aggregations (Phase 7, Point 22)."""

from .aggregator import RollupSummary, aggregate_entities, compute_rollup
from .time_windows import (
    TimeWindow,
    compute_boundaries_utc,
    compute_day_boundaries_utc,
    compute_month_boundaries_utc,
    compute_week_boundaries_utc,
    get_week_start,
)

__all__ = [
    # Aggregation
    "RollupSummary",
    # Time windows
    "TimeWindow",
    "aggregate_entities",
    "compute_boundaries_utc",
    "compute_day_boundaries_utc",
    "compute_month_boundaries_utc",
    "compute_rollup",
    "compute_week_boundaries_utc",
    "get_week_start",
]
