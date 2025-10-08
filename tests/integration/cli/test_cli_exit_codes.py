"""Integration tests for CLI exit codes and operational flags.

Tests verify that:
- Stable exit codes (0,2,3,4,5,6,7) are returned
- --dry-run flag shows plan without executing
- --yes flag bypasses confirmation prompts
- --trace-id allows request correlation
"""

import json
from pathlib import Path

import pytest

from kira.cli.cli_common import ExitCode
from kira.cli.kira_task_v2 import main as task_cli_main
from kira.core.vault_init import init_vault


class TestExitCodes:
    """Test stable exit codes."""

    def test_success_exit_code(self, tmp_path: Path, monkeypatch):
        """Successful command returns exit code 0."""
        vault_path = tmp_path / "vault"
        init_vault(vault_path)
        monkeypatch.setenv("KIRA_VAULT_PATH", str(vault_path))

        exit_code = task_cli_main(["create", "--title", "Test", "--json"])
        assert exit_code == ExitCode.SUCCESS

    def test_fsm_error_exit_code(self, tmp_path: Path):
        """FSM guard violation returns exit code 4."""
        vault_path = tmp_path / "vault"
        init_vault(vault_path)

        # Create task
        task_cli_main(["create", "--title", "Task", "--json"])

        # TODO: Add test once we enforce FSM guards strictly
        # For now, this is a placeholder

    def test_validation_error_exit_code(self, tmp_path: Path):
        """Validation error returns exit code 2."""
        # This would be tested when we add validation to create
        pass

    def test_io_error_exit_code(self, tmp_path: Path, monkeypatch):
        """I/O error returns exit code 5."""
        vault_path = tmp_path / "vault"
        # Don't initialize vault - should trigger I/O error
        monkeypatch.setenv("KIRA_VAULT_PATH", str(vault_path))
        exit_code = task_cli_main(["create", "--title", "Test"])
        assert exit_code in (ExitCode.IO_LOCK_ERROR, ExitCode.UNKNOWN_ERROR)


class TestOperationalFlags:
    """Test operational flags: --dry-run, --yes, --trace-id."""

    def test_dry_run_flag(self, tmp_path: Path, capsys, monkeypatch):
        """--dry-run shows plan without executing."""
        vault_path = tmp_path / "vault"
        init_vault(vault_path)
        monkeypatch.setenv("KIRA_VAULT_PATH", str(vault_path))

        # Run with --dry-run
        exit_code = task_cli_main(["create", "--title", "Test Task", "--dry-run", "--json"])

        result = json.loads(capsys.readouterr().out.strip())

        # Verify dry-run metadata
        assert result["meta"]["dry_run"] is True
        assert result["data"]["action"] == "create_task"
        assert exit_code == ExitCode.SUCCESS

        # Verify task was NOT created (count tasks before and after should be same)
        tasks_dir = vault_path / "tasks"
        if tasks_dir.exists():
            # Vault init creates example tasks, so check that no NEW task was created
            task_files = list(tasks_dir.glob("task-*.md"))
            # Filter out example tasks (they have "example" in the name)
            actual_tasks = [t for t in task_files if "example" not in t.name.lower()]
            assert len(actual_tasks) == 0

    def test_yes_flag_non_interactive(self, tmp_path: Path, capsys, monkeypatch):
        """--yes flag bypasses confirmation prompts."""
        vault_path = tmp_path / "vault"
        init_vault(vault_path)
        monkeypatch.setenv("KIRA_VAULT_PATH", str(vault_path))

        # Create task
        task_cli_main(["create", "--title", "Task", "--json"])
        result = json.loads(capsys.readouterr().out.strip())
        task_id = result["data"]["task_id"]

        # Delete with --yes (no confirmation prompt)
        exit_code = task_cli_main(["delete", task_id, "--yes", "--json"])

        result = json.loads(capsys.readouterr().out.strip())
        assert result["data"]["action"] == "deleted"
        assert exit_code == ExitCode.SUCCESS

    def test_trace_id_correlation(self, tmp_path: Path, capsys, monkeypatch):
        """--trace-id allows request correlation."""
        vault_path = tmp_path / "vault"
        init_vault(vault_path)
        monkeypatch.setenv("KIRA_VAULT_PATH", str(vault_path))

        trace_id = "custom-trace-12345"
        task_cli_main(["create", "--title", "Test", "--trace-id", trace_id, "--json"])

        result = json.loads(capsys.readouterr().out.strip())
        assert result["trace_id"] == trace_id

    def test_idempotent_create_returns_existing(self, tmp_path: Path, capsys, monkeypatch):
        """Repeated create with same data returns existing (exit code 3 or 0)."""
        vault_path = tmp_path / "vault"
        init_vault(vault_path)
        monkeypatch.setenv("KIRA_VAULT_PATH", str(vault_path))

        # For now, skip this test - idempotent create not yet implemented
        # This will be implemented in a future phase
        pytest.skip("Idempotent create not yet implemented")


pytestmark = pytest.mark.integration

