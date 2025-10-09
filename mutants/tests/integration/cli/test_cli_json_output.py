"""Integration tests for CLI JSON output (machine-readable mode).

Tests verify that:
- All CLI commands support --json flag
- JSON output is clean (no log mixing)
- Output is valid JSON even on errors
"""

import json
from pathlib import Path

import pytest

from kira.cli.kira_task_v2 import main as task_cli_main
from kira.core.vault_init import init_vault


class TestJSONOutput:
    """Test --json flag for machine-readable output."""

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


pytestmark = pytest.mark.integration

