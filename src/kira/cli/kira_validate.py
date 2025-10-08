"""Graph validation CLI (ADR-016).

Provides commands for validating knowledge graph consistency:
- Orphan detection
- Cycle detection
- Broken link detection
- Duplicate entity detection
"""

import sys
from pathlib import Path

import click

from kira.core.config import load_config
from kira.core.graph_validation import GraphValidator, ValidationReport
from kira.core.links import LinkGraph

__all__ = ["validate_command"]


@click.group(name="validate")
def validate_command():
    """Validate knowledge graph consistency (ADR-016)."""
    pass


@validate_command.command(name="all")
@click.option(
    "--vault-root",
    "-v",
    type=click.Path(exists=True, path_type=Path),
    help="Path to vault root directory",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output report file (default: @Indexes/graph_report.md)",
)
@click.option(
    "--ignore-orphans",
    is_flag=True,
    help="Ignore orphan detection",
)
@click.option(
    "--fail-on-issues",
    is_flag=True,
    help="Exit with error code if issues found (for CI)",
)
@click.option(
    "--similarity-threshold",
    type=float,
    default=0.85,
    help="Duplicate similarity threshold (0.0-1.0, default: 0.85)",
)
def validate_all(
    vault_root: Path | None,
    output: Path | None,
    ignore_orphans: bool,
    fail_on_issues: bool,
    similarity_threshold: float,
):
    """Run all validation checks on knowledge graph.

    Examples:
        # Validate entire vault
        kira validate all

        # Validate and save report
        kira validate all -o graph_report.md

        # Validate for CI (fails if issues found)
        kira validate all --fail-on-issues
    """
    config = load_config()

    if not vault_root:
        vault_root = Path(config.get("vault_root", ".kira/vault"))

    if not vault_root.exists():
        click.echo(f"❌ Vault not found: {vault_root}", err=True)
        sys.exit(1)

    click.echo(f"🔍 Validating knowledge graph at {vault_root}...")

    # Create validator
    validator = GraphValidator(vault_root=vault_root)

    # Run validation
    report = validator.validate()

    # Display results
    display_report(report, ignore_orphans=ignore_orphans)

    # Save report
    if output:
        save_report(report, output, ignore_orphans=ignore_orphans)
        click.echo(f"\n📄 Report saved to {output}")
    else:
        # Default output location
        indexes_dir = vault_root / "@Indexes"
        indexes_dir.mkdir(exist_ok=True)
        default_output = indexes_dir / "graph_report.md"
        save_report(report, default_output, ignore_orphans=ignore_orphans)
        click.echo(f"\n📄 Report saved to {default_output}")

    # Exit with error if issues found (for CI)
    if fail_on_issues and report.has_issues():
        sys.exit(1)


@validate_command.command(name="orphans")
@click.option(
    "--vault-root",
    "-v",
    type=click.Path(exists=True, path_type=Path),
    help="Path to vault root directory",
)
def check_orphans(vault_root: Path | None):
    """Find orphaned entities with no links.

    Examples:
        kira validate orphans
    """
    config = load_config()

    if not vault_root:
        vault_root = Path(config.get("vault_root", ".kira/vault"))

    validator = GraphValidator(vault_root=vault_root)
    orphans = validator.find_orphans()

    if orphans:
        click.echo(f"⚠️  Found {len(orphans)} orphaned entities:\n")
        for entity_id in sorted(orphans):
            click.echo(f"  - {entity_id}")
    else:
        click.echo("✅ No orphaned entities found")


@validate_command.command(name="cycles")
@click.option(
    "--vault-root",
    "-v",
    type=click.Path(exists=True, path_type=Path),
    help="Path to vault root directory",
)
def check_cycles(vault_root: Path | None):
    """Find cycles in dependency graph.

    Examples:
        kira validate cycles
    """
    config = load_config()

    if not vault_root:
        vault_root = Path(config.get("vault_root", ".kira/vault"))

    validator = GraphValidator(vault_root=vault_root)
    cycles = validator.find_cycles()

    if cycles:
        click.echo(f"❌ Found {len(cycles)} cycle(s):\n", err=True)
        for i, cycle in enumerate(cycles, 1):
            cycle_str = " → ".join(cycle)
            click.echo(f"  {i}. {cycle_str}")
    else:
        click.echo("✅ No cycles found in dependency graph")


