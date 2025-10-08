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
    # Migration
    "migrate_file",
    "migrate_vault",
    "validate_migration",
    # CLI
    "run_migration",
    # Utilities
    "normalize_timestamp_to_utc",
    "infer_entity_type",
    # Data classes
    "MigrationResult",
    "MigrationStats",
]
