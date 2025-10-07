"""Inbox normalization plugin implementation."""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from kira.plugin_sdk.context import PluginContext

_NORMALIZER: InboxNormalizer | None = None


@dataclass
class InboxNormalizer:
    """Normalize inbox messages and files into markdown entries."""

    context: PluginContext

    def __post_init__(self) -> None:
        vault_root = Path(self.context.config.get("vault", {}).get("path", "./vault"))
        self.inbox_path = vault_root / "inbox"
        self.processed_path = vault_root / "processed"
        self.inbox_path.mkdir(parents=True, exist_ok=True)
        self.processed_path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def normalize_text(text: str) -> str:
        """Collapse whitespace while preserving paragraph breaks."""
        normalized = text.replace("\r\n", "\n").strip()
        normalized = re.sub(r"[ \t\u00A0]+", " ", normalized)
        normalized = re.sub(r" ?\n ?", "\n", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip(".,!?;:\"'()[]{}")

    def extract_metadata(self, content: str, source: str | None = None) -> dict[str, object]:
        """Extract lightweight metadata heuristics from content."""
        metadata: dict[str, object] = {
            "source": source or "unknown",
            "timestamp": datetime.now(UTC).isoformat(),
            "length": len(content),
            "priority": "medium",
            "type": "text",
        }

        tags = {tag.strip("#") for tag in re.findall(r"#[\w\-]+", content)}
        if tags:
            metadata["tags"] = sorted(tags)

        lowered = content.lower()
        if lowered.startswith("#"):
            metadata["type"] = "note"
        if "задача" in lowered:
            metadata["type"] = "task"
            metadata["priority"] = "high"
        if re.search(r"https?://", content):
            metadata["type"] = "link"

        return metadata

    def create_normalized_file(self, content: str, metadata: dict[str, object]) -> Path:
        """Write processed markdown with frontmatter.

        Uses Host API (ctx.vault) to create entities instead of direct filesystem writes,
        following ADR-006. Falls back to direct write if vault is not available (development).
        """
        # Try to use Host API first (ADR-006)
        if self.context.vault is not None:
            try:
                # Extract title from content or metadata
                title_match = re.match(r"^#\s+(.+)$", content.split("\n")[0])
                title = title_match.group(1) if title_match else "Inbox item"

                # Prepare entity data
                entity_data = {
                    "title": title,
                    "source": metadata.get("source", "unknown"),
                    "type": metadata.get("type", "text"),
                    "priority": metadata.get("priority", "medium"),
                    "status": "inbox",
                }

                # Add tags if present
                if "tags" in metadata:
                    entity_data["tags"] = metadata["tags"]

                # Create entity via Host API
                entity = self.context.vault.create_entity(
                    entity_type="note",
                    data=entity_data,
                    content=content,
                )

                self.context.logger.info(f"Created entity via Host API: {entity.id}")
                return entity.path if entity.path else self.processed_path / f"{entity.id}.md"

            except Exception as exc:
                self.context.logger.warning(f"Host API unavailable, falling back to direct write: {exc}")

        # Fallback: direct filesystem write (for development/testing without full Host API)
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
        return output_path

    def process_message(self, message: str, source: str | None = None) -> dict[str, object]:
        """Normalize and persist a raw message."""
        normalized = self.normalize_text(message)
        metadata = self.extract_metadata(normalized, source)
        file_path = self.create_normalized_file(normalized, metadata)
        return {
            "success": True,
            "file_path": str(file_path),
            "metadata": metadata,
        }

    def process_file(self, file_path: Path) -> dict[str, object]:
        """Normalize an incoming file by moving it into the processed vault."""
        file_path = Path(file_path)
        content = file_path.read_text(encoding="utf-8")
        metadata = self.extract_metadata(content, source="file")
        normalized_file = self.create_normalized_file(content, metadata)
        original_path = file_path
        if file_path.exists():
            file_path.unlink()
        return {
            "success": True,
            "original_file": str(original_path),
            "processed_file": str(normalized_file),
            "file_path": str(normalized_file),
            "metadata": metadata,
        }


def get_normalizer() -> InboxNormalizer:
    if _NORMALIZER is None:
        raise RuntimeError("Inbox plugin is not activated")
    return _NORMALIZER


def activate(context: PluginContext) -> dict[str, str]:
    """Activate the inbox plugin by initialising the normalizer."""
    global _NORMALIZER
    _NORMALIZER = InboxNormalizer(context)
    context.logger.info("Inbox plugin activated")
    return {"status": "ok", "plugin": "kira-inbox"}


def handle_message_received(context: PluginContext, event_data: dict[str, object]) -> None:
    message = str(event_data.get("message", ""))
    source = event_data.get("source")
    normalizer = get_normalizer()
    result = normalizer.process_message(message, source=source if isinstance(source, str) else None)
    context.logger.debug(f"Normalized message stored at {result['file_path']}")


def handle_file_dropped(context: PluginContext, event_data: dict[str, object]) -> None:
    file_path = Path(str(event_data.get("file_path")))
    normalizer = get_normalizer()
    result = normalizer.process_file(file_path)
    context.logger.debug(f"Normalized file stored at {result['processed_file']}")


def normalize_command(context: PluginContext, args: Iterable[str]) -> str:
    terms = list(args)
    if not terms:
        return "Использование: kira inbox normalize <текст>"

    normalizer = get_normalizer()
    message = " ".join(terms)
    result = normalizer.process_message(message)
    return f"Нормализовано {len(message)} символов -> {result['file_path']}"
