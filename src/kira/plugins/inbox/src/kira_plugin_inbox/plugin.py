"""Inbox normalization plugin implementation (ADR-013).

Classifies and normalizes free-text messages into typed Vault entities
with schema validation, metadata extraction, and clarification workflow.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable

    from kira.plugin_sdk.context import PluginContext

from .clarification_queue import ClarificationQueue

__all__ = ["InboxNormalizer", "activate", "get_normalizer"]

_NORMALIZER: InboxNormalizer | None = None


@dataclass
class EntityClassification:
    """Classification result for inbox item."""

    entity_type: str  # task, event, meeting, email_draft, research, note
    confidence: float  # 0.0 to 1.0
    extracted_fields: dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""


@dataclass
class InboxNormalizer:
    """Normalize inbox messages and files into typed Vault entities (ADR-013).

    Features:
    - Schema-driven classification (task/event/meeting/email_draft/research/note)
    - Metadata extraction with confidence scoring
    - Clarification queue for low-confidence extractions
    - Integration with Telegram for confirmations
    - Event-driven processing (message.received, file.dropped)
    - Host API integration for Vault writes
    """

    context: PluginContext
    confidence_threshold: float = 0.75

    def __post_init__(self) -> None:
        """Initialize normalizer paths and clarification queue."""
        vault_root = Path(self.context.config.get("vault", {}).get("path", "./vault"))
        self.inbox_path = vault_root / "inbox"
        self.processed_path = vault_root / "processed"
        self.inbox_path.mkdir(parents=True, exist_ok=True)
        self.processed_path.mkdir(parents=True, exist_ok=True)

        # Clarification queue with proper persistence
        self._clarifications_path = vault_root / ".kira" / "clarifications.json"
        self._clarification_queue = ClarificationQueue(storage_path=self._clarifications_path)

        # Setup event handlers
        self._setup_event_handlers()

    def _setup_event_handlers(self) -> None:
        """Setup event handlers for inbox processing."""
        # Subscribe to incoming messages and files
        self.context.events.subscribe("message.received", self._handle_message_received)
        self.context.events.subscribe("file.dropped", self._handle_file_dropped)

        # Subscribe to confirmation responses
        self.context.events.subscribe("inbox.clarification_confirmed", self._handle_clarification_confirmed)

        self.context.logger.info("Inbox event handlers registered")

    @staticmethod
    def normalize_text(text: str) -> str:
        """Collapse whitespace while preserving paragraph breaks."""
        normalized = text.replace("\r\n", "\n").strip()
        normalized = re.sub(r"[ \t\u00A0]+", " ", normalized)
        normalized = re.sub(r" ?\n ?", "\n", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip(".,!?;:\"'()[]{}")

    def classify_content(self, content: str) -> EntityClassification:
        """Classify content into entity type with confidence score.

        Uses heuristics and patterns to determine entity type:
        - task: action verbs, deadlines, "нужно", "сделать"
        - event: dates, times, location, attendees
        - meeting: "встреча", "созвон", time + attendees
        - email_draft: email addresses, "написать", "отправить"
        - research: "изучить", "почитать", "исследовать", URLs
        - note: fallback for general notes

        Parameters
        ----------
        content
            Text content to classify

        Returns
        -------
        EntityClassification
            Classification with confidence and extracted fields
        """
        content_lower = content.lower()
        content_lower.split()

        # Score for each entity type
        scores = {
            "task": 0.0,
            "event": 0.0,
            "meeting": 0.0,
            "email_draft": 0.0,
            "research": 0.0,
            "note": 0.3,  # Base score for fallback
        }

        extracted_fields: dict[str, Any] = {}

        # Task indicators
        task_verbs = ["сделать", "нужно", "создать", "написать", "исправить", "добавить", "убрать"]
        task_indicators = [
            "todo",
            "задач",
            "task",
            "fix",
            "bug",
            "implement",
        ]  # "задач" matches "задача", "задачу", etc.

        if any(verb in content_lower for verb in task_verbs):
            scores["task"] += 0.4
        if any(ind in content_lower for ind in task_indicators):
            scores["task"] += 0.3

        # Event indicators
        event_indicators = ["событие", "мероприятие", "конференция", "event"]
        time_patterns = [r"\d{1,2}:\d{2}", r"\d{1,2}h", r"\d{1,2}ч"]
        date_patterns = [r"\d{1,2}\.\d{1,2}", r"\d{4}-\d{2}-\d{2}", r"завтра", r"сегодня", r"через \w+"]

        if any(ind in content_lower for ind in event_indicators):
            scores["event"] += 0.3
        if any(re.search(pattern, content_lower) for pattern in time_patterns):
            scores["event"] += 0.2
            # Extract time
            time_match = re.search(r"(\d{1,2}):(\d{2})", content)
            if time_match:
                extracted_fields["time"] = time_match.group(0)
        if any(re.search(pattern, content_lower) for pattern in date_patterns):
            scores["event"] += 0.2

        # Meeting indicators
        meeting_indicators = ["встреча", "созвон", "звонок", "meeting", "call", "sync"]
        if any(ind in content_lower for ind in meeting_indicators):
            scores["meeting"] += 0.6
            scores["event"] += 0.1  # Meetings are also events

        # Email draft indicators
        email_patterns = [r"[\w\.-]+@[\w\.-]+", r"отправить.*письмо", r"написать.*email"]
        if any(re.search(pattern, content_lower) for pattern in email_patterns):
            scores["email_draft"] += 0.4
            # Extract email addresses
            emails = re.findall(r"[\w\.-]+@[\w\.-]+", content)
            if emails:
                extracted_fields["recipients"] = emails

        # Research indicators
        research_indicators = ["изучить", "почитать", "исследовать", "research", "study", "learn"]
        if any(ind in content_lower for ind in research_indicators):
            scores["research"] += 0.3
        if re.search(r"https?://", content):
            scores["research"] += 0.2
            # Extract URLs
            urls = re.findall(r"https?://[^\s]+", content)
            if urls:
                extracted_fields["links"] = urls

        # Extract priority
        if any(word in content_lower for word in ["срочно", "важно", "urgent", "asap"]):
            extracted_fields["priority"] = "high"
        elif any(word in content_lower for word in ["низкий", "low"]):
            extracted_fields["priority"] = "low"
        else:
            extracted_fields["priority"] = "medium"

        # Extract title (first line or first sentence)
        lines = content.split("\n")
        first_line = lines[0].strip("#").strip()
        if len(first_line) > 100:
            # Too long, take first sentence
            sentences = re.split(r"[.!?]\s+", first_line)
            extracted_fields["title"] = sentences[0][:100]
        else:
            extracted_fields["title"] = first_line

        # Extract tags
        tags = {tag.strip("#") for tag in re.findall(r"#[\w\-]+", content)}
        if tags:
            extracted_fields["tags"] = sorted(tags)

        # Determine entity type with highest score
        entity_type = max(scores.items(), key=lambda x: x[1])[0]
        confidence = scores[entity_type]

        # Boost confidence if multiple indicators present
        if len([s for s in scores.values() if s > 0.2]) == 1:
            confidence = min(confidence + 0.1, 1.0)

        reasoning = f"Classified as {entity_type} (score: {confidence:.2f})"

        return EntityClassification(
            entity_type=entity_type,
            confidence=confidence,
            extracted_fields=extracted_fields,
            reasoning=reasoning,
        )

    def extract_metadata(
        self,
        content: str,
        source: str | None = None,
        classification: EntityClassification | None = None,
    ) -> dict[str, Any]:
        """Extract comprehensive metadata from content.

        Parameters
        ----------
        content
            Text content
        source
            Source of the content (e.g., "telegram", "file")
        classification
            Pre-computed classification (optional)

        Returns
        -------
        dict
            Metadata dictionary for entity creation
        """
        if classification is None:
            classification = self.classify_content(content)

        metadata: dict[str, Any] = {
            "source": source or "unknown",
            "timestamp": datetime.now(UTC).isoformat(),
            "length": len(content),
            "entity_type": classification.entity_type,
            "confidence": classification.confidence,
            "status": "inbox",
        }

        # Merge extracted fields
        metadata.update(classification.extracted_fields)

        return metadata

    def create_entity(self, content: str, metadata: dict[str, Any]) -> dict[str, Any]:
        """Create entity via Host API or queue for clarification.

        Parameters
        ----------
        content
            Entity content
        metadata
            Entity metadata

        Returns
        -------
        dict
            Result with entity ID or clarification request ID
        """
        entity_type = metadata.get("entity_type", "note")
        confidence = metadata.get("confidence", 0.0)

        # Check confidence threshold
        if confidence < self.confidence_threshold:
            # Queue for clarification
            return self._queue_clarification(content, metadata)

        # High confidence - create entity directly
        try:
            if self.context.vault is not None:
                # Prepare entity data
                entity_data = {
                    "title": metadata.get("title", "Inbox item"),
                    "source": metadata.get("source", "unknown"),
                    "priority": metadata.get("priority", "medium"),
                    "status": "inbox",
                }

                # Add optional fields
                if "tags" in metadata:
                    entity_data["tags"] = metadata["tags"]
                if "time" in metadata:
                    entity_data["time"] = metadata["time"]
                if "recipients" in metadata:
                    entity_data["recipients"] = metadata["recipients"]
                if "links" in metadata:
                    entity_data["links"] = metadata["links"]

                # Create entity via Host API
                entity = self.context.vault.create_entity(
                    entity_type=entity_type,
                    data=entity_data,
                    content=content,
                )

                self.context.logger.info(f"Created {entity_type} entity: {entity.id}")

                # Publish success event
                self.context.events.publish(
                    "inbox.normalized",
                    {
                        "entity_id": entity.id,
                        "entity_type": entity_type,
                        "confidence": confidence,
                        "source": metadata.get("source"),
                    },
                )

                return {
                    "success": True,
                    "entity_id": entity.id,
                    "entity_type": entity_type,
                    "confidence": confidence,
                }

            # Fallback to file creation
            return self._create_file_fallback(content, metadata)

        except Exception as exc:
            self.context.logger.error(f"Failed to create entity: {exc}")
            return {
                "success": False,
                "error": str(exc),
            }

    def _queue_clarification(self, content: str, metadata: dict[str, Any]) -> dict[str, Any]:
        """Queue item for clarification.

        Parameters
        ----------
        content
            Item content
        metadata
            Extracted metadata

        Returns
        -------
        dict
            Clarification request details
        """
        entity_type = metadata.get("entity_type", "note")
        confidence = metadata.get("confidence", 0.0)

        # Generate alternatives (other possible entity types)
        alternatives = []
        content_lower = content.lower()

        if "встреча" in content_lower or "созвон" in content_lower:
            alternatives.append({"type": "meeting", "confidence": 0.6})
        if "задача" in content_lower or "нужно" in content_lower:
            alternatives.append({"type": "task", "confidence": 0.5})

        # Include content in metadata for persistence
        extracted_data = metadata.copy()
        extracted_data["content"] = content

        # Add to queue with proper serialization
        item = self._clarification_queue.add(
            source_event_id=metadata.get("event_id", f"evt-{uuid.uuid4().hex[:8]}"),
            extracted_type=entity_type,
            extracted_data=extracted_data,
            confidence=confidence,
            alternatives=alternatives[:2],  # Max 2 alternatives
        )

        # Request confirmation via Telegram (if available)
        self._request_telegram_confirmation(item)

        self.context.logger.info(f"Queued for clarification: {item.clarification_id}")

        return {
            "success": False,
            "requires_clarification": True,
            "request_id": item.clarification_id,
            "confidence": confidence,
        }

    def _request_telegram_confirmation(self, item: Any) -> None:
        """Request inline confirmation via Telegram.

        Parameters
        ----------
        item
            ClarificationItem from queue
        """
        # Extract content from extracted_data
        content = item.extracted_data.get("content", "")
        if not content:
            # Try to reconstruct from metadata
            title = item.extracted_data.get("title", "Unknown item")
            content = f"{title}"

        # Build confirmation message
        message = "📥 *Inbox Normalization*\n\n"
        message += f"Content: {content[:100]}...\n\n"
        message += f"Detected as: *{item.extracted_type}*\n"
        message += f"Confidence: {item.confidence:.0%}\n\n"
        message += "Is this correct?"

        # Build options
        options = [
            {"text": f"✅ Yes ({item.extracted_type})", "callback_data": "confirm"},
        ]

        for alt in item.suggested_alternatives[:2]:
            alt_type = alt.get("type", "unknown")
            options.append({"text": f"🔄 {alt_type.capitalize()}", "callback_data": f"alt_{alt_type}"})

        options.append({"text": "❌ Skip", "callback_data": "skip"})

        # Publish confirmation request event
        self.context.events.publish(
            "telegram.confirmation_request",
            {
                "request_id": item.clarification_id,
                "message": message,
                "options": options,
                "command": "inbox.confirm",
                "context": {
                    "content": content,
                    "classification": item.extracted_type,
                    "metadata": item.extracted_data,
                },
            },
        )

    def _handle_clarification_confirmed(self, event: Any) -> None:
        """Handle clarification confirmation from user.

        Parameters
        ----------
        event
            Confirmation event with user choice
        """
        payload = event.payload
        request_id = payload.get("request_id")
        choice = payload.get("choice")

        if not request_id:
            return

        # Get pending items
        pending_items = self._clarification_queue.get_pending()
        item = next((i for i in pending_items if i.clarification_id == request_id), None)

        if not item:
            self.context.logger.warning(f"Clarification item not found: {request_id}")
            return

        # Extract content from item
        content = item.extracted_data.get("content", item.extracted_data.get("title", ""))

        if choice == "confirm":
            # User confirmed - create entity with original classification
            metadata = item.extracted_data.copy()
            metadata["entity_type"] = item.extracted_type
            metadata["confidence"] = 1.0  # User confirmed
            result = self.create_entity(content, metadata)
            
            # Update item status
            self._clarification_queue.confirm(request_id, {"confirmed": True})
            self.context.logger.info(f"Clarification confirmed: {request_id} -> {result}")

        elif choice.startswith("alt_"):
            # User selected alternative type
            alt_type = choice.split("_", 1)[1]
            metadata = item.extracted_data.copy()
            metadata["entity_type"] = alt_type
            metadata["confidence"] = 1.0
            result = self.create_entity(content, metadata)
            
            # Update item status with alternative
            self._clarification_queue.confirm(request_id, {"confirmed": True, "alternative": alt_type})
            self.context.logger.info(f"Clarification alternative selected: {request_id} -> {alt_type}")

        elif choice == "skip":
            # User skipped - mark as rejected
            self._clarification_queue.confirm(request_id, {"confirmed": False})
            self.context.logger.info(f"Clarification skipped: {request_id}")

    def _create_file_fallback(self, content: str, metadata: dict[str, Any]) -> dict[str, Any]:
        """Fallback: create markdown file directly.

        Parameters
        ----------
        content
            Content
        metadata
            Metadata

        Returns
        -------
        dict
            Result with file path
        """
        safe_name = metadata.get("timestamp", datetime.now(UTC).isoformat())
        file_name = f"{safe_name}-{uuid.uuid4().hex[:8]}.md"
        output_path = self.processed_path / file_name

        frontmatter = json.dumps(metadata, ensure_ascii=False, indent=2)
        body_lines = [
            "---",
            frontmatter,
            "---",
            "",
            "# Inbox Normalizer",
            "",
            content,
            "",
        ]
        body = "\n".join(body_lines)
        output_path.write_text(body, encoding="utf-8")

        self.context.logger.debug(f"Created file directly: {output_path}")

        return {
            "success": True,
            "file_path": str(output_path),
            "entity_type": metadata.get("entity_type"),
        }

    def process_message(self, message: str, source: str | None = None) -> dict[str, Any]:
        """Normalize and persist a raw message.

        Parameters
        ----------
        message
            Raw message text
        source
            Source identifier

        Returns
        -------
        dict
            Processing result
        """
        normalized = self.normalize_text(message)

        # Classify and extract metadata
        classification = self.classify_content(normalized)
        metadata = self.extract_metadata(normalized, source, classification)

        # Create entity
        return self.create_entity(normalized, metadata)

    def process_file(self, file_path: Path) -> dict[str, Any]:
        """Normalize an incoming file.

        Parameters
        ----------
        file_path
            Path to file

        Returns
        -------
        dict
            Processing result
        """
        file_path = Path(file_path)
        content = file_path.read_text(encoding="utf-8")
        result = self.process_message(content, source="file")

        # Delete original file if processing succeeded
        if result.get("success") and file_path.exists():
            file_path.unlink()

        return result

    def _handle_message_received(self, event: Any) -> None:
        """Handle message.received event.

        Parameters
        ----------
        event
            Event with message data
        """
        try:
            payload = event.payload
            message = str(payload.get("message", ""))
            source = payload.get("source")

            if not message:
                return

            result = self.process_message(message, source=source if isinstance(source, str) else None)

            self.context.logger.info(f"Processed message from {source}: {result}")

        except Exception as exc:
            self.context.logger.error(f"Failed to handle message.received: {exc}")

    def _handle_file_dropped(self, event: Any) -> None:
        """Handle file.dropped event.

        Parameters
        ----------
        event
            Event with file data
        """
        try:
            payload = event.payload
            file_path = Path(str(payload.get("file_path")))

            if not file_path.exists():
                self.context.logger.warning(f"File not found: {file_path}")
                return

            result = self.process_file(file_path)

            self.context.logger.info(f"Processed file {file_path}: {result}")

        except Exception as exc:
            self.context.logger.error(f"Failed to handle file.dropped: {exc}")

    def get_pending_clarifications(self) -> list[Any]:
        """Get pending clarification items.

        Returns
        -------
        list
            List of pending clarification items
        """
        return self._clarification_queue.get_pending()

    def get_clarification_statistics(self) -> dict[str, Any]:
        """Get clarification queue statistics.

        Returns
        -------
        dict
            Statistics about the clarification queue
        """
        return self._clarification_queue.get_statistics()


def get_normalizer() -> InboxNormalizer:
    """Get active normalizer instance."""
    if _NORMALIZER is None:
        raise RuntimeError("Inbox plugin is not activated")
    return _NORMALIZER


def activate(context: PluginContext) -> dict[str, str]:
    """Activate the inbox plugin by initialising the normalizer.

    Parameters
    ----------
    context
        Plugin execution context

    Returns
    -------
    dict
        Activation status
    """
    global _NORMALIZER
    _NORMALIZER = InboxNormalizer(context)

    context.logger.info("Inbox normalizer plugin activated (ADR-013)")
    context.events.publish(
        "inbox.activated",
        {
            "message": "Inbox normalizer activated with schema-driven classification",
            "plugin": "kira-inbox",
            "features": [
                "schema_driven_classification",
                "clarification_queue",
                "telegram_integration",
                "event_publishing",
            ],
        },
    )

    return {"status": "ok", "plugin": "kira-inbox", "version": "1.0.0"}


def handle_message_received(context: PluginContext, event_data: dict[str, Any]) -> None:
    """Handle message.received event (legacy compatibility)."""
    message = str(event_data.get("message", ""))
    source = event_data.get("source")
    normalizer = get_normalizer()
    result = normalizer.process_message(message, source=source if isinstance(source, str) else None)
    context.logger.debug(f"Normalized message stored: {result}")


def handle_file_dropped(context: PluginContext, event_data: dict[str, Any]) -> None:
    """Handle file.dropped event (legacy compatibility)."""
    file_path = Path(str(event_data.get("file_path")))
    normalizer = get_normalizer()
    result = normalizer.process_file(file_path)
    context.logger.debug(f"Normalized file stored: {result}")


def normalize_command(context: PluginContext, args: Iterable[str]) -> str:
    """Normalize command (legacy compatibility)."""
    terms = list(args)
    if not terms:
        return "Usage: kira inbox normalize <text>"

    normalizer = get_normalizer()
    message = " ".join(terms)
    result = normalizer.process_message(message)

    if result.get("success"):
        return f"Normalized {len(message)} chars -> entity: {result.get('entity_id', 'file created')}"
    if result.get("requires_clarification"):
        return f"Requires clarification (ID: {result.get('request_id')})"
    return f"Error: {result.get('error', 'unknown')}"
