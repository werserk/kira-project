"""Clarification Queue for low-confidence normalizations (ADR-013).

When the inbox normalizer has low confidence in its extraction, it stores
the item in a clarification queue and requests user confirmation via Telegram.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ClarificationItem:
    """Item awaiting clarification."""
    
    clarification_id: str
    source_event_id: str
    extracted_type: str
    extracted_data: dict[str, Any]
    confidence: float
    suggested_alternatives: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: str = "pending"  # pending, confirmed, rejected, timeout
    user_response: dict[str, Any] | None = None


class ClarificationQueue:
    """Queue for items requiring user clarification.
    
    Features (ADR-013):
    - Store uncertain extractions
    - Generate Telegram inline button options
    - Track user responses
    - Auto-timeout after N hours
    - Metrics on clarification accuracy
    
    Example:
        >>> queue = ClarificationQueue(storage_path=Path("vault/.kira/clarifications.json"))
        >>> item = queue.add(
        ...     source_event_id="evt-123",
        ...     extracted_type="task",
        ...     extracted_data={"title": "Maybe a task?"},
        ...     confidence=0.65,
        ... )
        >>> # Later, from Telegram callback:
        >>> queue.confirm(item.clarification_id, user_data={"confirmed": True})
    """
    
    def __init__(self, storage_path: Path) -> None:
        """Initialize clarification queue.
        
        Parameters
        ----------
        storage_path
            Path to JSON storage file
        """
        self.storage_path = storage_path
        self._items: dict[str, ClarificationItem] = {}
        self._load()
    
    def add(
        self,
        source_event_id: str,
        extracted_type: str,
        extracted_data: dict[str, Any],
        confidence: float,
        alternatives: list[dict[str, Any]] | None = None,
    ) -> ClarificationItem:
        """Add item to clarification queue.
        
        Parameters
        ----------
        source_event_id
            ID of source event (message.received, etc.)
        extracted_type
            Extracted entity type (task, note, etc.)
        extracted_data
            Extracted frontmatter and content
        confidence
            Confidence score (0.0-1.0)
        alternatives
            Alternative interpretations
        
        Returns
        -------
        ClarificationItem
            Created clarification item
        """
        clarification_id = f"clarif-{uuid.uuid4().hex[:8]}"
        
        item = ClarificationItem(
            clarification_id=clarification_id,
            source_event_id=source_event_id,
            extracted_type=extracted_type,
            extracted_data=extracted_data,
            confidence=confidence,
            suggested_alternatives=alternatives or [],
        )
        
        self._items[clarification_id] = item
        self._save()
        
        return item
    
    def confirm(
        self,
        clarification_id: str,
        user_data: dict[str, Any],
    ) -> ClarificationItem | None:
        """Confirm clarification with user input.
        
        Parameters
        ----------
        clarification_id
            Clarification ID
        user_data
            User response data (from Telegram callback)
        
        Returns
        -------
        ClarificationItem or None
            Updated item, or None if not found
        """
        item = self._items.get(clarification_id)
        
        if not item:
            return None
        
        item.status = "confirmed" if user_data.get("confirmed") else "rejected"
        item.user_response = user_data
        
        self._save()
        
        return item
    
    def get_pending(self, max_age_hours: float = 24.0) -> list[ClarificationItem]:
        """Get pending clarification items.
        
        Parameters
        ----------
        max_age_hours
            Maximum age in hours (auto-timeout older items)
        
        Returns
        -------
        list[ClarificationItem]
            Pending items (not expired)
        """
        now = datetime.now(timezone.utc)
        pending = []
        
        for item in self._items.values():
            if item.status != "pending":
                continue
            
            age_hours = (now - item.created_at).total_seconds() / 3600
            
            if age_hours > max_age_hours:
                # Auto-timeout
                item.status = "timeout"
                self._save()
                continue
            
            pending.append(item)
        
        return pending
    
    def get_statistics(self) -> dict[str, Any]:
        """Get queue statistics.
        
        Returns
        -------
        dict
            Statistics including accuracy metrics
        """
        total = len(self._items)
        
        by_status = {"pending": 0, "confirmed": 0, "rejected": 0, "timeout": 0}
        
        confirmed_items = []
        
        for item in self._items.values():
            by_status[item.status] = by_status.get(item.status, 0) + 1
            
            if item.status == "confirmed":
                confirmed_items.append(item)
        
        # Calculate accuracy: items with high confidence that were confirmed
        high_confidence_correct = sum(
            1 for item in confirmed_items if item.confidence >= 0.8
        )
        
        accuracy = (
            high_confidence_correct / total
            if total > 0
            else 0.0
        )
        
        return {
            "total_items": total,
            "by_status": by_status,
            "accuracy": accuracy,
            "avg_confidence": (
                sum(item.confidence for item in self._items.values()) / total
                if total > 0
                else 0.0
            ),
        }
    
    def _load(self) -> None:
        """Load queue from storage."""
        if not self.storage_path.exists():
            return
        
        try:
            with open(self.storage_path, encoding="utf-8") as f:
                data = json.load(f)
            
            for item_data in data.get("items", []):
                # Convert ISO timestamps
                item_data["created_at"] = datetime.fromisoformat(
                    item_data["created_at"].replace("Z", "+00:00")
                )
                
                item = ClarificationItem(**item_data)
                self._items[item.clarification_id] = item
                
        except Exception:
            # If load fails, start with empty queue
            pass
    
    def _save(self) -> None:
        """Save queue to storage."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "version": "1.0",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "items": [
                {
                    **asdict(item),
                    "created_at": item.created_at.isoformat(),
                }
                for item in self._items.values()
            ],
        }
        
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def create_telegram_inline_keyboard(item: ClarificationItem) -> dict[str, Any]:
    """Create Telegram inline keyboard for clarification.
    
    Parameters
    ----------
    item
        Clarification item
    
    Returns
    -------
    dict
        Telegram InlineKeyboardMarkup structure
    """
    buttons = [
        [
            {
                "text": f"✅ Yes, it's a {item.extracted_type}",
                "callback_data": json.dumps({
                    "action": "clarify",
                    "id": item.clarification_id,
                    "confirmed": True,
                }),
            }
        ],
    ]
    
    # Add alternative buttons
    for alt in item.suggested_alternatives[:2]:  # Max 2 alternatives
        alt_type = alt.get("type", "unknown")
        buttons.append([
            {
                "text": f"📝 No, it's a {alt_type}",
                "callback_data": json.dumps({
                    "action": "clarify",
                    "id": item.clarification_id,
                    "confirmed": True,
                    "alternative": alt_type,
                }),
            }
        ])
    
    buttons.append([
        {
            "text": "❌ Ignore",
            "callback_data": json.dumps({
                "action": "clarify",
                "id": item.clarification_id,
                "confirmed": False,
            }),
        }
    ])
    
    return {"inline_keyboard": buttons}

