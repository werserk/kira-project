"""Link graph management for Vault entities (ADR-006, ADR-016).

Maintains forward and backward links between entities, ensuring
consistency and preventing orphaned references.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "Link",
    "LinkGraph",
    "LinkType",
    "extract_links_from_content",
    "extract_links_from_frontmatter",
    "find_broken_links",
]


@dataclass(frozen=True)
class Link:
    """Represents a link between two entities."""

    source_id: str
    target_id: str
    link_type: str
    context: dict[str, Any] = field(default_factory=dict, hash=False, compare=False)

    def __str__(self) -> str:
        """String representation."""
        return f"{self.source_id} --{self.link_type}--> {self.target_id}"

    def reverse(self) -> Link:
        """Create reverse link."""
        return Link(
            source_id=self.target_id,
            target_id=self.source_id,
            link_type=f"backlink:{self.link_type}",
            context=self.context.copy(),
        )


class LinkType:
    """Standard link types."""

    # Explicit frontmatter links
    RELATES_TO = "relates_to"
    DEPENDS_ON = "depends_on"
    BLOCKS = "blocks"
    CHILD_OF = "child_of"
    PART_OF = "part_of"
    REFERENCES = "references"

    # Content-based links
    MENTIONS = "mentions"
    LINKS_TO = "links_to"

    # Project relationships
    ASSIGNED_TO = "assigned_to"
    TAGGED_WITH = "tagged_with"

    # Temporal relationships
    FOLLOWS = "follows"
    PRECEDES = "precedes"

    @classmethod
    def get_all_types(cls) -> set[str]:
        """Get all standard link types."""
        return {
            cls.RELATES_TO,
            cls.DEPENDS_ON,
            cls.BLOCKS,
            cls.CHILD_OF,
            cls.PART_OF,
            cls.REFERENCES,
            cls.MENTIONS,
            cls.LINKS_TO,
            cls.ASSIGNED_TO,
            cls.TAGGED_WITH,
            cls.FOLLOWS,
            cls.PRECEDES,
        }

    @classmethod
    def is_bidirectional(cls, link_type: str) -> bool:
        """Check if link type is bidirectional."""
        bidirectional = {cls.RELATES_TO, cls.REFERENCES}
        return link_type in bidirectional


class LinkGraph:
    """Graph of entity relationships with consistency management."""

    def __init__(self) -> None:
        """Initialize empty link graph."""
        self._forward_links: dict[str, set[Link]] = defaultdict(set)
        self._backward_links: dict[str, set[Link]] = defaultdict(set)
        self._entities: set[str] = set()

    def add_entity(self, entity_id: str) -> None:
        """Add entity to graph.

        Parameters
        ----------
        entity_id
            Entity identifier
        """
        self._entities.add(entity_id)

    def remove_entity(self, entity_id: str) -> list[Link]:
        """Remove entity and all its links.

        Parameters
        ----------
        entity_id
            Entity identifier

        Returns
        -------
        list[Link]
            List of removed links
        """
        removed_links: list[Link] = []

        # Remove all outgoing links
        if entity_id in self._forward_links:
            for link in list(self._forward_links[entity_id]):
                removed_links.append(link)
                self.remove_link(link.source_id, link.target_id, link.link_type)

        # Remove all incoming links
        if entity_id in self._backward_links:
            for link in list(self._backward_links[entity_id]):
                removed_links.append(link)
                self.remove_link(link.source_id, link.target_id, link.link_type)

        # Remove entity from registry
        self._entities.discard(entity_id)

        return removed_links

    def add_link(self, source_id: str, target_id: str, link_type: str, context: dict[str, Any] | None = None) -> None:
        """Add link between entities.

        Parameters
        ----------
        source_id
            Source entity ID
        target_id
            Target entity ID
        link_type
            Type of link
        context
            Optional context metadata
        """
        if source_id == target_id:
            return  # No self-links

        link = Link(source_id, target_id, link_type, context or {})

        # Add forward link
        self._forward_links[source_id].add(link)

        # Add backward link
        self._backward_links[target_id].add(link)

        # Register entities
        self._entities.add(source_id)
        self._entities.add(target_id)

        # Add bidirectional link if applicable
        if LinkType.is_bidirectional(link_type):
            reverse_link = link.reverse()
            self._forward_links[target_id].add(reverse_link)
            self._backward_links[source_id].add(reverse_link)

    def remove_link(self, source_id: str, target_id: str, link_type: str) -> bool:
        """Remove specific link.

        Parameters
        ----------
        source_id
            Source entity ID
        target_id
            Target entity ID
        link_type
            Type of link

        Returns
        -------
        bool
            True if link was found and removed
        """
        # Find and remove forward link
        forward_found = False
        for link in list(self._forward_links.get(source_id, [])):
            if link.target_id == target_id and link.link_type == link_type:
                self._forward_links[source_id].remove(link)
                forward_found = True
                break

        # Find and remove backward link
        backward_found = False
        for link in list(self._backward_links.get(target_id, [])):
            if link.source_id == source_id and link.link_type == link_type:
                self._backward_links[target_id].remove(link)
                backward_found = True
                break

        # Handle bidirectional links
        if LinkType.is_bidirectional(link_type):
            reverse_type = f"backlink:{link_type}"
            # Remove reverse links
            for link in list(self._forward_links.get(target_id, [])):
                if link.target_id == source_id and link.link_type == reverse_type:
                    self._forward_links[target_id].remove(link)
                    break
            for link in list(self._backward_links.get(source_id, [])):
                if link.source_id == target_id and link.link_type == reverse_type:
                    self._backward_links[source_id].remove(link)
                    break

        return forward_found and backward_found

    def get_outgoing_links(self, entity_id: str, link_type: str | None = None) -> list[Link]:
        """Get outgoing links from entity.

        Parameters
        ----------
        entity_id
            Source entity ID
        link_type
            Optional link type filter

        Returns
        -------
        list[Link]
            List of outgoing links
        """
        links = list(self._forward_links.get(entity_id, []))

        if link_type:
            links = [link for link in links if link.link_type == link_type]

        return sorted(links, key=lambda l: (l.link_type, l.target_id))

    def get_incoming_links(self, entity_id: str, link_type: str | None = None) -> list[Link]:
        """Get incoming links to entity.

        Parameters
        ----------
        entity_id
            Target entity ID
        link_type
            Optional link type filter

        Returns
        -------
        list[Link]
            List of incoming links
        """
        links = list(self._backward_links.get(entity_id, []))

        if link_type:
            links = [link for link in links if link.link_type == link_type]

        return sorted(links, key=lambda l: (l.link_type, l.source_id))

    def get_all_links(self, entity_id: str) -> list[Link]:
        """Get all links (incoming and outgoing) for entity.

        Parameters
        ----------
        entity_id
            Entity ID

        Returns
        -------
        list[Link]
            All links involving the entity
        """
        outgoing = self.get_outgoing_links(entity_id)
        incoming = self.get_incoming_links(entity_id)
        return outgoing + incoming

    def get_connected_entities(self, entity_id: str, max_depth: int = 1) -> set[str]:
        """Get entities connected to given entity.

        Parameters
        ----------
        entity_id
            Starting entity ID
        max_depth
            Maximum traversal depth

        Returns
        -------
        set[str]
            Connected entity IDs
        """
        connected = set()
        visited = set()
        to_visit = [(entity_id, 0)]

        while to_visit:
            current_id, depth = to_visit.pop(0)

            if current_id in visited or depth > max_depth:
                continue

            visited.add(current_id)

            if depth > 0:  # Don't include starting entity
                connected.add(current_id)

            if depth < max_depth:
                # Add neighbors
                for link in self.get_outgoing_links(current_id):
                    to_visit.append((link.target_id, depth + 1))
                for link in self.get_incoming_links(current_id):
                    to_visit.append((link.source_id, depth + 1))

        return connected

    def find_orphaned_entities(self) -> set[str]:
        """Find entities with no links.

        Returns
        -------
        set[str]
            Orphaned entity IDs
        """
        orphaned = set()

        for entity_id in self._entities:
            if not self.get_all_links(entity_id):
                orphaned.add(entity_id)

        return orphaned

    def find_broken_links(self, existing_entities: set[str]) -> list[Link]:
        """Find links pointing to non-existent entities.

        Parameters
        ----------
        existing_entities
            Set of known entity IDs

        Returns
        -------
        list[Link]
            List of broken links
        """
        broken = []

        for links in self._forward_links.values():
            for link in links:
                if link.target_id not in existing_entities:
                    broken.append(link)

        return broken

    def find_cycles(self, link_type: str = LinkType.DEPENDS_ON) -> list[list[str]]:
        """Find cycles in directed graph for specific link type (ADR-016).

        Parameters
        ----------
        link_type
            Link type to check for cycles (default: depends_on)

        Returns
        -------
        list[list[str]]
            List of cycles, each cycle is a list of entity IDs
        """
        cycles = []
        visited = set()
        rec_stack = set()
        path = []

        def dfs(node: str) -> bool:
            """DFS to detect cycles."""
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            # Check all dependencies
            for link in self.get_outgoing_links(node, link_type):
                target = link.target_id

                if target not in visited:
                    if dfs(target):
                        return True
                elif target in rec_stack:
                    # Found cycle - extract cycle from path
                    cycle_start = path.index(target)
                    cycle = path[cycle_start:] + [target]
                    cycles.append(cycle)
                    return True

            path.pop()
            rec_stack.remove(node)
            return False

        # Check all nodes
        for entity_id in self._entities:
            if entity_id not in visited:
                dfs(entity_id)

        return cycles

    def get_stats(self) -> dict[str, Any]:
        """Get link graph statistics.

        Returns
        -------
        dict[str, Any]
            Statistics
        """
        total_links = sum(len(links) for links in self._forward_links.values())
        link_types: dict[str, int] = defaultdict(int)

        for links in self._forward_links.values():
            for link in links:
                link_types[link.link_type] += 1

        return {
            "total_entities": len(self._entities),
            "total_links": total_links,
            "link_types": dict(link_types),
            "orphaned_entities": len(self.find_orphaned_entities()),
        }


def extract_links_from_frontmatter(frontmatter: dict[str, Any]) -> list[tuple[str, str]]:
    """Extract links from entity frontmatter.

    Parameters
    ----------
    frontmatter
        Entity frontmatter

    Returns
    -------
    list[tuple[str, str]]
        List of (link_type, target_id) tuples
    """
    links = []

    # Direct link fields
    link_fields = {
        "relates_to": LinkType.RELATES_TO,
        "depends_on": LinkType.DEPENDS_ON,
        "blocks": LinkType.BLOCKS,
        "child_of": LinkType.CHILD_OF,
        "part_of": LinkType.PART_OF,
        "references": LinkType.REFERENCES,
    }

    for field_name, link_type in link_fields.items():
        if field_name in frontmatter:
            value = frontmatter[field_name]
            if isinstance(value, str):
                links.append((link_type, value))
            elif isinstance(value, list):
                for target in value:
                    if isinstance(target, str):
                        links.append((link_type, target))

    # Tags as special links
    if "tags" in frontmatter:
        tags = frontmatter["tags"]
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str):
                    links.append((LinkType.TAGGED_WITH, f"tag-{tag}"))

    return links


def extract_links_from_content(content: str) -> list[tuple[str, str]]:
    """Extract links from Markdown content.

    Parameters
    ----------
    content
        Markdown content

    Returns
    -------
    list[tuple[str, str]]
        List of (link_type, target_id) tuples
    """
    links: list[tuple[str, str]] = []

    if not content:
        return links

    # Wiki-style links: [[entity-id]]
    wiki_pattern = r"\[\[([a-z0-9][a-z0-9-]+)\]\]"
    for match in re.finditer(wiki_pattern, content):
        entity_id = match.group(1)
        links.append((LinkType.LINKS_TO, entity_id))

    # Entity mentions: @entity-id
    mention_pattern = r"@([a-z0-9][a-z0-9-]+)"
    for match in re.finditer(mention_pattern, content):
        entity_id = match.group(1)
        links.append((LinkType.MENTIONS, entity_id))

    return links


def find_broken_links(
    entity_id: str,
    frontmatter: dict[str, Any],
    content: str,
    existing_entities: set[str],
) -> list[str]:
    """Find broken links in entity.

    Parameters
    ----------
    entity_id
        Entity ID
    frontmatter
        Entity frontmatter
    content
        Entity content
    existing_entities
        Set of known entity IDs

    Returns
    -------
    list[str]
        List of broken link target IDs
    """
    broken = []

    # Extract all links
    fm_links = extract_links_from_frontmatter(frontmatter)
    content_links = extract_links_from_content(content)

    all_links = fm_links + content_links

    # Check each target
    for _link_type, target_id in all_links:
        if target_id.startswith("tag-"):
            # Tags are always valid
            continue

        if target_id not in existing_entities:
            broken.append(target_id)

    return broken


def update_entity_links(
    link_graph: LinkGraph,
    entity_id: str,
    frontmatter: dict[str, Any],
    content: str,
) -> None:
    """Update entity links in graph.

    Parameters
    ----------
    link_graph
        Link graph to update
    entity_id
        Entity ID
    frontmatter
        Entity frontmatter
    content
        Entity content
    """
    # Remove existing outgoing links
    existing_links = link_graph.get_outgoing_links(entity_id)
    for link in existing_links:
        link_graph.remove_link(link.source_id, link.target_id, link.link_type)

    # Extract and add new links
    fm_links = extract_links_from_frontmatter(frontmatter)
    content_links = extract_links_from_content(content)

    all_links = fm_links + content_links

    for link_type, target_id in all_links:
        link_graph.add_link(entity_id, target_id, link_type)
