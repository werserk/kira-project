"""Tests for graph validation (ADR-016)."""

import tempfile
from pathlib import Path

from kira.core.graph_validation import (
    DuplicateCandidate,
    GraphValidator,
    ValidationReport,
    find_duplicates,
    normalize_title,
)
from kira.core.links import LinkGraph, LinkType


class TestNormalizeTitle:
    """Test title normalization."""

    def test_lowercase(self):
        """Test lowercase conversion."""
        assert normalize_title("Hello World") == "hello world"

    def test_remove_punctuation(self):
        """Test punctuation removal."""
        assert normalize_title("Hello, World!") == "hello world"

    def test_remove_extra_whitespace(self):
        """Test whitespace normalization."""
        assert normalize_title("Hello   World") == "hello world"

    def test_remove_stop_words(self):
        """Test stop word removal."""
        result = normalize_title("The quick brown fox")
        assert "the" not in result
        assert "quick" in result
        assert "brown" in result

    def test_complex_title(self):
        """Test complex title normalization."""
        title = "How to Build a REST API in Python"
        normalized = normalize_title(title)

        assert "how" in normalized
        assert "build" in normalized
        assert "rest" in normalized
        assert "api" in normalized
        assert "python" in normalized


class TestDuplicateCandidate:
    """Test DuplicateCandidate dataclass."""

    def test_create_duplicate_candidate(self):
        """Test creating duplicate candidate."""
        dup = DuplicateCandidate(
            entity_id_1="task-1",
            entity_id_2="task-2",
            similarity=0.95,
            reason="Similar titles",
            metadata={"kind": "task"},
        )

        assert dup.entity_id_1 == "task-1"
        assert dup.entity_id_2 == "task-2"
        assert dup.similarity == 0.95
        assert dup.reason == "Similar titles"


class TestValidationReport:
    """Test ValidationReport dataclass."""

    def test_has_issues_with_problems(self):
        """Test has_issues when problems exist."""
        report = ValidationReport(
            orphans=["orphan-1"],
            cycles=[],
            broken_links=[],
            duplicates=[],
            total_entities=10,
            total_links=5,
        )

        assert report.has_issues()

    def test_has_issues_clean(self):
        """Test has_issues when clean."""
        report = ValidationReport(
            orphans=[],
            cycles=[],
            broken_links=[],
            duplicates=[],
            total_entities=10,
            total_links=5,
        )

        assert not report.has_issues()

    def test_issue_count(self):
        """Test issue count calculation."""
        report = ValidationReport(
            orphans=["o1", "o2"],
            cycles=[["c1", "c2"]],
            broken_links=[("b1", "b2"), ("b3", "b4")],
            duplicates=[
                DuplicateCandidate("d1", "d2", 0.9, "test", {}),
            ],
            total_entities=10,
            total_links=5,
        )

        assert report.issue_count() == 6  # 2 + 1 + 2 + 1


class TestLinkGraphCycleDetection:
    """Test cycle detection in link graph."""

    def setup_method(self):
        """Setup test fixtures."""
        self.graph = LinkGraph()

    def test_no_cycles_empty_graph(self):
        """Test empty graph has no cycles."""
        cycles = self.graph.find_cycles()
        assert len(cycles) == 0

    def test_no_cycles_linear_chain(self):
        """Test linear dependency chain has no cycles."""
        self.graph.add_link("task-1", "task-2", LinkType.DEPENDS_ON)
        self.graph.add_link("task-2", "task-3", LinkType.DEPENDS_ON)
        self.graph.add_link("task-3", "task-4", LinkType.DEPENDS_ON)

        cycles = self.graph.find_cycles()
        assert len(cycles) == 0

    def test_simple_cycle(self):
        """Test simple A→B→A cycle."""
        self.graph.add_link("task-1", "task-2", LinkType.DEPENDS_ON)
        self.graph.add_link("task-2", "task-1", LinkType.DEPENDS_ON)

        cycles = self.graph.find_cycles()

        assert len(cycles) == 1
        cycle = cycles[0]
        assert "task-1" in cycle
        assert "task-2" in cycle

    def test_three_node_cycle(self):
        """Test A→B→C→A cycle."""
        self.graph.add_link("task-1", "task-2", LinkType.DEPENDS_ON)
        self.graph.add_link("task-2", "task-3", LinkType.DEPENDS_ON)
        self.graph.add_link("task-3", "task-1", LinkType.DEPENDS_ON)

        cycles = self.graph.find_cycles()

        assert len(cycles) == 1
        cycle = cycles[0]
        assert len(cycle) >= 3

    def test_self_cycle_ignored(self):
        """Test self-cycles are prevented."""
        # LinkGraph should prevent self-links
        self.graph.add_link("task-1", "task-1", LinkType.DEPENDS_ON)

        # Should have no effect
        links = self.graph.get_outgoing_links("task-1")
        assert len(links) == 0

    def test_multiple_cycles(self):
        """Test multiple separate cycles."""
        # Cycle 1: A→B→A
        self.graph.add_link("a", "b", LinkType.DEPENDS_ON)
        self.graph.add_link("b", "a", LinkType.DEPENDS_ON)

        # Cycle 2: C→D→C
        self.graph.add_link("c", "d", LinkType.DEPENDS_ON)
        self.graph.add_link("d", "c", LinkType.DEPENDS_ON)

        cycles = self.graph.find_cycles()

        assert len(cycles) >= 2


