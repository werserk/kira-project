#!/usr/bin/env python3
"""Common CLI utilities for Phase 2: LLM-friendly CLI with JSON output, stable exit codes, and audit logging."""

import json
import traceback
import uuid
from datetime import UTC, datetime
from enum import IntEnum
from pathlib import Path
from typing import Any

import click


class ExitCode(IntEnum):
    """Stable exit codes for CLI commands (Phase 2, Task 9)."""

    SUCCESS = 0  # Successful execution
    VALIDATION_ERROR = 2  # Schema validation error
    CONFLICT_IDEMPOTENT = 3  # Conflict or idempotent operation
    FSM_ERROR = 4  # Finite State Machine guard failure
    IO_LOCK_ERROR = 5  # I/O or lock error
    CONFIG_ERROR = 6  # Configuration error
    UNKNOWN_ERROR = 7  # Unknown/unexpected error


class AuditLogger:
    """Audit logger for command execution history (Phase 2, Task 10)."""

    def __init__(self, artifacts_dir: Path | None = None):
        """Initialize audit logger.

        Args:
            artifacts_dir: Path to artifacts directory. Defaults to project root/artifacts
        """
        if artifacts_dir is None:
            # Default to project root/artifacts
            from ..config.settings import get_app_config

            config = get_app_config()
            artifacts_dir = Path(config.get("artifacts_dir", "artifacts"))

        self.audit_dir = artifacts_dir / "audit"
        self.audit_dir.mkdir(parents=True, exist_ok=True)

    def log(self, trace_id: str, cmd: str, args: dict[str, Any], result: dict[str, Any]) -> None:
        """Log command execution to JSONL.

        Args:
            trace_id: Trace ID for correlation
            cmd: Command name (e.g., "task.create")
            args: Command arguments
            result: Command result with status, data, error, etc.
        """
        # Generate daily log file
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        log_file = self.audit_dir / f"audit-{today}.jsonl"

        audit_entry = {
            "trace_id": trace_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "command": cmd,
            "args": args,
            "result": result,
        }

        # Append to JSONL
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")


