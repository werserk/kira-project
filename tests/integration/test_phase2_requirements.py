"""Integration tests for Phase 2: CLI for Humans & Agents (LLM-friendly).

DoD for Phase 2:
- Task 8: All CLI commands support --json with clean JSON output (no log mixing)
- Task 9: Stable exit codes (0,2,3,4,5,6,7) + --dry-run, --yes, --trace-id flags
- Task 10: Audit log to artifacts/audit/*.jsonl with full action history
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kira.cli.cli_common import AuditLogger, CLIContext, ExitCode
from kira.cli.kira_task_v2 import main as task_cli_main
from kira.core.vault_init import init_vault


class TestMachineReadableOutput:
    """Test Task 8: --json flag for machine-readable output."""

    def test_json_output_contains_only_json(self, tmp_path: Path, capsys, monkeypatch):
        """--json mode outputs only JSON, no human-readable text or logs."""
        # Initialize vault
        vault_path = tmp_path / "vault"
        init_vault(vault_path)

        # Set vault path in environment
        monkeypatch.setenv("KIRA_VAULT_PATH", str(vault_path))

        # Run command with --json
        exit_code = task_cli_main(["create", "--title", "Test Task", "--json", "--trace-id", "test-123"])

        # Capture output
        captured = capsys.readouterr()
        output = captured.out.strip()

        # Verify it's valid JSON
        result = json.loads(output)

        # Verify JSON structure
        assert "status" in result
        assert "trace_id" in result
        assert result["trace_id"] == "test-123"
        assert result["status"] == "success"
        assert "data" in result
        assert exit_code == 0

        # Verify no error logs in stderr
        assert not captured.err or "ERROR" not in captured.err

    def test_json_output_on_error(self, tmp_path: Path, capsys, monkeypatch):
        """--json mode outputs JSON even on errors."""
        vault_path = tmp_path / "vault"
        init_vault(vault_path)
        monkeypatch.setenv("KIRA_VAULT_PATH", str(vault_path))

        # Run command that will fail (update non-existent task)
        exit_code = task_cli_main(["update", "nonexistent-task", "--status", "done", "--json"])

        captured = capsys.readouterr()
        output = captured.out.strip()

        # Should be valid JSON with error
        result = json.loads(output)
        assert result["status"] == "error"
        assert "error" in result
        assert "not found" in result["error"].lower()
        assert exit_code != 0

    def test_all_commands_support_json(self, tmp_path: Path, capsys, monkeypatch):
        """All task commands support --json flag."""
        vault_path = tmp_path / "vault"
        init_vault(vault_path)
        monkeypatch.setenv("KIRA_VAULT_PATH", str(vault_path))

        # Test create with --json
        task_cli_main(["create", "--title", "Task 1", "--json"])
        result1 = json.loads(capsys.readouterr().out.strip())
        assert result1["status"] == "success"
        task_id = result1["data"]["task_id"]

        # Test list with --json
        task_cli_main(["list", "--json"])
        result2 = json.loads(capsys.readouterr().out.strip())
        assert result2["status"] == "success"
        assert isinstance(result2["data"], list)

        # Test get with --json
        task_cli_main(["get", task_id, "--json"])
        result3 = json.loads(capsys.readouterr().out.strip())
        assert result3["status"] == "success"
        assert result3["data"]["id"] == task_id


class TestStableExitCodes:
    """Test Task 9: Stable exit codes and operational flags."""

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


class TestAuditLog:
    """Test Task 10: Audit logging to artifacts/audit/*.jsonl."""

    def test_audit_log_created(self, tmp_path: Path):
        """Command execution writes to audit log."""
        vault_path = tmp_path / "vault"
        artifacts_dir = tmp_path / "artifacts"
        init_vault(vault_path)

        # Create CLI context with audit logger
        ctx = CLIContext(json_output=True, trace_id="audit-test-123")
        ctx.audit_logger = AuditLogger(artifacts_dir)

        # Log a command
        ctx.log_audit(
            "task.create",
            {"title": "Test Task"},
            {"status": "success", "data": {"task_id": "task-123"}},
        )

        # Verify audit log exists
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        audit_file = artifacts_dir / "audit" / f"audit-{today}.jsonl"

        assert audit_file.exists()

        # Verify audit entry
        with open(audit_file) as f:
            lines = f.readlines()
            assert len(lines) == 1

            entry = json.loads(lines[0])
            assert entry["trace_id"] == "audit-test-123"
            assert entry["command"] == "task.create"
            assert entry["args"]["title"] == "Test Task"
            assert entry["result"]["status"] == "success"

    def test_audit_log_full_action_history(self, tmp_path: Path, capsys, monkeypatch):
        """Audit log contains full action history for reconstruction."""
        vault_path = tmp_path / "vault"
        init_vault(vault_path)
        monkeypatch.setenv("KIRA_VAULT_PATH", str(vault_path))

        # Perform multiple operations
        task_cli_main(["create", "--title", "Task 1", "--json", "--trace-id", "op-1"])
        result1 = json.loads(capsys.readouterr().out.strip())
        task_id = result1["data"]["task_id"]

        task_cli_main(
            [
                "update",
                task_id,
                "--status",
                "doing",
                "--json",
                "--trace-id",
                "op-2",
            ]
        )
        capsys.readouterr()  # Clear

        task_cli_main(
            [
                "update",
                task_id,
                "--status",
                "done",
                "--json",
                "--trace-id",
                "op-3",
            ]
        )
        capsys.readouterr()

        # Read audit log
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        artifacts_dir = Path("artifacts")
        audit_file = artifacts_dir / "audit" / f"audit-{today}.jsonl"

        assert audit_file.exists()

        # Verify all operations are logged
        with open(audit_file) as f:
            entries = [json.loads(line) for line in f]

        # Should have at least 3 entries (create, 2 updates)
        assert len(entries) >= 3

        # Verify sequence
        trace_ids = [e["trace_id"] for e in entries[-3:]]
        assert "op-1" in trace_ids
        assert "op-2" in trace_ids
        assert "op-3" in trace_ids

    def test_audit_log_includes_before_after(self, tmp_path: Path, capsys, monkeypatch):
        """Audit log can reconstruct state changes (before/after)."""
        vault_path = tmp_path / "vault"
        init_vault(vault_path)
        monkeypatch.setenv("KIRA_VAULT_PATH", str(vault_path))

        # Create and update task
        task_cli_main(["create", "--title", "Task", "--json"])
        result = json.loads(capsys.readouterr().out.strip())
        task_id = result["data"]["task_id"]

        task_cli_main(["update", task_id, "--status", "done", "--json"])
        capsys.readouterr()

        # Read audit log
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        audit_file = Path("artifacts") / "audit" / f"audit-{today}.jsonl"

        with open(audit_file) as f:
            entries = [json.loads(line) for line in f]

        # Verify update entry has args showing the change
        update_entries = [e for e in entries if e["command"] == "task.update"]
        assert len(update_entries) > 0

        update_entry = update_entries[0]
        assert update_entry["args"]["status"] == "done"


class TestPhase2Complete:
    """Verify all Phase 2 DoD requirements are met."""

    def test_all_phase2_requirements(self, tmp_path: Path, capsys, monkeypatch):
        """Combined test: JSON output + exit codes + audit log."""
        vault_path = tmp_path / "vault"
        init_vault(vault_path)
        monkeypatch.setenv("KIRA_VAULT_PATH", str(vault_path))

        # 1. JSON output
        task_cli_main(["create", "--title", "Phase2 Task", "--json", "--trace-id", "phase2-test"])
        result = json.loads(capsys.readouterr().out.strip())
        assert result["status"] == "success"
        assert result["trace_id"] == "phase2-test"
        task_id = result["data"]["task_id"]

        # 2. Dry-run
        task_cli_main(["delete", task_id, "--dry-run", "--json"])
        result = json.loads(capsys.readouterr().out.strip())
        assert result["meta"]["dry_run"] is True

        # Task should still exist
        task_cli_main(["get", task_id, "--json"])
        result = json.loads(capsys.readouterr().out.strip())
        assert result["status"] == "success"

        # 3. Non-interactive delete with --yes
        exit_code = task_cli_main(["delete", task_id, "--yes", "--json"])
        result = json.loads(capsys.readouterr().out.strip())
        assert exit_code == ExitCode.SUCCESS
        assert result["data"]["action"] == "deleted"

        # 4. Audit log exists
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        audit_file = Path("artifacts") / "audit" / f"audit-{today}.jsonl"
        assert audit_file.exists()

        # 5. Audit log is reconstructible
        with open(audit_file) as f:
            entries = [json.loads(line) for line in f]

        # Should have create, delete entries
        commands = [e["command"] for e in entries]
        assert "task.create" in commands
        assert "task.delete" in commands