class TestFindDuplicates:
    """Test duplicate detection."""

    def test_no_duplicates(self):
        """Test entities with different titles."""
        entities = {
            "task-1": {"title": "Write tests", "kind": "task"},
            "task-2": {"title": "Review code", "kind": "task"},
            "task-3": {"title": "Deploy app", "kind": "task"},
        }

        duplicates = find_duplicates(entities, similarity_threshold=0.85)

        assert len(duplicates) == 0

    def test_exact_duplicate_titles(self):
        """Test exact duplicate titles."""
        entities = {
            "task-1": {"title": "Fix bug in auth", "kind": "task"},
            "task-2": {"title": "Fix bug in auth", "kind": "task"},
        }

        duplicates = find_duplicates(entities, similarity_threshold=0.85)

        assert len(duplicates) == 1
        dup = duplicates[0]
        assert dup.similarity == 1.0

    def test_similar_titles(self):
        """Test similar but not identical titles."""
        entities = {
            "task-1": {"title": "Fix authentication bug", "kind": "task"},
            "task-2": {"title": "Fix authentication issue", "kind": "task"},
        }

        duplicates = find_duplicates(entities, similarity_threshold=0.70)

        assert len(duplicates) >= 1

    def test_different_kinds_separate(self):
        """Test entities of different kinds are not compared."""
        entities = {
            "task-1": {"title": "Important work", "kind": "task"},
            "note-1": {"title": "Important work", "kind": "note"},
        }

        duplicates = find_duplicates(entities, similarity_threshold=0.85)

        # Should not find duplicates across different kinds
        assert len(duplicates) == 0

    def test_threshold_filtering(self):
        """Test similarity threshold filtering."""
        entities = {
            "task-1": {"title": "Write documentation", "kind": "task"},
            "task-2": {"title": "Write docs", "kind": "task"},
        }

        # Lower threshold should find match
        duplicates_low = find_duplicates(entities, similarity_threshold=0.50)
        assert len(duplicates_low) >= 1

        # Higher threshold might not
        duplicates_high = find_duplicates(entities, similarity_threshold=0.95)
        assert len(duplicates_high) == 0

    def test_multiple_duplicates(self):
        """Test finding multiple duplicate pairs."""
        entities = {
            "task-1": {"title": "Fix bug", "kind": "task"},
            "task-2": {"title": "Fix bug", "kind": "task"},
            "task-3": {"title": "Fix bug", "kind": "task"},
        }

        duplicates = find_duplicates(entities, similarity_threshold=0.85)

        # Should find multiple pairs (1-2, 1-3, 2-3)
        assert len(duplicates) >= 3