class CLIContext:
    """Context for CLI execution with JSON output, trace ID, and audit logging."""

    def __init__(
        self,
        json_output: bool = False,
        dry_run: bool = False,
        yes: bool = False,
        trace_id: str | None = None,
        verbose: bool = False,
    ):
        """Initialize CLI context.

        Args:
            json_output: Enable JSON output mode
            dry_run: Enable dry-run mode (show plan, no execution)
            yes: Non-interactive mode (assume yes)
            trace_id: Trace ID for correlation
            verbose: Verbose output
        """
        self.json_output = json_output
        self.dry_run = dry_run
        self.yes = yes
        self.trace_id = trace_id or f"trace-{uuid.uuid4().hex[:12]}"
        self.verbose = verbose
        self.audit_logger = AuditLogger()

    def output(
        self, data: Any, status: str = "success", error: str | None = None, meta: dict[str, Any] | None = None
    ) -> None:
        """Output result in appropriate format.

        Args:
            data: Result data
            status: Status ("success", "error", "warning")
            error: Error message if status is error
            meta: Additional metadata
        """
        if self.json_output:
            # JSON mode: print only JSON, no logs
            result = {"status": status, "trace_id": self.trace_id}

            if error:
                result["error"] = error
            else:
                result["data"] = data

            if meta:
                result["meta"] = meta

            click.echo(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            # Human-readable mode
            if status == "error":
                click.echo(f"❌ {error}")
            elif status == "warning":
                click.echo(f"⚠️  {data}")
            else:
                # Format data for human output
                if isinstance(data, dict):
                    for key, value in data.items():
                        click.echo(f"{key}: {value}")
                elif isinstance(data, list):
                    for item in data:
                        click.echo(f"  - {item}")
                else:
                    click.echo(data)

    def log_audit(self, cmd: str, args: dict[str, Any], result: dict[str, Any]) -> None:
        """Log command to audit trail.

        Args:
            cmd: Command name
            args: Command arguments
            result: Command result
        """
        self.audit_logger.log(self.trace_id, cmd, args, result)

    def confirm(self, message: str) -> bool:
        """Ask for confirmation (or auto-confirm in yes mode).

        Args:
            message: Confirmation message

        Returns:
            True if confirmed, False otherwise
        """
        if self.yes:
            return True

        if self.json_output:
            # In JSON mode, can't ask for confirmation
            raise click.ClickException("Cannot confirm in --json mode. Use --yes for non-interactive execution.")

        return click.confirm(message)


def cli_command(func):
    """Decorator to add common CLI options to commands.

    Adds:
    - --json: JSON output mode
    - --dry-run: Dry-run mode
    - --yes: Non-interactive mode
    - --trace-id: Trace ID for correlation
    - --verbose: Verbose output
    """
    import functools

    @click.option("--json", "json_output", is_flag=True, help="Output as JSON (machine-readable)")
    @click.option("--dry-run", is_flag=True, help="Show plan without executing")
    @click.option("--yes", is_flag=True, help="Non-interactive mode (assume yes)")
    @click.option("--trace-id", type=str, help="Trace ID for correlation")
    @click.option("--verbose", "-v", is_flag=True, help="Verbose output")
    @functools.wraps(func)
    def wrapper(
        json_output: bool,
        dry_run: bool,
        yes: bool,
        trace_id: str | None,
        verbose: bool,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        # Create CLI context
        ctx = CLIContext(
            json_output=json_output,
            dry_run=dry_run,
            yes=yes,
            trace_id=trace_id,
            verbose=verbose,
        )

        # Inject context as first argument
        return func(ctx, *args, **kwargs)

    return wrapper


def handle_cli_error(ctx: CLIContext, exc: Exception, cmd: str, args: dict[str, Any]) -> int:
    """Handle CLI error and return appropriate exit code.

    Args:
        ctx: CLI context
        exc: Exception to handle
        cmd: Command name
        args: Command arguments

    Returns:
        Appropriate exit code
    """
    # Determine exit code based on exception type
    exit_code = ExitCode.UNKNOWN_ERROR
    error_msg = str(exc)

    # Import exceptions at runtime to avoid circular imports
    from ..core.task_fsm import FSMGuardError

    if "validation" in error_msg.lower() or "schema" in error_msg.lower():
        exit_code = ExitCode.VALIDATION_ERROR
    elif isinstance(exc, FSMGuardError):
        exit_code = ExitCode.FSM_ERROR
    elif "conflict" in error_msg.lower() or "already exists" in error_msg.lower():
        exit_code = ExitCode.CONFLICT_IDEMPOTENT
    elif "lock" in error_msg.lower() or "permission" in error_msg.lower() or isinstance(exc, IOError | OSError):
        exit_code = ExitCode.IO_LOCK_ERROR
    elif "config" in error_msg.lower():
        exit_code = ExitCode.CONFIG_ERROR

    # Log to audit
    result = {
        "status": "error",
        "error": error_msg,
        "error_type": type(exc).__name__,
        "exit_code": int(exit_code),
    }

    if ctx.verbose:
        result["traceback"] = traceback.format_exc()

    ctx.log_audit(cmd, args, result)

    # Output error
    ctx.output(None, status="error", error=error_msg, meta={"exit_code": int(exit_code)})

    if ctx.verbose and not ctx.json_output:
        click.echo("\nTraceback:", err=True)
        traceback.print_exc()

    return int(exit_code)


def handle_cli_success(
    ctx: CLIContext, data: Any, cmd: str, args: dict[str, Any], meta: dict[str, Any] | None = None
) -> int:
    """Handle CLI success and return success code.

    Args:
        ctx: CLI context
        data: Success data
        cmd: Command name
        args: Command arguments
        meta: Additional metadata

    Returns:
        Success exit code (0)
    """
    # Log to audit
    result = {"status": "success", "data": data, "exit_code": 0}

    if meta:
        result["meta"] = meta

    ctx.log_audit(cmd, args, result)

    # Output result
    ctx.output(data, status="success", meta=meta)

    return int(ExitCode.SUCCESS)
