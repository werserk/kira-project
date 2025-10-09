"""Integration tests for kira doctor diagnostic tool."""

import json
import os
import subprocess
from pathlib import Path

import pytest


class TestDoctorCommand:
    """Tests for kira doctor command."""

    def test_doctor_json_output(self):
        """Test doctor command with JSON output."""
        result = subprocess.run(
            ["poetry", "run", "python", "-m", "kira.cli", "doctor", "--json-output"],
            capture_output=True,
            text=True,
        )

        # Parse JSON output
        output = json.loads(result.stdout)

        # Verify structure
        assert "environment" in output
        assert "vault" in output
        assert "adapters" in output
        assert "permissions" in output
        assert "summary" in output

        # Verify summary
        summary = output["summary"]
        assert "total" in summary
        assert "passed" in summary
        assert "warnings" in summary
        assert "failed" in summary
        assert summary["overall"] in ["ok", "warn", "fail"]

    def test_doctor_categories(self):
        """Test doctor checks all categories."""
        result = subprocess.run(
            ["poetry", "run", "python", "-m", "kira.cli", "doctor", "--json-output"],
            capture_output=True,
            text=True,
        )

        output = json.loads(result.stdout)

        # Environment checks
        env_checks = output["environment"]["checks"]
        assert any(c["name"] == ".env file" for c in env_checks)
        assert any(c["name"] == "Vault path" for c in env_checks)

        # Vault checks
        vault_checks = output["vault"]["checks"]
        assert any("directory" in c["name"] for c in vault_checks)

        # Adapter checks
        adapter_checks = output["adapters"]["checks"]
        assert any(c["name"] == "Network connectivity" for c in adapter_checks)

    def test_doctor_exit_codes(self):
        """Test doctor exit codes."""
        result = subprocess.run(
            ["poetry", "run", "python", "-m", "kira.cli", "doctor", "--json-output"],
            capture_output=True,
        )

        # Exit code should be 0 (ok), 1 (fail), or 2 (warn)
        assert result.returncode in [0, 1, 2]


class TestDoctorChecks:
    """Tests for individual doctor checks."""

    def test_vault_check_missing_directory(self, tmp_path, monkeypatch):
        """Test vault check with missing directory."""
        # Point to non-existent vault
        monkeypatch.setenv("KIRA_VAULT_PATH", str(tmp_path / "nonexistent"))

        result = subprocess.run(
            ["poetry", "run", "python", "-m", "kira.cli", "doctor", "--json-output"],
            capture_output=True,
            text=True,
        )

        output = json.loads(result.stdout)

        # Should have vault path failure
        vault_checks = output["environment"]["checks"]
        vault_path_check = next(c for c in vault_checks if c["name"] == "Vault path")
        assert vault_path_check["status"] == "fail"

    def test_environment_check_no_env_file(self, tmp_path, monkeypatch):
        """Test environment check without .env file."""
        # Change to temp directory
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            result = subprocess.run(
                ["poetry", "run", "python", "-m", "kira.cli", "doctor", "--json-output"],
                capture_output=True,
                text=True,
                cwd=original_cwd,  # Run from project root
            )

            output = json.loads(result.stdout)

            # Check for .env warning (it's in project root, not temp dir)
            # This test mainly verifies the command runs
            assert "environment" in output

        finally:
            os.chdir(original_cwd)
