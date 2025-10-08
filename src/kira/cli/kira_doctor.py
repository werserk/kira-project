"""Kira doctor - diagnostic tool for environment and system health.

Usage:
    poetry run python -m kira.cli doctor
"""

import json
import os
from pathlib import Path

import click


@click.command()
@click.option("--json-output", is_flag=True, help="Output as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def doctor(json_output: bool, verbose: bool) -> None:
    """Run system diagnostics and health checks."""
    results = {
        "environment": check_environment(),
        "vault": check_vault(),
        "adapters": check_adapters(),
        "permissions": check_permissions(),
    }

    # Calculate overall status
    all_checks = []
    for category in results.values():
        all_checks.extend(category["checks"])

    failed = sum(1 for c in all_checks if c["status"] == "fail")
    warnings = sum(1 for c in all_checks if c["status"] == "warn")
    passed = sum(1 for c in all_checks if c["status"] == "ok")

    results["summary"] = {
        "total": len(all_checks),
        "passed": passed,
        "warnings": warnings,
        "failed": failed,
        "overall": "fail" if failed > 0 else ("warn" if warnings > 0 else "ok"),
    }

    if json_output:
        click.echo(json.dumps(results, indent=2))
    else:
        print_colorized_report(results, verbose)

    # Exit code
    if results["summary"]["overall"] == "fail":
        raise SystemExit(1)
    elif results["summary"]["overall"] == "warn":
        raise SystemExit(2)


def check_environment() -> dict:
    """Check environment configuration."""
    checks = []

    # Check .env file
    env_path = Path(".env")
    if env_path.exists():
        checks.append({"name": ".env file", "status": "ok", "message": "Found"})
    else:
        checks.append({"name": ".env file", "status": "warn", "message": "Not found, using defaults"})

    # Check vault path
    vault_path = os.getenv("KIRA_VAULT_PATH", "vault")
    if Path(vault_path).exists():
        checks.append({"name": "Vault path", "status": "ok", "message": f"Found at {vault_path}"})
    else:
        checks.append({"name": "Vault path", "status": "fail", "message": f"Not found at {vault_path}"})

    # Check LLM provider keys
    provider = os.getenv("LLM_PROVIDER", "openrouter")
    if provider == "openrouter":
        key = os.getenv("OPENROUTER_API_KEY")
        if key:
            checks.append({"name": "OpenRouter API key", "status": "ok", "message": "Configured"})
        else:
            checks.append({"name": "OpenRouter API key", "status": "fail", "message": "Missing"})
    elif provider == "openai":
        key = os.getenv("OPENAI_API_KEY")
        if key:
            checks.append({"name": "OpenAI API key", "status": "ok", "message": "Configured"})
        else:
            checks.append({"name": "OpenAI API key", "status": "fail", "message": "Missing"})

    return {"category": "Environment", "checks": checks}


def check_vault() -> dict:
    """Check vault consistency."""
    checks = []

    vault_path = Path(os.getenv("KIRA_VAULT_PATH", "vault"))

    # Check required directories
    required_dirs = ["tasks", "notes", "events", "inbox"]
    for dir_name in required_dirs:
        dir_path = vault_path / dir_name
        if dir_path.exists():
            checks.append({"name": f"{dir_name}/ directory", "status": "ok", "message": "Exists"})
        else:
            checks.append({"name": f"{dir_name}/ directory", "status": "warn", "message": "Missing"})

    # Check write permissions
    if os.access(vault_path, os.W_OK):
        checks.append({"name": "Vault write access", "status": "ok", "message": "Writable"})
    else:
        checks.append({"name": "Vault write access", "status": "fail", "message": "Not writable"})

    return {"category": "Vault", "checks": checks}


def check_adapters() -> dict:
    """Check adapter connectivity."""
    checks = []

    # Check Ollama (local)
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        import httpx

        with httpx.Client(timeout=2.0) as client:
            response = client.get(f"{ollama_url}/api/tags")
            if response.status_code == 200:
                checks.append({"name": "Ollama", "status": "ok", "message": "Available"})
            else:
                checks.append({"name": "Ollama", "status": "warn", "message": "Not responding"})
    except Exception:
        checks.append({"name": "Ollama", "status": "warn", "message": "Not available (optional)"})

    # Network connectivity
    try:
        import httpx

        with httpx.Client(timeout=5.0) as client:
            response = client.get("https://api.openrouter.ai/api/v1/models")
            if response.status_code in [200, 401]:  # 401 means network works, just no key
                checks.append({"name": "Network connectivity", "status": "ok", "message": "Online"})
            else:
                checks.append({"name": "Network connectivity", "status": "warn", "message": "Limited"})
    except Exception as e:
        checks.append({"name": "Network connectivity", "status": "fail", "message": f"Offline: {e}"})

    return {"category": "Adapters", "checks": checks}


def check_permissions() -> dict:
    """Check file permissions."""
    checks = []

    # Check audit directory
    audit_dir = Path("artifacts/audit")
    if audit_dir.exists() and os.access(audit_dir, os.W_OK):
        checks.append({"name": "Audit directory", "status": "ok", "message": "Writable"})
    elif audit_dir.exists():
        checks.append({"name": "Audit directory", "status": "fail", "message": "Not writable"})
    else:
        checks.append({"name": "Audit directory", "status": "warn", "message": "Will be created"})

    # Check logs directory
    logs_dir = Path("logs")
    if logs_dir.exists() and os.access(logs_dir, os.W_OK):
        checks.append({"name": "Logs directory", "status": "ok", "message": "Writable"})
    else:
        checks.append({"name": "Logs directory", "status": "warn", "message": "Will be created"})

    return {"category": "Permissions", "checks": checks}


def print_colorized_report(results: dict, verbose: bool) -> None:
    """Print colorized diagnostic report."""
    # Colors
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    click.echo(f"\n{BOLD}=== Kira System Diagnostics ==={RESET}\n")

    for key, category_data in results.items():
        if key == "summary":
            continue

        click.echo(f"{BOLD}{category_data['category']}:{RESET}")

        for check in category_data["checks"]:
            status = check["status"]
            name = check["name"]
            message = check["message"]

            if status == "ok":
                icon = f"{GREEN}✓{RESET}"
            elif status == "warn":
                icon = f"{YELLOW}⚠{RESET}"
            else:
                icon = f"{RED}✗{RESET}"

            click.echo(f"  {icon} {name}: {message}")

        click.echo()

    # Summary
    summary = results["summary"]
    overall = summary["overall"]

    if overall == "ok":
        color = GREEN
        status_text = "HEALTHY"
    elif overall == "warn":
        color = YELLOW
        status_text = "WARNINGS"
    else:
        color = RED
        status_text = "ISSUES FOUND"

    click.echo(f"{BOLD}Summary:{RESET}")
    click.echo(f"  Total checks: {summary['total']}")
    click.echo(f"  {GREEN}Passed: {summary['passed']}{RESET}")
    click.echo(f"  {YELLOW}Warnings: {summary['warnings']}{RESET}")
    click.echo(f"  {RED}Failed: {summary['failed']}{RESET}")
    click.echo(f"\n{BOLD}Overall Status: {color}{status_text}{RESET}\n")


if __name__ == "__main__":
    doctor()
