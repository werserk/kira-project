#!/usr/bin/env python3
"""Nightly validation job for knowledge graph (ADR-016).

Runs comprehensive validation checks and generates reports with auto-fix suggestions.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from kira.core.graph_validation import GraphValidator, ValidationReport
from kira.core.links import LinkGraph


def generate_report_markdown(report: ValidationReport, vault_path: Path) -> str:
    """Generate Markdown report from validation results.
    
    Parameters
    ----------
    report
        Validation report
    vault_path
        Path to vault
    
    Returns
    -------
    str
        Markdown formatted report
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    
    markdown = f"""# Knowledge Graph Validation Report

**Generated:** {timestamp}  
**Vault:** {vault_path}  
**Status:** {'✅ All checks passed' if not report.has_issues() else f'⚠️  {report.issue_count()} issues found'}

## Summary

- **Total Entities:** {report.total_entities}
- **Total Links:** {report.total_links}
- **Orphaned Entities:** {len(report.orphans)}
- **Dependency Cycles:** {len(report.cycles)}
- **Broken Links:** {len(report.broken_links)}
- **Potential Duplicates:** {len(report.duplicates)}

---

"""
    
    # Orphaned Entities
    if report.orphans:
        markdown += "## 🔗 Orphaned Entities\n\n"
        markdown += "Entities with no incoming or outgoing links:\n\n"
        
        for entity_id in sorted(report.orphans)[:20]:  # Limit to 20
            markdown += f"- `{entity_id}`\n"
        
        if len(report.orphans) > 20:
            markdown += f"\n_... and {len(report.orphans) - 20} more_\n"
        
        markdown += "\n**Suggested Fixes:**\n\n"
        markdown += "- Add related tasks/projects to link orphans\n"
        markdown += "- Add tags to group similar entities\n"
        markdown += "- Consider if orphans should be archived\n\n"
        markdown += "---\n\n"
    
    # Dependency Cycles
    if report.cycles:
        markdown += "## 🔄 Dependency Cycles\n\n"
        markdown += "Circular dependencies detected (tasks cannot depend on themselves):\n\n"
        
        for i, cycle in enumerate(report.cycles[:10], 1):  # Limit to 10
            markdown += f"### Cycle {i}\n\n"
            markdown += "```\n"
            markdown += " → ".join(cycle)
            markdown += "\n```\n\n"
        
        if len(report.cycles) > 10:
            markdown += f"_... and {len(report.cycles) - 10} more cycles_\n\n"
        
        markdown += "**Suggested Fixes:**\n\n"
        markdown += "- Review and remove one dependency from each cycle\n"
        markdown += "- Restructure task breakdown to avoid circular dependencies\n"
        markdown += "- Use tags or projects instead of `depends_on` for related tasks\n\n"
        markdown += "**Auto-fix Available:** Run `kira vault fix-cycles --preview`\n\n"
        markdown += "---\n\n"
    
    # Broken Links
    if report.broken_links:
        markdown += "## 🔗 Broken Links\n\n"
        markdown += "Links pointing to non-existent entities:\n\n"
        
        for source, target in sorted(report.broken_links)[:30]:  # Limit to 30
            markdown += f"- `{source}` → `{target}` (missing)\n"
        
        if len(report.broken_links) > 30:
            markdown += f"\n_... and {len(report.broken_links) - 30} more_\n"
        
        markdown += "\n**Suggested Fixes:**\n\n"
        markdown += "- Create missing entities\n"
        markdown += "- Fix typos in entity IDs\n"
        markdown += "- Remove broken links from frontmatter\n"
        markdown += "- Use alias tracking if entities were renamed\n\n"
        markdown += "**Auto-fix Available:** Run `kira vault fix-links --interactive`\n\n"
        markdown += "---\n\n"
    
    # Duplicates
    if report.duplicates:
        markdown += "## 📋 Potential Duplicates\n\n"
        markdown += "Entities with similar titles and types:\n\n"
        
        for dup in sorted(report.duplicates, key=lambda d: d.similarity, reverse=True)[:20]:
            markdown += f"### Similarity: {dup.similarity:.1%}\n\n"
            markdown += f"- `{dup.entity_id_1}`\n"
            markdown += f"- `{dup.entity_id_2}`\n"
            markdown += f"- **Reason:** {dup.reason}\n\n"
        
        if len(report.duplicates) > 20:
            markdown += f"_... and {len(report.duplicates) - 20} more potential duplicates_\n\n"
        
        markdown += "**Suggested Fixes:**\n\n"
        markdown += "- Review and merge genuine duplicates\n"
        markdown += "- Add distinguishing details to similar entities\n"
        markdown += "- Archive completed/obsolete entities\n\n"
        markdown += "**Auto-fix Available:** Run `kira vault merge-duplicates --interactive`\n\n"
        markdown += "---\n\n"
    
    if not report.has_issues():
        markdown += "## ✅ No Issues Found\n\n"
        markdown += "All validation checks passed! Your knowledge graph is healthy.\n\n"
    
    markdown += "## Next Steps\n\n"
    markdown += "1. Review issues above\n"
    markdown += "2. Run suggested auto-fix commands (with `--preview` first)\n"
    markdown += "3. Re-run validation: `kira vault validate`\n\n"
    
    markdown += "---\n\n"
    markdown += "_This report is generated nightly. See `scripts/nightly_validation.py` for details._\n"
    
    return markdown


