#!/usr/bin/env python3
"""CLI module for vault migration (Phase 4).

Provides commands for:
- Migrating vault files to new schema
- Dry-run validation
- Detailed reporting
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import click

from ..core.config import load_config
from ..migration.migrator import migrate_vault, validate_migration

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(
    context_settings=CONTEXT_SETTINGS,
    help="Vault migration commands (Phase 4)",
)
def cli() -> None:
    """Root command for migration."""


@cli.command("run")
@click.option(
    "--vault-path",
    type=str,
    help="Path to vault directory (default: from config)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview changes without writing (Phase 4 DoD: validation report)",
)
@click.option(
    "--no-validate",
    is_flag=True,
    help="Skip validation after migration",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results as JSON (Phase 2: machine-readable output)",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Show detailed output",
)
def run_command(
    vault_path: str | None,
    dry_run: bool,
    no_validate: bool,
    output_json: bool,
    verbose: bool,
) -> int:
    """Migrate vault files to new schema (Phase 4, Point 15).

    DoD: After migration, every file parses and passes round-trip tests.

    Exit codes (Phase 2):
    - 0: Success
    - 1: General error
    - 2: Validation error
    - 5: I/O error
    """
    try:
        # Get vault path
        if vault_path:
            vault_path_obj = Path(vault_path)
        else:
            config = load_config()
            vault_path_str = config.get("vault", {}).get("path")
            if not vault_path_str:
                error_msg = "Vault path not specified in config"
                if output_json:
                    click.echo(json.dumps({"status": "error", "error": error_msg, "exit_code": 6}))
                else:
                    click.echo(f"❌ {error_msg}")
                return 6  # Config error

            vault_path_obj = Path(vault_path_str)

        # Validate vault path exists
        if not vault_path_obj.exists():
            error_msg = f"Vault path does not exist: {vault_path_obj}"
            if output_json:
                click.echo(json.dumps({"status": "error", "error": error_msg, "exit_code": 5}))
            else:
                click.echo(f"❌ {error_msg}")
            return 5  # I/O error

        if not vault_path_obj.is_dir():
            error_msg = f"Vault path is not a directory: {vault_path_obj}"
            if output_json:
                click.echo(json.dumps({"status": "error", "error": error_msg, "exit_code": 5}))
            else:
                click.echo(f"❌ {error_msg}")
            return 5  # I/O error

        # Show migration header (unless JSON output)
        if not output_json:
            click.echo(f"🔄 Migrating vault: {vault_path_obj}")
            if dry_run:
                click.echo("📋 DRY RUN - no changes will be written (Phase 4, Point 16)")
            click.echo()

        # Run migration
        stats, results = migrate_vault(vault_path_obj, dry_run=dry_run)

        # Prepare output data
        output_data = {
            "vault_path": str(vault_path_obj),
            "dry_run": dry_run,
            "stats": {
                "total_files": stats.total_files,
                "successful": stats.successful,
                "skipped": stats.skipped,
                "failed": stats.failed,
            },
            "results": [],
        }

        # Add detailed results
        for result in results:
            result_data = {
                "file_path": str(result.file_path),
                "success": result.success,
                "changes": result.changes,
                "errors": result.errors,
            }
            output_data["results"].append(result_data)

        # Output results
        if output_json:
            # JSON output (Phase 2: machine-readable)
            output_data["status"] = "success" if stats.failed == 0 else "error"
            output_data["exit_code"] = 0 if stats.failed == 0 else 2
            click.echo(json.dumps(output_data, indent=2))
        else:
            # Human-readable output
            click.echo(f"📊 Migration Summary:")
            click.echo(f"   Total files: {stats.total_files}")
            click.echo(f"   ✅ Successful: {stats.successful}")
            click.echo(f"   ⏭️  Skipped (no changes): {stats.skipped}")
            click.echo(f"   ❌ Failed: {stats.failed}")
            click.echo()

            # Show detailed results if verbose
            if verbose:
                click.echo("📝 Detailed Results:\n")
                for result in results:
                    if result.changes or result.errors:
                        click.echo(f"📄 {result.file_path}")
                        if result.changes:
                            for change in result.changes:
                                click.echo(f"   ✓ {change}")
                        if result.errors:
                            for error in result.errors:
                                click.echo(f"   ✗ {error}")
                        click.echo()

        # Validate migrated files (Phase 4, Point 16: validation report)
        if not no_validate and not dry_run and stats.successful > 0:
            if not output_json:
                click.echo("🔍 Validating migrated files (DoD: round-trip tests)...")

            validation_errors = []

            for result in results:
                if result.success and result.changes:
                    is_valid, errors = validate_migration(result.file_path)
                    if not is_valid:
                        validation_errors.append(
                            {
                                "file_path": str(result.file_path),
                                "errors": errors,
                            }
                        )

            if validation_errors:
                if output_json:
                    output_data["validation_errors"] = validation_errors
                    output_data["status"] = "error"
                    output_data["exit_code"] = 2
                    click.echo(json.dumps(output_data, indent=2))
                else:
                    click.echo(f"\n❌ Validation failed for {len(validation_errors)} files:")
                    for val_error in validation_errors:
                        click.echo(f"  📄 {val_error['file_path']}:")
                        for error in val_error["errors"]:
                            click.echo(f"      - {error}")
                return 2  # Validation error
            elif not output_json:
                click.echo("✅ All migrated files validated successfully (DoD: round-trip passed)")

        # Dry-run validation report (Phase 4, Point 16)
        if dry_run and not output_json:
            critical_count = sum(1 for r in results if r.errors)
            click.echo("\n📋 Dry-Run Validation Report (Phase 4, Point 16):")
            click.echo(f"   Critical errors: {critical_count}")
            if critical_count == 0:
                click.echo("   ✅ DoD: 0 critical errors - ready for live run")
            else:
                click.echo("   ❌ Fix critical errors before live migration")

        # Return exit code
        if stats.failed > 0:
            return 2  # Validation error
        return 0

    except Exception as exc:
        error_msg = f"Migration failed: {exc}"
        if output_json:
            click.echo(
                json.dumps(
                    {
                        "status": "error",
                        "error": error_msg,
                        "exit_code": 1,
                    }
                )
            )
        else:
            click.echo(f"❌ {error_msg}")
            if verbose:
                import traceback

                traceback.print_exc()
        return 1


@cli.command("validate")
@click.option(
    "--vault-path",
    type=str,
    help="Path to vault directory (default: from config)",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output results as JSON",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Show detailed output",
)
def validate_command(
    vault_path: str | None,
    output_json: bool,
    verbose: bool,
) -> int:
    """Validate vault files without migration (Phase 4, Point 16).

    DoD: Report shows 0 critical errors before live run.
    """
    try:
        # Get vault path
        if vault_path:
            vault_path_obj = Path(vault_path)
        else:
            config = load_config()
            vault_path_str = config.get("vault", {}).get("path")
            if not vault_path_str:
                error_msg = "Vault path not specified in config"
                if output_json:
                    click.echo(json.dumps({"status": "error", "error": error_msg}))
                else:
                    click.echo(f"❌ {error_msg}")
                return 6

            vault_path_obj = Path(vault_path_str)

        if not vault_path_obj.exists():
            error_msg = f"Vault path does not exist: {vault_path_obj}"
            if output_json:
                click.echo(json.dumps({"status": "error", "error": error_msg}))
            else:
                click.echo(f"❌ {error_msg}")
            return 5

        # Find all .md files
        md_files = list(vault_path_obj.rglob("*.md"))

        if not output_json:
            click.echo(f"🔍 Validating {len(md_files)} files in: {vault_path_obj}\n")

        # Validate each file
        validation_results = []
        critical_errors = 0

        for md_file in md_files:
            is_valid, errors = validate_migration(md_file)
            if not is_valid:
                critical_errors += 1
                validation_results.append(
                    {
                        "file_path": str(md_file),
                        "errors": errors,
                    }
                )

        # Output results
        if output_json:
            output_data = {
                "status": "success" if critical_errors == 0 else "error",
                "vault_path": str(vault_path_obj),
                "total_files": len(md_files),
                "critical_errors": critical_errors,
                "validation_results": validation_results,
            }
            click.echo(json.dumps(output_data, indent=2))
        else:
            click.echo("📊 Validation Report (Phase 4, Point 16):")
            click.echo(f"   Total files: {len(md_files)}")
            click.echo(f"   Critical errors: {critical_errors}")

            if critical_errors == 0:
                click.echo("\n✅ DoD: 0 critical errors - vault is ready")
            else:
                click.echo(f"\n❌ Found {critical_errors} files with errors:")
                for val_result in validation_results:
                    click.echo(f"\n📄 {val_result['file_path']}:")
                    for error in val_result["errors"]:
                        click.echo(f"   - {error}")

        return 0 if critical_errors == 0 else 2

    except Exception as exc:
        error_msg = f"Validation failed: {exc}"
        if output_json:
            click.echo(json.dumps({"status": "error", "error": error_msg}))
        else:
            click.echo(f"❌ {error_msg}")
            if verbose:
                import traceback

                traceback.print_exc()
        return 1


def main(args: list[str] | None = None) -> int:
    """Main entry point for migration CLI."""
    if args is None:
        args = sys.argv[1:]

    try:
        return cli.main(args=list(args), standalone_mode=False)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 0


if __name__ == "__main__":
    sys.exit(main())

