"""Kira monitor - tail and filter live logs.

Usage:
    poetry run python -m kira.cli monitor [--type audit|sandbox|errors] [--trace TRACE_ID]
"""

import json
import time
from pathlib import Path

import click


@click.command()
@click.option("--type", "log_type", type=click.Choice(["audit", "sandbox", "errors", "all"]), default="all")
@click.option("--trace", help="Filter by trace ID")
@click.option("--since", help="Show logs since (e.g., '5m', '1h')")
@click.option("--follow", "-f", is_flag=True, default=True, help="Follow log output")
def monitor(log_type: str, trace: str | None, since: str | None, follow: bool) -> None:
    """Monitor live Kira logs."""
    click.echo(f"📊 Monitoring Kira logs (type={log_type}, follow={follow})")
    if trace:
        click.echo(f"   Filtering by trace_id: {trace}")

    log_files = get_log_files(log_type)

    if not log_files:
        click.echo("No log files found", err=True)
        raise SystemExit(1)

    # Tail logs
    try:
        tail_logs(log_files, trace, follow)
    except KeyboardInterrupt:
        click.echo("\nMonitoring stopped")


def get_log_files(log_type: str) -> list[Path]:
    """Get log files to monitor."""
    files = []

    if log_type in ["audit", "all"]:
        audit_dir = Path("artifacts/audit")
        if audit_dir.exists():
            files.extend(sorted(audit_dir.glob("*.jsonl")))

    if log_type in ["sandbox", "all"]:
        sandbox_dir = Path("artifacts/sandbox/violations")
        if sandbox_dir.exists():
            files.extend(sorted(sandbox_dir.glob("*.jsonl")))

    if log_type in ["errors", "all"]:
        logs_dir = Path("logs")
        if logs_dir.exists():
            files.extend(sorted(logs_dir.glob("*.jsonl")))

    return files


def tail_logs(log_files: list[Path], trace_filter: str | None, follow: bool) -> None:
    """Tail log files."""
    # Track file positions
    file_positions: dict[Path, int] = {}

    for log_file in log_files:
        if log_file.exists():
            file_positions[log_file] = log_file.stat().st_size

    while True:
        for log_file in log_files:
            if not log_file.exists():
                continue

            current_size = log_file.stat().st_size
            last_pos = file_positions.get(log_file, 0)

            if current_size > last_pos:
                with log_file.open() as f:
                    f.seek(last_pos)
                    for line in f:
                        try:
                            entry = json.loads(line)
                            # Filter by trace if specified
                            if trace_filter and entry.get("trace_id") != trace_filter:
                                continue

                            print_log_entry(entry, log_file.name)
                        except json.JSONDecodeError:
                            # Skip malformed lines
                            pass

                file_positions[log_file] = current_size

        if not follow:
            break

        time.sleep(0.5)


def print_log_entry(entry: dict, source: str) -> None:
    """Print formatted log entry."""
    timestamp = entry.get("timestamp", "")
    event = entry.get("event", entry.get("event_type", "unknown"))
    trace_id = entry.get("trace_id", "")

    # Colorize based on event type
    if "error" in event.lower() or entry.get("status") == "error":
        color = "\033[91m"  # Red
    elif "warn" in event.lower():
        color = "\033[93m"  # Yellow
    else:
        color = "\033[92m"  # Green

    reset = "\033[0m"

    click.echo(
        f"{color}[{timestamp[:19]}] {source:20} {event:30} "
        f"trace={trace_id[:8] if trace_id else 'none':8}{reset}"
    )

    # Show relevant details
    if "message" in entry:
        click.echo(f"  → {entry['message']}")


if __name__ == "__main__":
    monitor()
