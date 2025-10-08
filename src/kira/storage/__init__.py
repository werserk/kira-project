"""Storage layer for Vault operations with file locking (Phase 0, Point 1)."""

from .vault import Vault, VaultConfig, get_vault

__all__ = [
    "Vault",
    "VaultConfig",
    "get_vault",
]