class TestGraphValidator:
    """Test GraphValidator class."""

    def setup_method(self):
        """Setup test fixtures."""
        # Create temporary vault
        self.temp_dir = tempfile.mkdtemp()
        self.vault_root = Path(self.temp_dir) / "vault"
        self.vault_root.mkdir()

        # Create some test entities
        self._create_entity("task-1", "Fix authentication", "task")
        self._create_entity("task-2", "Write tests", "task")
        self._create_entity("note-1", "Meeting notes", "note")

    def _create_entity(self, entity_id: str, title: str, kind: str) -> None:
        """Helper to create entity file."""
        content = f"""---
title: {title}
kind: {kind}
---

# {title}

Some content here.
"""
        entity_file = self.vault_root / f"{entity_id}.md"
        entity_file.write_text(content)

    def test_validator_initialization(self):
        """Test validator initialization."""
        validator = GraphValidator(vault_root=self.vault_root)

        assert validator.vault_root == self.vault_root
        assert len(validator._entities) == 3

    def test_find_orphans(self):
        """Test finding orphaned entities."""
        validator = GraphValidator(vault_root=self.vault_root)

        orphans = validator.find_orphans()

        # All entities are orphans (no links)
        assert len(orphans) == 3

    def test_find_orphans_with_links(self):
        """Test orphans excludes linked entities."""
        # Add link between entities
        validator = GraphValidator(vault_root=self.vault_root)
        validator.link_graph.add_link("task-1", "task-2", LinkType.DEPENDS_ON)

        orphans = validator.find_orphans()

        # task-1 and task-2 should not be orphans
        assert "task-1" not in orphans
        assert "task-2" not in orphans

    def test_find_broken_links(self):
        """Test finding broken links."""
        validator = GraphValidator(vault_root=self.vault_root)

        # Add link to non-existent entity
        validator.link_graph.add_link("task-1", "task-999", LinkType.DEPENDS_ON)

        broken = validator.find_broken_links()

        assert len(broken) >= 1
        assert ("task-1", "task-999") in broken

    def test_find_duplicates(self):
        """Test finding duplicate entities."""
        # Create duplicate
        self._create_entity("task-3", "Fix authentication", "task")

        validator = GraphValidator(vault_root=self.vault_root)
        duplicates = validator.find_duplicates(similarity_threshold=0.85)

        assert len(duplicates) >= 1

    def test_validate_all(self):
        """Test comprehensive validation."""
        validator = GraphValidator(vault_root=self.vault_root)

        report = validator.validate()

        assert isinstance(report, ValidationReport)
        assert report.total_entities == 3
        assert report.orphans  # All are orphans
        assert len(report.cycles) == 0
        assert len(report.broken_links) == 0

    def test_validate_with_issues(self):
        """Test validation with all issue types."""
        # Add cycle
        validator = GraphValidator(vault_root=self.vault_root)
        validator.link_graph.add_link("task-1", "task-2", LinkType.DEPENDS_ON)
        validator.link_graph.add_link("task-2", "task-1", LinkType.DEPENDS_ON)

        # Add broken link
        validator.link_graph.add_link("task-1", "missing", LinkType.REFERENCES)

        # Create duplicate
        self._create_entity("task-3", "Fix authentication", "task")
        validator._load_entities()

        report = validator.validate()

        assert report.has_issues()
        assert len(report.cycles) >= 1
        assert len(report.broken_links) >= 1

    def test_ignore_folders(self):
        """Test ignoring specific folders."""
        # Create entity in ignored folder
        indexes_dir = self.vault_root / "@Indexes"
        indexes_dir.mkdir()
        (indexes_dir / "index-1.md").write_text("# Index")

        validator = GraphValidator(
            vault_root=self.vault_root,
            ignore_folders=["@Indexes"],
        )

        # Should not load ignored entities
        assert "index-1" not in validator._entities

    def test_ignore_kinds(self):
        """Test ignoring specific kinds."""
        self._create_entity("template-1", "Template", "template")

        validator = GraphValidator(
            vault_root=self.vault_root,
            ignore_kinds=["template"],
        )

        orphans = validator.find_orphans()

        # Template should not be in orphans
        assert "template-1" not in orphans


class TestGraphValidationIntegration:
    """Integration tests for graph validation."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.vault_root = Path(self.temp_dir) / "vault"
        self.vault_root.mkdir()

    def _create_entity(
        self,
        entity_id: str,
        title: str,
        kind: str,
        content: str = "",
        **frontmatter,
    ) -> None:
        """Helper to create entity."""
        fm_lines = [f"title: {title}", f"kind: {kind}"]

        for key, value in frontmatter.items():
            if isinstance(value, list):
                fm_lines.append(f"{key}:")
                for item in value:
                    fm_lines.append(f"  - {item}")
            else:
                fm_lines.append(f"{key}: {value}")

        full_content = "---\n" + "\n".join(fm_lines) + "\n---\n\n" + content

        (self.vault_root / f"{entity_id}.md").write_text(full_content)

    def test_full_validation_workflow(self):
        """Test complete validation workflow."""
        # Create entities with various issues
        self._create_entity("task-1", "Build feature", "task", depends_on="task-2")
        self._create_entity("task-2", "Test feature", "task", depends_on="task-1")
        self._create_entity("task-3", "Build feature", "task")  # Duplicate
        self._create_entity("orphan", "Lonely task", "task")  # Orphan

        # Create entity with broken link
        self._create_entity(
            "task-4",
            "Deploy",
            "task",
            content="Depends on [[missing-task]]",
        )

        # Validate
        validator = GraphValidator(vault_root=self.vault_root)

        # Load links from frontmatter
        for entity_id, metadata in validator._entities.items():
            # Simple frontmatter parsing for test
            content = metadata["content"]
            if "depends_on:" in content:
                # Extract dependency
                for line in content.split("\n"):
                    if line.startswith("depends_on:"):
                        dep = line.split(":", 1)[1].strip()
                        validator.link_graph.add_link(entity_id, dep, LinkType.DEPENDS_ON)

        report = validator.validate()

        # Should find issues
        assert report.has_issues()
        assert len(report.cycles) >= 1  # task-1 ↔ task-2
        assert len(report.orphans) >= 1  # orphan task
        assert len(report.duplicates) >= 1  # task-1 & task-3

    def test_validation_report_serialization(self):
        """Test report can be used for documentation."""
        self._create_entity("task-1", "Task", "task")

        validator = GraphValidator(vault_root=self.vault_root)
        report = validator.validate()

        # Report should have usable data
        assert isinstance(report.total_entities, int)
        assert isinstance(report.total_links, int)
        assert isinstance(report.orphans, list)
        assert isinstance(report.cycles, list)
        assert isinstance(report.broken_links, list)
        assert isinstance(report.duplicates, list)
