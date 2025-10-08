"""Sync contract embedded in entity front-matter (Phase 4, Point 14).

The sync contract tracks synchronization state to prevent echo loops
and enable conflict resolution in two-way sync scenarios.

Contract Fields (stored in x-kira metadata):
- source: Origin of last write ("kira" | "gcal" | other)
- version: Monotonically increasing version number (int)
- remote_id: ID in remote system (e.g., GCal event ID)
- last_write_ts: Timestamp of last write (ISO-8601 UTC)

Protocol:
- On Kira writes: set source="kira", increment version
- On remote imports: set source="gcal" (or other), increment version
- Metadata persists across updates and changes predictably
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from ..core.time import format_utc_iso8601, get_current_utc

__all__ = [
    "SyncContract",
    "SyncSource",
    "create_kira_sync_contract",
    "create_remote_sync_contract",
    "get_sync_contract",
    "update_sync_contract",
]

SyncSource = Literal["kira", "gcal", "telegram", "other"]


@dataclass
class SyncContract:
    """Sync contract for tracking synchronization state.

    Attributes
    ----------
    source : SyncSource
        Origin of last write ("kira", "gcal", etc.)
    version : int
        Monotonically increasing version number
    remote_id : str | None
        ID in remote system (if synced)
    last_write_ts : str
        Timestamp of last write (ISO-8601 UTC)
    etag : str | None
        Optional ETag from remote system (for optimistic locking)
    """

    source: SyncSource
    version: int
    remote_id: str | None = None
    last_write_ts: str | None = None
    etag: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage in x-kira metadata.

        Returns
        -------
        dict[str, Any]
            Contract as dictionary
        """
        result: dict[str, Any] = {
            "source": self.source,
            "version": self.version,
        }

        if self.remote_id is not None:
            result["remote_id"] = self.remote_id

        if self.last_write_ts is not None:
            result["last_write_ts"] = self.last_write_ts

        if self.etag is not None:
            result["etag"] = self.etag

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SyncContract:
        """Create contract from dictionary.

        Parameters
        ----------
        data
            Dictionary with contract fields

        Returns
        -------
        SyncContract
            Parsed contract
        """
        return cls(
            source=data.get("source", "kira"),
            version=data.get("version", 0),
            remote_id=data.get("remote_id"),
            last_write_ts=data.get("last_write_ts"),
            etag=data.get("etag"),
        )


def get_sync_contract(metadata: dict[str, Any]) -> SyncContract | None:
    """Extract sync contract from entity metadata.

    Parameters
    ----------
    metadata
        Entity metadata dictionary

    Returns
    -------
    SyncContract | None
        Sync contract if present, None otherwise
    """
    x_kira = metadata.get("x-kira", {})
    if not x_kira:
        return None

    # Check if sync contract fields present
    if "source" not in x_kira and "version" not in x_kira:
        return None

    return SyncContract.from_dict(x_kira)


def update_sync_contract(
    metadata: dict[str, Any],
    *,
    source: SyncSource,
    remote_id: str | None = None,
    etag: str | None = None,
) -> dict[str, Any]:
    """Update sync contract in metadata (Phase 4, Point 14).

    Increments version and updates last_write_ts automatically.

    Parameters
    ----------
    metadata
        Entity metadata dictionary
    source
        Origin of this write ("kira", "gcal", etc.)
    remote_id
        Optional remote system ID
    etag
        Optional ETag from remote system

    Returns
    -------
    dict[str, Any]
        Updated metadata with sync contract
    """
    # Get current contract or create new one
    current_contract = get_sync_contract(metadata)

    if current_contract is None:
        # Create new contract
        new_version = 1
    else:
        # Increment version
        new_version = current_contract.version + 1

    # Get current timestamp
    now_utc = get_current_utc()
    last_write_ts = format_utc_iso8601(now_utc)

    # Build new contract
    new_contract = SyncContract(
        source=source,
        version=new_version,
        remote_id=remote_id if remote_id is not None else (current_contract.remote_id if current_contract else None),
        last_write_ts=last_write_ts,
        etag=etag,
    )

    # Update metadata
    updated_metadata = metadata.copy()
    updated_metadata["x-kira"] = new_contract.to_dict()

    return updated_metadata


def create_kira_sync_contract(
    metadata: dict[str, Any],
    *,
    remote_id: str | None = None,
) -> dict[str, Any]:
    """Create or update sync contract for Kira-originated write (Phase 4, Point 14).

    Sets source="kira" and increments version.

    Parameters
    ----------
    metadata
        Entity metadata
    remote_id
        Optional remote system ID (if entity is synced)

    Returns
    -------
    dict[str, Any]
        Updated metadata with Kira sync contract
    """
    return update_sync_contract(metadata, source="kira", remote_id=remote_id)


def create_remote_sync_contract(
    metadata: dict[str, Any],
    *,
    source: SyncSource,
    remote_id: str,
    etag: str | None = None,
) -> dict[str, Any]:
    """Create or update sync contract for remote-originated import (Phase 4, Point 14).

    Sets source to remote system (e.g., "gcal") and increments version.

    Parameters
    ----------
    metadata
        Entity metadata
    source
        Remote source ("gcal", "telegram", etc.)
    remote_id
        Remote system ID
    etag
        Optional ETag from remote system

    Returns
    -------
    dict[str, Any]
        Updated metadata with remote sync contract
    """
    return update_sync_contract(
        metadata,
        source=source,
        remote_id=remote_id,
        etag=etag,
    )


def is_kira_origin(metadata: dict[str, Any]) -> bool:
    """Check if last write originated from Kira.

    Parameters
    ----------
    metadata
        Entity metadata

    Returns
    -------
    bool
        True if last write was from Kira
    """
    contract = get_sync_contract(metadata)
    return contract is not None and contract.source == "kira"


def is_remote_origin(metadata: dict[str, Any], source: SyncSource) -> bool:
    """Check if last write originated from specific remote source.

    Parameters
    ----------
    metadata
        Entity metadata
    source
        Remote source to check

    Returns
    -------
    bool
        True if last write was from specified remote
    """
    contract = get_sync_contract(metadata)
    return contract is not None and contract.source == source


def get_sync_version(metadata: dict[str, Any]) -> int:
    """Get current sync version from metadata.

    Parameters
    ----------
    metadata
        Entity metadata

    Returns
    -------
    int
        Current version (0 if no contract)
    """
    contract = get_sync_contract(metadata)
    return contract.version if contract else 0
