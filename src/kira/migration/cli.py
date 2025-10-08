"""CLI command for vault migration (Phase 8, Point 23)."""

from __future__ import annotations

import sys
from pathlib import Path

from .migrator import migrate_vault, validate_migration

__all__ = ["run_migration"]


def run_migration(
    vault_path: Path | str,
    dry_run: bool = False,
    validate: bool = True,
    verbose: bool = False,
) -> int:
    """Run vault migration CLI command.

    Parameters
    ----------
    vault_path
        Path to vault directory
    dry_run
        If True, don't write changes
    validate
        If True, validate migrated files
    verbose
        If True, show detailed output

    Returns
    -------
    int
        Exit code (0 = success, 1 = failure)
    """
    vault_path = Path(vault_path)

    if not vault_path.exists():
        print(f"Error: Vault path does not exist: {vault_path}", file=sys.stderr)
        return 1

    if not vault_path.is_dir():
        print(f"Error: Vault path is not a directory: {vault_path}", file=sys.stderr)
        return 1

    # Run migration
    print(f"Migrating vault: {vault_path}")
    if dry_run:
        print("DRY RUN - no changes will be written")
    print()

    stats, results = migrate_vault(vault_path, dry_run=dry_run)

    # Print results
    print(f"Total files: {stats.total_files}")
    print(f"Successful: {stats.successful}")
    print(f"Skipped (no changes): {stats.skipped}")
    print(f"Failed: {stats.failed}")
    print()

    # Show detailed results if verbose
    if verbose:
        for result in results:
            if result.changes or result.errors:
                print(f"File: {result.file_path}")
                if result.changes:
                    for change in result.changes:
                        print(f"  ✓ {change}")
                if result.errors:
                    for error in result.errors:
                        print(f"  ✗ {error}")
                print()

    # Validate migrated files
    if validate and not dry_run and stats.successful > 0:
        print("Validating migrated files...")
        validation_errors = []

        for result in results:
            if result.success and result.changes:
                is_valid, errors = validate_migration(result.file_path)
                if not is_valid:
                    validation_errors.append((result.file_path, errors))

        if validation_errors:
            print(f"\n✗ Validation failed for {len(validation_errors)} files:")
            for file_path, errors in validation_errors:
                print(f"  {file_path}:")
                for error in errors:
                    print(f"    - {error}")
            return 1
        else:
            print("✓ All migrated files validated successfully")

    # Return exit code
    if stats.failed > 0:
        return 1

    return 0


def main():
    """Main entry point for migration CLI."""
    import argparse

    parser = argparse.ArgumentParser(description="Migrate vault files to new schema (Phase 8, Point 23)")
    parser.add_argument(
        "vault_path",
        type=Path,
        help="Path to vault directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't write changes, just show what would be done",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip validation after migration",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed output",
    )

    args = parser.parse_args()

    exit_code = run_migration(
        vault_path=args.vault_path,
        dry_run=args.dry_run,
        validate=not args.no_validate,
        verbose=args.verbose,
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