@validate_command.command(name="broken-links")
@click.option(
    "--vault-root",
    "-v",
    type=click.Path(exists=True, path_type=Path),
    help="Path to vault root directory",
)
def check_broken_links(vault_root: Path | None):
    """Find broken wikilinks and references.

    Examples:
        kira validate broken-links
    """
    config = load_config()

    if not vault_root:
        vault_root = Path(config.get("vault_root", ".kira/vault"))

    validator = GraphValidator(vault_root=vault_root)
    broken = validator.find_broken_links()

    if broken:
        click.echo(f"❌ Found {len(broken)} broken link(s):\n", err=True)
        for source_id, target_id in broken:
            click.echo(f"  {source_id} → {target_id} (missing)")
    else:
        click.echo("✅ No broken links found")


@validate_command.command(name="duplicates")
@click.option(
    "--vault-root",
    "-v",
    type=click.Path(exists=True, path_type=Path),
    help="Path to vault root directory",
)
@click.option(
    "--threshold",
    "-t",
    type=float,
    default=0.85,
    help="Similarity threshold (0.0-1.0, default: 0.85)",
)
def check_duplicates(vault_root: Path | None, threshold: float):
    """Find potential duplicate entities.

    Examples:
        kira validate duplicates
        kira validate duplicates --threshold 0.9
    """
    config = load_config()

    if not vault_root:
        vault_root = Path(config.get("vault_root", ".kira/vault"))

    validator = GraphValidator(vault_root=vault_root)
    duplicates = validator.find_duplicates(similarity_threshold=threshold)

    if duplicates:
        click.echo(f"⚠️  Found {len(duplicates)} potential duplicate(s):\n")
        for dup in duplicates:
            click.echo(f"  {dup.entity_id_1} ≈ {dup.entity_id_2} " f"(similarity: {dup.similarity:.2%})")
            click.echo(f"    Reason: {dup.reason}")
    else:
        click.echo("✅ No duplicates found")


def display_report(report: ValidationReport, ignore_orphans: bool = False):
    """Display validation report to console.

    Parameters
    ----------
    report
        Validation report
    ignore_orphans
        Skip orphan display
    """
    click.echo("\n" + "=" * 70)
    click.echo("📊 KNOWLEDGE GRAPH VALIDATION REPORT")
    click.echo("=" * 70)

    click.echo(f"\n📈 Statistics:")
    click.echo(f"  Total entities: {report.total_entities}")
    click.echo(f"  Total links: {report.total_links}")
    click.echo(f"  Total issues: {report.issue_count()}")

    # Cycles
    if report.cycles:
        click.echo(f"\n❌ Cycles: {len(report.cycles)}")
        for i, cycle in enumerate(report.cycles[:5], 1):
            cycle_str = " → ".join(cycle)
            click.echo(f"  {i}. {cycle_str}")
        if len(report.cycles) > 5:
            click.echo(f"  ... and {len(report.cycles) - 5} more")
    else:
        click.echo("\n✅ Cycles: 0")

    # Broken links
    if report.broken_links:
        click.echo(f"\n❌ Broken links: {len(report.broken_links)}")
        for source, target in report.broken_links[:10]:
            click.echo(f"  {source} → {target} (missing)")
        if len(report.broken_links) > 10:
            click.echo(f"  ... and {len(report.broken_links) - 10} more")
    else:
        click.echo("\n✅ Broken links: 0")

    # Duplicates
    if report.duplicates:
        click.echo(f"\n⚠️  Potential duplicates: {len(report.duplicates)}")
        for dup in report.duplicates[:5]:
            click.echo(f"  {dup.entity_id_1} ≈ {dup.entity_id_2} " f"({dup.similarity:.0%})")
        if len(report.duplicates) > 5:
            click.echo(f"  ... and {len(report.duplicates) - 5} more")
    else:
        click.echo("\n✅ Duplicates: 0")

    # Orphans
    if not ignore_orphans:
        if report.orphans:
            click.echo(f"\n⚠️  Orphaned entities: {len(report.orphans)}")
            for entity_id in report.orphans[:10]:
                click.echo(f"  {entity_id}")
            if len(report.orphans) > 10:
                click.echo(f"  ... and {len(report.orphans) - 10} more")
        else:
            click.echo("\n✅ Orphans: 0")

    click.echo("\n" + "=" * 70)

    # Summary
    if report.has_issues():
        click.echo(f"⚠️  Validation found {report.issue_count()} issue(s) " "that need attention")
    else:
        click.echo("✅ Knowledge graph is healthy!")


