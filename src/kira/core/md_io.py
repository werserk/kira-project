"""Markdown I/O with YAML frontmatter support (ADR-006).

Provides atomic read/write operations for Markdown files with
structured frontmatter metadata.

Phase 0, Point 2: Uses deterministic YAML serialization for consistency.
"""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from .yaml_serializer import parse_frontmatter, serialize_frontmatter

__all__ = [
    "MarkdownDocument",
    "MarkdownIOError",
    "parse_markdown",
    "read_markdown",
    "write_markdown",
]


class MarkdownIOError(Exception):
    """Raised when Markdown I/O operations fail."""

    pass


@dataclass
class MarkdownDocument:
    """Container for Markdown document with frontmatter.

    Attributes
    ----------
    frontmatter : dict[str, Any]
        YAML frontmatter metadata
    content : str
        Markdown content body
    """

    frontmatter: dict[str, Any]
    content: str

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get frontmatter metadata value.

        Parameters
        ----------
        key
            Metadata key
        default
            Default value if key not found

        Returns
        -------
        Any
            Metadata value
        """
        return self.frontmatter.get(key, default)

    def set_metadata(self, key: str, value: Any) -> None:
        """Set frontmatter metadata value.

        Parameters
        ----------
        key
            Metadata key
        value
            Metadata value
        """
        self.frontmatter[key] = value

    def has_metadata(self, key: str) -> bool:
        """Check if metadata key exists.

        Parameters
        ----------
        key
            Metadata key

        Returns
        -------
        bool
            True if key exists
        """
        return key in self.frontmatter

    def to_markdown_string(self) -> str:
        """Convert to full Markdown string with frontmatter.
        
        Uses deterministic serialization (Phase 0, Point 2) with:
        - Fixed key ordering
        - ISO-8601 UTC timestamps
        - Consistent formatting

        Returns
        -------
        str
            Full Markdown document
        """
        if not self.frontmatter:
            return self.content

        # Serialize frontmatter using deterministic serializer (Phase 0, Point 2)
        frontmatter_yaml = serialize_frontmatter(self.frontmatter)

        # Assemble document
        parts = ["---", frontmatter_yaml, "---"]

        if self.content.strip():
            parts.extend(["", self.content])

        return "\n".join(parts)


def parse_markdown(content: str) -> MarkdownDocument:
    """Parse Markdown content with optional frontmatter.

    Parameters
    ----------
    content
        Raw Markdown content

    Returns
    -------
    MarkdownDocument
        Parsed document

    Raises
    ------
    MarkdownIOError
        If parsing fails
    """
    if not content.strip():
        return MarkdownDocument(frontmatter={}, content="")

    # Check for frontmatter
    if not content.startswith("---"):
        # No frontmatter, just content
        return MarkdownDocument(frontmatter={}, content=content)

    try:
        # Split frontmatter and content
        parts = content.split("---", 2)

        if len(parts) < 3:
            # Malformed frontmatter, treat as regular content
            return MarkdownDocument(frontmatter={}, content=content)

        frontmatter_raw = parts[1].strip()
        markdown_content = parts[2].lstrip("\n") if len(parts) > 2 else ""

        # Parse YAML frontmatter using deterministic parser (Phase 0, Point 2)
        if frontmatter_raw:
            try:
                frontmatter = parse_frontmatter(frontmatter_raw)
            except ValueError as exc:
                raise MarkdownIOError(str(exc)) from exc
        else:
            frontmatter = {}

        return MarkdownDocument(frontmatter=frontmatter, content=markdown_content)

    except Exception as exc:
        if isinstance(exc, MarkdownIOError):
            raise
        raise MarkdownIOError(f"Failed to parse Markdown: {exc}") from exc


def read_markdown(file_path: Path | str) -> MarkdownDocument:
    """Read Markdown file with frontmatter.

    Parameters
    ----------
    file_path
        Path to Markdown file

    Returns
    -------
    MarkdownDocument
        Parsed document

    Raises
    ------
    MarkdownIOError
        If read fails
    """
    path = Path(file_path)

    try:
        content = path.read_text(encoding="utf-8")
        return parse_markdown(content)
    except FileNotFoundError as exc:
        raise MarkdownIOError(f"File not found: {path}") from exc
    except UnicodeDecodeError as exc:
        raise MarkdownIOError(f"File encoding error: {path} - {exc}") from exc
    except Exception as exc:
        raise MarkdownIOError(f"Failed to read {path}: {exc}") from exc


def write_markdown(
    file_path: Path | str,
    document: MarkdownDocument,
    *,
    atomic: bool = True,
    create_dirs: bool = True,
) -> None:
    """Write Markdown document to file.

    Parameters
    ----------
    file_path
        Target file path
    document
        Document to write
    atomic
        Use atomic write (temp file + rename)
    create_dirs
        Create parent directories if needed

    Raises
    ------
    MarkdownIOError
        If write fails
    """
    path = Path(file_path)

    try:
        # Create parent directories if needed
        if create_dirs and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)

        # Generate document content
        content = document.to_markdown_string()

        if atomic:
            # Atomic write: temp file + rename
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.tmp",
                delete=False,
            ) as tmp_file:
                tmp_file.write(content)
                tmp_file.flush()
                tmp_path = Path(tmp_file.name)

            # Atomic rename
            tmp_path.rename(path)
        else:
            # Direct write
            path.write_text(content, encoding="utf-8")

    except Exception as exc:
        raise MarkdownIOError(f"Failed to write {path}: {exc}") from exc


def update_frontmatter(
    file_path: Path | str,
    updates: dict[str, Any],
    *,
    create_if_missing: bool = False,
) -> MarkdownDocument:
    """Update frontmatter in existing Markdown file.

    Parameters
    ----------
    file_path
        Path to Markdown file
    updates
        Frontmatter updates to apply
    create_if_missing
        Create file if it doesn't exist

    Returns
    -------
    MarkdownDocument
        Updated document

    Raises
    ------
    MarkdownIOError
        If update fails
    """
    path = Path(file_path)

    try:
        if path.exists():
            document = read_markdown(path)
        elif create_if_missing:
            document = MarkdownDocument(frontmatter={}, content="")
        else:
            raise MarkdownIOError(f"File not found: {path}")

        # Apply updates
        document.frontmatter.update(updates)

        # Write back
        write_markdown(path, document)

        return document

    except Exception as exc:
        if isinstance(exc, MarkdownIOError):
            raise
        raise MarkdownIOError(f"Failed to update frontmatter in {path}: {exc}") from exc


def extract_title(document: MarkdownDocument) -> str | None:
    """Extract title from document.

    Looks for title in frontmatter first, then first H1 in content.

    Parameters
    ----------
    document
        Markdown document

    Returns
    -------
    str or None
        Extracted title
    """
    # Check frontmatter first
    title = document.get_metadata("title")
    if title:
        return str(title).strip()

    # Look for first H1 in content
    if not document.content:
        return None

    h1_match = re.search(r"^#\s+(.+)$", document.content, re.MULTILINE)
    if h1_match:
        return h1_match.group(1).strip()

    return None


def validate_frontmatter(frontmatter: dict[str, Any], required_fields: list[str]) -> list[str]:
    """Validate frontmatter has required fields.

    Parameters
    ----------
    frontmatter
        Frontmatter to validate
    required_fields
        List of required field names

    Returns
    -------
    list[str]
        List of missing fields (empty if valid)
    """
    missing = []
    for field in required_fields:
        if field not in frontmatter:
            missing.append(field)
        elif frontmatter[field] is None or frontmatter[field] == "":
            missing.append(field)
    return missing


def merge_frontmatter(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """Merge frontmatter dictionaries.

    Parameters
    ----------
    base
        Base frontmatter
    updates
        Updates to apply

    Returns
    -------
    dict[str, Any]
        Merged frontmatter
    """
    result = base.copy()

    for key, value in updates.items():
        if isinstance(value, dict) and key in result and isinstance(result[key], dict):
            # Deep merge for nested dicts
            result[key] = merge_frontmatter(result[key], value)
        else:
            # Direct assignment
            result[key] = value

    return result


def normalize_frontmatter_dates(frontmatter: dict[str, Any]) -> dict[str, Any]:
    """Normalize date fields in frontmatter to ISO format.

    Parameters
    ----------
    frontmatter
        Frontmatter to normalize

    Returns
    -------
    dict[str, Any]
        Normalized frontmatter
    """
    import datetime

    result = frontmatter.copy()
    date_fields = {"created", "updated", "due_date", "start_time", "end_time"}

    for key, value in result.items():
        if key in date_fields and value:
            if isinstance(value, datetime.datetime):
                result[key] = value.isoformat()
            elif isinstance(value, datetime.date):
                result[key] = value.isoformat()
            elif isinstance(value, str):
                try:
                    # Try to parse and reformat
                    dt = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
                    result[key] = dt.isoformat()
                except ValueError:
                    # Keep as-is if can't parse
                    pass

    return result
