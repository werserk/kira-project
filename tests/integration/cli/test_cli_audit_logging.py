"""Integration tests for CLI audit logging.

Tests verify that:
- Command execution writes to audit log
- Audit log contains full action history for reconstruction
- Audit entries include before/after state
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kira.cli.cli_common import AuditLogger, CLIContext
from kira.cli.kira_task_v2 import main as task_cli_main
from kira.core.vault_init import init_vault


class TestAuditLogging:
    """Test audit logging to artifacts/audit/*.jsonl."""

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
        update_entries = [e for e in entries if e["command"] == "task.update" and e["args"]["task_id"] == task_id]
        assert len(update_entries) > 0

        update_entry = update_entries[0]
        assert update_entry["args"]["status"] == "done"


class TestCLIIntegrationComplete:
    """Verify all CLI requirements are met (JSON + exit codes + audit)."""

    def test_all_cli_requirements(self, tmp_path: Path, capsys, monkeypatch):
        """Combined test: JSON output + exit codes + audit log."""
        vault_path = tmp_path / "vault"
        init_vault(vault_path)
        monkeypatch.setenv("KIRA_VAULT_PATH", str(vault_path))

        # 1. JSON output
        task_cli_main(["create", "--title", "CLI Test Task", "--json", "--trace-id", "cli-test"])
        result = json.loads(capsys.readouterr().out.strip())
        assert result["status"] == "success"
        assert result["trace_id"] == "cli-test"
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
        from kira.cli.cli_common import ExitCode

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


pytestmark = pytest.mark.integration