def save_report(
    report: ValidationReport,
    output_path: Path,
    ignore_orphans: bool = False,
):
    """Save validation report to Markdown file.

    Parameters
    ----------
    report
        Validation report
    output_path
        Output file path
    ignore_orphans
        Skip orphans in report
    """
    from datetime import datetime, timezone

    lines = []

    # Header
    lines.append("# Knowledge Graph Validation Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")

    # Statistics
    lines.append("## Statistics")
    lines.append("")
    lines.append(f"- **Total entities**: {report.total_entities}")
    lines.append(f"- **Total links**: {report.total_links}")
    lines.append(f"- **Total issues**: {report.issue_count()}")
    lines.append("")

    # Cycles
    lines.append("## Cycles in Dependency Graph")
    lines.append("")
    if report.cycles:
        lines.append(f"❌ **Found {len(report.cycles)} cycle(s)**")
        lines.append("")
        for i, cycle in enumerate(report.cycles, 1):
            cycle_str = " → ".join(cycle)
            lines.append(f"{i}. `{cycle_str}`")
        lines.append("")
        lines.append("**Action**: Break cycles by removing or reversing dependencies")
    else:
        lines.append("✅ No cycles detected")
    lines.append("")

    # Broken links
    lines.append("## Broken Links")
    lines.append("")
    if report.broken_links:
        lines.append(f"❌ **Found {len(report.broken_links)} broken link(s)**")
        lines.append("")
        for source, target in report.broken_links:
            lines.append(f"- `{source}` → `{target}` (missing)")
        lines.append("")
        lines.append("**Action**: Fix or remove broken references")
    else:
        lines.append("✅ No broken links detected")
    lines.append("")

    # Duplicates
    lines.append("## Potential Duplicates")
    lines.append("")
    if report.duplicates:
        lines.append(f"⚠️  **Found {len(report.duplicates)} potential duplicate(s)**")
        lines.append("")
        for dup in report.duplicates:
            lines.append(f"- `{dup.entity_id_1}` ≈ `{dup.entity_id_2}` " f"(similarity: {dup.similarity:.0%})")
            lines.append(f"  - {dup.reason}")
        lines.append("")
        lines.append("**Action**: Review and merge duplicates if appropriate")
    else:
        lines.append("✅ No duplicates detected")
    lines.append("")

    # Orphans
    if not ignore_orphans:
        lines.append("## Orphaned Entities")
        lines.append("")
        if report.orphans:
            lines.append(f"⚠️  **Found {len(report.orphans)} orphaned entity/entities**")
            lines.append("")
            for entity_id in report.orphans:
                lines.append(f"- `{entity_id}`")
            lines.append("")
            lines.append("**Action**: Add links to integrate orphans or archive if obsolete")
        else:
            lines.append("✅ No orphaned entities")
        lines.append("")

    # Write file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))


if __name__ == "__main__":
    validate_command()