def main() -> None:
    """Main entry point for nightly validation."""
    print("🔍 Starting nightly validation...")
    print()
    
    # Load config to get vault path
    config_path = PROJECT_ROOT / "kira.yaml"
    vault_path = PROJECT_ROOT / "examples" / "minimal-vault"  # Default
    
    if config_path.exists():
        import yaml
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
            vault_path = Path(config.get("vault", {}).get("path", vault_path))
        except Exception as e:
            print(f"⚠️  Warning: Could not load config: {e}")
            print(f"Using default vault path: {vault_path}")
    
    print(f"📁 Vault path: {vault_path}")
    print()
    
    # Run validation
    print("Running validation checks...")
    print()
    
    try:
        validator = GraphValidator(
            vault_root=vault_path,
            ignore_folders=["@Indexes", "@Templates", "@Archive"],
            ignore_kinds=["tag", "index", "template"],
        )
        
        report = validator.validate()
        
        print("✅ Validation complete")
        print()
        
        # Print summary
        print("Summary:")
        print(f"  - Total entities: {report.total_entities}")
        print(f"  - Total links: {report.total_links}")
        print(f"  - Orphans: {len(report.orphans)}")
        print(f"  - Cycles: {len(report.cycles)}")
        print(f"  - Broken links: {len(report.broken_links)}")
        print(f"  - Duplicates: {len(report.duplicates)}")
        print()
        
        # Generate Markdown report
        report_markdown = generate_report_markdown(report, vault_path)
        
        # Save report
        indexes_dir = vault_path / "@Indexes"
        indexes_dir.mkdir(exist_ok=True)
        
        report_path = indexes_dir / "graph_report.md"
        report_path.write_text(report_markdown, encoding="utf-8")
        
        print(f"✅ Report saved: {report_path}")
        print()
        
        # Also save JSON for programmatic access
        json_report_path = indexes_dir / "graph_report.json"
        json_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_entities": report.total_entities,
            "total_links": report.total_links,
            "orphans": report.orphans,
            "cycles": [[str(node) for node in cycle] for cycle in report.cycles],
            "broken_links": [[src, tgt] for src, tgt in report.broken_links],
            "duplicates": [
                {
                    "entity_1": dup.entity_id_1,
                    "entity_2": dup.entity_id_2,
                    "similarity": dup.similarity,
                    "reason": dup.reason,
                }
                for dup in report.duplicates
            ],
        }
        
        with open(json_report_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ JSON report saved: {json_report_path}")
        print()
        
        # Exit with appropriate code
        if report.has_issues():
            print(f"⚠️  Found {report.issue_count()} issues")
            print("Review the report and run suggested fixes.")
            sys.exit(1)
        else:
            print("✅ No issues found! Graph is healthy.")
            sys.exit(0)
            
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

