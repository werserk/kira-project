"""Vault migration utilities (Phase 8, Point 23)."""

from .cli import run_migration
from .migrator import (
    MigrationResult,
    MigrationStats,
    infer_entity_type,
    migrate_file,
    migrate_vault,
    normalize_timestamp_to_utc,
    validate_migration,
)

__all__ = [
    # Data classes
    "MigrationResult",
    "MigrationStats",
    "infer_entity_type",
    # Migration
    "migrate_file",
    "migrate_vault",
    # Utilities
    "normalize_timestamp_to_utc",
    # CLI
    "run_migration",
    "validate_migration",
]
