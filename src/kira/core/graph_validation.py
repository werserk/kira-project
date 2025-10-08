"""Graph validation and consistency checks (ADR-016).

Provides tools for finding orphans, cycles, duplicates, and broken links
in the knowledge graph to maintain data integrity.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import TYPE_CHECKING, Any

from .links import LinkGraph, LinkType

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "DuplicateCandidate",
    "GraphValidator",
    "ValidationReport",
    "find_duplicates",
    "normalize_title",
]


@dataclass
class DuplicateCandidate:
    """Represents a potential duplicate entity."""

    entity_id_1: str
    entity_id_2: str
    similarity: float
    reason: str
    metadata: dict[str, Any]


@dataclass
class ValidationReport:
    """Comprehensive validation report for knowledge graph."""

    orphans: list[str]
    cycles: list[list[str]]
    broken_links: list[tuple[str, str]]  # (source_id, target_id)
    duplicates: list[DuplicateCandidate]
    total_entities: int
    total_links: int

    def has_issues(self) -> bool:
        """Check if report has any issues."""
        return bool(self.orphans or self.cycles or self.broken_links or self.duplicates)

    def issue_count(self) -> int:
        """Count total issues."""
        return len(self.orphans) + len(self.cycles) + len(self.broken_links) + len(self.duplicates)


class GraphValidator:
    """Validates knowledge graph consistency (ADR-016).

    Performs automated checks for:
    - Orphaned entities (no incoming/outgoing links)
    - Cycles in dependency graphs
    - Broken wikilinks and references
    - Duplicate entities (by title + context)

    Example:
        >>> validator = GraphValidator(vault_root=Path(".kira/vault"))
        >>> report = validator.validate()
        >>> if report.has_issues():
        ...     print(f"Found {report.issue_count()} issues")
    """

    def __init__(
        self,
        *,
        vault_root: Path,
        link_graph: LinkGraph | None = None,
        ignore_folders: list[str] | None = None,
        ignore_kinds: list[str] | None = None,
    ) -> None:
        """Initialize graph validator.

        Parameters
        ----------
        vault_root
            Path to vault root directory
        link_graph
            Optional pre-built link graph
        ignore_folders
            Folders to ignore for orphan detection
        ignore_kinds
            Entity kinds to ignore for orphan detection
        """
        self.vault_root = vault_root
        self.link_graph = link_graph or LinkGraph()
        self.ignore_folders = ignore_folders or ["@Indexes", "@Templates"]
        self.ignore_kinds = ignore_kinds or ["tag", "index", "template"]

        self._entities: dict[str, dict[str, Any]] = {}
        self._load_entities()

    def _load_entities(self) -> None:
        """Load entities from vault."""
        if not self.vault_root.exists():
            return

        for md_file in self.vault_root.rglob("*.md"):
            # Skip ignored folders
            if any(folder in md_file.parts for folder in self.ignore_folders):
                continue

            entity_id = md_file.stem

            # Extract basic metadata
            try:
                content = md_file.read_text()
                title, kind = self._extract_metadata(content)

                self._entities[entity_id] = {
                    "path": md_file,
                    "title": title,
                    "kind": kind,
                    "content": content,
                }

                # Add to link graph
                self.link_graph.add_entity(entity_id)

            except Exception:
                continue

    def _extract_metadata(self, content: str) -> tuple[str, str]:
        """Extract title and kind from content.

        Parameters
        ----------
        content
            File content

        Returns
        -------
        tuple[str, str]
            (title, kind)
        """
        title = "Untitled"
        kind = "note"

        # Extract from frontmatter
        if content.startswith("---"):
            lines = content.split("\n")
            for line in lines[1:]:
                if line.strip() == "---":
                    break
                if line.startswith("title:"):
                    title = line.split(":", 1)[1].strip()
                elif line.startswith("kind:") or line.startswith("type:"):
                    kind = line.split(":", 1)[1].strip()

        return title, kind

    def validate(self) -> ValidationReport:
        """Run all validation checks.

        Returns
        -------
        ValidationReport
            Comprehensive validation report
        """
        orphans = self.find_orphans()
        cycles = self.find_cycles()
        broken_links = self.find_broken_links()
        duplicates = self.find_duplicates()

        stats = self.link_graph.get_stats()

        return ValidationReport(
            orphans=orphans,
            cycles=cycles,
            broken_links=broken_links,
            duplicates=duplicates,
            total_entities=stats["total_entities"],
            total_links=stats["total_links"],
        )

    def find_orphans(self) -> list[str]:
        """Find orphaned entities (ADR-016).

        Returns
        -------
        list[str]
            List of orphaned entity IDs
        """
        orphaned = []

        for entity_id, metadata in self._entities.items():
            # Skip ignored kinds
            if metadata["kind"] in self.ignore_kinds:
                continue

            # Check if has any links
            all_links = self.link_graph.get_all_links(entity_id)

            if not all_links:
                orphaned.append(entity_id)

        return orphaned

    def find_cycles(self) -> list[list[str]]:
        """Find cycles in dependency graph (ADR-016).

        Returns
        -------
        list[list[str]]
            List of cycles (each is a list of entity IDs forming the cycle)
        """
        return self.link_graph.find_cycles(LinkType.DEPENDS_ON)

    def find_broken_links(self) -> list[tuple[str, str]]:
        """Find broken wikilinks and references (ADR-016).

        Returns
        -------
        list[tuple[str, str]]
            List of (source_id, target_id) pairs with broken links
        """
        broken = []
        existing_ids = set(self._entities.keys())

        # Check all links in graph
        for entity_id in self._entities:
            for link in self.link_graph.get_outgoing_links(entity_id):
                # Skip tag links
                if link.target_id.startswith("tag-"):
                    continue

                if link.target_id not in existing_ids:
                    broken.append((entity_id, link.target_id))

        return broken

    def find_duplicates(
        self,
        similarity_threshold: float = 0.85,
    ) -> list[DuplicateCandidate]:
        """Find potential duplicate entities (ADR-016).

        Uses normalized title + kind matching with fuzzy string comparison.

        Parameters
        ----------
        similarity_threshold
            Minimum similarity score (0.0 - 1.0)

        Returns
        -------
        list[DuplicateCandidate]
            List of potential duplicates
        """
        duplicates = []

        # Group by kind first
        by_kind: dict[str, list[str]] = defaultdict(list)

        for entity_id, metadata in self._entities.items():
            kind = metadata["kind"]
            by_kind[kind].append(entity_id)

        # Check within each kind
        for kind, entity_ids in by_kind.items():
            for i, id1 in enumerate(entity_ids):
                for id2 in entity_ids[i + 1 :]:
                    metadata1 = self._entities[id1]
                    metadata2 = self._entities[id2]

                    # Normalize titles
                    title1 = normalize_title(metadata1["title"])
                    title2 = normalize_title(metadata2["title"])

                    # Calculate similarity
                    similarity = SequenceMatcher(None, title1, title2).ratio()

                    if similarity >= similarity_threshold:
                        duplicates.append(
                            DuplicateCandidate(
                                entity_id_1=id1,
                                entity_id_2=id2,
                                similarity=similarity,
                                reason=f"Similar titles: '{metadata1['title']}' vs '{metadata2['title']}'",
                                metadata={
                                    "kind": kind,
                                    "title1": metadata1["title"],
                                    "title2": metadata2["title"],
                                },
                            )
                        )

        return duplicates


def normalize_title(title: str) -> str:
    """Normalize title for comparison (ADR-016).

    Parameters
    ----------
    title
        Original title

    Returns
    -------
    str
        Normalized title
    """
    # Lowercase
    normalized = title.lower()

    # Remove punctuation
    normalized = re.sub(r"[^\w\s-]", "", normalized)

    # Remove extra whitespace
    normalized = " ".join(normalized.split())

    # Remove common words
    stop_words = {"a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for"}
    words = normalized.split()
    words = [w for w in words if w not in stop_words]
    normalized = " ".join(words)

    return normalized.strip()


def find_duplicates(
    entities: dict[str, dict[str, Any]],
    similarity_threshold: float = 0.85,
) -> list[DuplicateCandidate]:
    """Standalone function to find duplicates.

    Parameters
    ----------
    entities
        Dictionary of entity_id -> metadata
    similarity_threshold
        Minimum similarity score

    Returns
    -------
    list[DuplicateCandidate]
        Potential duplicates
    """
    duplicates = []

    # Group by kind
    by_kind: dict[str, list[str]] = defaultdict(list)

    for entity_id, metadata in entities.items():
        kind = metadata.get("kind", "note")
        by_kind[kind].append(entity_id)

    # Check within each kind
    for kind, entity_ids in by_kind.items():
        for i, id1 in enumerate(entity_ids):
            for id2 in entity_ids[i + 1 :]:
                title1 = normalize_title(entities[id1].get("title", ""))
                title2 = normalize_title(entities[id2].get("title", ""))

                similarity = SequenceMatcher(None, title1, title2).ratio()

                if similarity >= similarity_threshold:
                    duplicates.append(
                        DuplicateCandidate(
                            entity_id_1=id1,
                            entity_id_2=id2,
                            similarity=similarity,
                            reason=f"Similar titles in kind '{kind}'",
                            metadata={
                                "kind": kind,
                                "title1": entities[id1].get("title", ""),
                                "title2": entities[id2].get("title", ""),
                            },
                        )
                    )

    return duplicates
