"""Diagnostic CLI for log tailing and filtering (ADR-015).

Provides tools for viewing, filtering, and analyzing structured JSONL logs.
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import click

from kira.core.config import load_config

__all__ = ["diag_command"]


@click.group(name="diag")
def diag_command() -> None:
    """Diagnostic tools for logs and telemetry (ADR-015)."""
    pass


@diag_command.command(name="tail")
@click.option(
    "--component",
    "-c",
    help="Filter by component name (e.g., 'kira-core', 'telegram-adapter')",
)
@click.option(
    "--trace-id",
    "-t",
    help="Filter by trace ID for end-to-end request tracking",
)
@click.option(
    "--level",
    "-l",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    help="Filter by log level",
)
@click.option(
    "--since",
    "-s",
    help="Show logs since time (e.g., '10m', '1h', '2d')",
)
@click.option(
    "--follow",
    "-f",
    is_flag=True,
    help="Follow log output (like 'tail -f')",
)
@click.option(
    "--limit",
    "-n",
    type=int,
    default=50,
    help="Number of lines to show (default: 50)",
)
@click.option(
    "--category",
    type=click.Choice(["core", "adapters", "plugins", "pipelines", "all"]),
    default="all",
    help="Filter by component category",
)
@click.option(
    "--entity-id",
    "-e",
    help="Filter by entity ID",
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output raw JSON lines instead of formatted text",
)
def tail_command(
    component: str | None,
    trace_id: str | None,
    level: str | None,
    since: str | None,
    follow: bool,
    limit: int,
    category: str,
    entity_id: str | None,
    output_json: bool,
) -> None:
    """Tail structured logs with filtering (ADR-015).

    Examples:
        # Show last 50 lines from all components
        kira diag tail

        # Follow logs from telegram adapter
        kira diag tail -c telegram-adapter -f

        # Show errors from last hour
        kira diag tail -l ERROR --since 1h

        # Trace specific request end-to-end
        kira diag tail -t abc-123-def

        # Show logs for specific entity
        kira diag tail -e task-20251007-1234
    """
    config = load_config()
    log_dir = Path(config.get("log_dir", "logs"))

    if not log_dir.exists():
        click.echo(f"❌ Log directory not found: {log_dir}", err=True)
        sys.exit(1)

    # Parse since filter
    since_timestamp = None
    if since:
        since_timestamp = parse_since(since)

    # Collect log files
    log_files = collect_log_files(log_dir, category, component)

    if not log_files:
        click.echo("❌ No log files found matching criteria", err=True)
        sys.exit(1)

    # Process logs
    logs = []

    for log_file in log_files:
        try:
            with open(log_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        log_entry = json.loads(line)

                        # Apply filters
                        if not matches_filters(
                            log_entry,
                            trace_id=trace_id,
                            level=level,
                            since_timestamp=since_timestamp,
                            entity_id=entity_id,
                        ):
                            continue

                        logs.append(log_entry)

                    except json.JSONDecodeError:
                        continue

        except Exception as exc:
            click.echo(f"⚠️  Error reading {log_file}: {exc}", err=True)

    # Sort by timestamp
    logs.sort(key=lambda x: x.get("timestamp", ""))

    # Apply limit
    if not follow:
        logs = logs[-limit:]

    # Output
    if output_json:
        for log in logs:
            click.echo(json.dumps(log))
    else:
        for log in logs:
            click.echo(format_log_entry(log))

    # Follow mode (simple implementation)
    if follow:
        click.echo("\n[Following logs... Press Ctrl+C to stop]")
        # In production, this would use inotify or similar
        click.echo("(Follow mode not yet implemented)")


def collect_log_files(
    log_dir: Path,
    category: str,
    component: str | None,
) -> list[Path]:
    """Collect log files matching criteria.

    Parameters
    ----------
    log_dir
        Base log directory
    category
        Category filter (core/adapters/plugins/pipelines/all)
    component
        Component name filter

    Returns
    -------
    list[Path]
        List of log file paths
    """
    log_files = []

    categories = ["core", "adapters", "plugins", "pipelines"] if category == "all" else [category]

    for cat in categories:
        cat_dir = log_dir / cat

        if not cat_dir.exists():
            continue

        if component:
            # Specific component
            component_file = cat_dir / f"{component}.jsonl"
            if component_file.exists():
                log_files.append(component_file)
        else:
            # All components in category
            log_files.extend(cat_dir.glob("*.jsonl"))

    return log_files


def matches_filters(
    log_entry: dict,
    *,
    trace_id: str | None,
    level: str | None,
    since_timestamp: datetime | None,
    entity_id: str | None,
) -> bool:
    """Check if log entry matches filters.

    Parameters
    ----------
    log_entry
        Log entry dictionary
    trace_id
        Trace ID filter
    level
        Log level filter
    since_timestamp
        Minimum timestamp
    entity_id
        Entity ID filter

    Returns
    -------
    bool
        True if matches all filters
    """
    # Trace ID filter
    if trace_id:
        entry_trace_id = log_entry.get("trace_id") or log_entry.get("correlation_id")
        if entry_trace_id != trace_id:
            return False

    # Level filter
    if level and log_entry.get("level", "").upper() != level.upper():
        return False

    # Since filter
    if since_timestamp:
        try:
            entry_time = datetime.fromisoformat(log_entry.get("timestamp", "").replace("Z", "+00:00"))
            if entry_time < since_timestamp:
                return False
        except Exception:
            pass

    # Entity ID filter
    if entity_id:
        entry_entity_id = log_entry.get("entity_id") or log_entry.get("task_id")
        if entry_entity_id != entity_id:
            return False

    return True


def parse_since(since_str: str) -> datetime:
    """Parse 'since' time specification.

    Parameters
    ----------
    since_str
        Time specification (e.g., '10m', '1h', '2d')

    Returns
    -------
    datetime
        Parsed timestamp

    Raises
    ------
    ValueError
        If format is invalid
    """
    since_str = since_str.strip().lower()

    # Extract number and unit
    if since_str[-1] == "m":
        # Minutes
        minutes = int(since_str[:-1])
        return datetime.now() - timedelta(minutes=minutes)

    if since_str[-1] == "h":
        # Hours
        hours = int(since_str[:-1])
        return datetime.now() - timedelta(hours=hours)

    if since_str[-1] == "d":
        # Days
        days = int(since_str[:-1])
        return datetime.now() - timedelta(days=days)

    raise ValueError(f"Invalid 'since' format: {since_str} (use '10m', '1h', '2d')")


def format_log_entry(log: dict) -> str:
    """Format log entry for display.

    Parameters
    ----------
    log
        Log entry dictionary

    Returns
    -------
    str
        Formatted log line
    """
    # Extract fields
    timestamp = log.get("timestamp", "")
    level = log.get("level", "INFO")
    component = log.get("component", "unknown")
    message = log.get("message", "")

    # Truncate timestamp
    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

    # Level color
    level_colors = {
        "DEBUG": "blue",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
    }

    level_colored = click.style(
        f"[{level:7s}]",
        fg=level_colors.get(level, "white"),
        bold=True,
    )

    # Build line
    line = f"{timestamp} {level_colored} {component:20s} {message}"

    # Add trace ID if present
    trace_id = log.get("trace_id")
    if trace_id:
        line += click.style(f" [trace: {trace_id[:8]}]", fg="cyan", dim=True)

    # Add latency if present
    latency_ms = log.get("latency_ms")
    if latency_ms is not None:
        line += click.style(f" [{latency_ms:.1f}ms]", fg="magenta", dim=True)

    # Add outcome if present
    outcome = log.get("outcome")
    if outcome and outcome != "success":
        outcome_color = "red" if outcome == "failure" else "yellow"
        line += click.style(f" [{outcome}]", fg=outcome_color)

    # Add error if present
    error = log.get("error")
    if error:
        error_type = error.get("type", "Error")
        error_msg = error.get("message", "")
        line += f"\n  ❌ {error_type}: {error_msg}"

    return line


@diag_command.command(name="stats")
@click.option(
    "--category",
    type=click.Choice(["core", "adapters", "plugins", "pipelines", "all"]),
    default="all",
    help="Component category to analyze",
)
@click.option(
    "--since",
    "-s",
    help="Analyze logs since time (e.g., '10m', '1h', '2d')",
)
def stats_command(category: str, since: str | None) -> None:
    """Show log statistics and metrics.

    Examples:
        # Show overall statistics
        kira diag stats

        # Show adapter statistics from last hour
        kira diag stats --category adapters --since 1h
    """
    config = load_config()
    log_dir = Path(config.get("log_dir", "logs"))

    if not log_dir.exists():
        click.echo(f"❌ Log directory not found: {log_dir}", err=True)
        sys.exit(1)

    # Parse since filter
    since_timestamp = None
    if since:
        since_timestamp = parse_since(since)

    # Collect and analyze logs
    stats = {
        "total_logs": 0,
        "by_level": {},
        "by_component": {},
        "errors": 0,
        "avg_latency_ms": 0.0,
        "traces": set(),
    }

    log_files = collect_log_files(log_dir, category, None)

    latencies = []

    for log_file in log_files:
        try:
            with open(log_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        log_entry = json.loads(line)

                        # Apply time filter
                        if since_timestamp:
                            try:
                                entry_time = datetime.fromisoformat(
                                    log_entry.get("timestamp", "").replace("Z", "+00:00")
                                )
                                if entry_time < since_timestamp:
                                    continue
                            except Exception:
                                continue

                        stats["total_logs"] += 1

                        # Level stats
                        level = log_entry.get("level", "INFO")
                        stats["by_level"][level] = stats["by_level"].get(level, 0) + 1

                        # Component stats
                        component = log_entry.get("component", "unknown")
                        stats["by_component"][component] = stats["by_component"].get(component, 0) + 1

                        # Error count
                        if level == "ERROR":
                            stats["errors"] += 1

                        # Latency
                        if "latency_ms" in log_entry:
                            latencies.append(log_entry["latency_ms"])

                        # Traces
                        trace_id = log_entry.get("trace_id")
                        if trace_id:
                            stats["traces"].add(trace_id)

                    except json.JSONDecodeError:
                        continue

        except Exception as exc:
            click.echo(f"⚠️  Error reading {log_file}: {exc}", err=True)

    # Calculate averages
    if latencies:
        stats["avg_latency_ms"] = sum(latencies) / len(latencies)

    # Display stats
    click.echo("📊 Log Statistics")
    click.echo("=" * 60)
    click.echo(f"Total logs: {stats['total_logs']}")
    click.echo(f"Unique traces: {len(stats['traces'])}")
    click.echo(f"Errors: {stats['errors']}")

    if stats["avg_latency_ms"] > 0:
        click.echo(f"Avg latency: {stats['avg_latency_ms']:.1f}ms")

    click.echo("\n📈 By Level:")
    for level, count in sorted(stats["by_level"].items()):
        percentage = (count / stats["total_logs"] * 100) if stats["total_logs"] > 0 else 0
        click.echo(f"  {level:8s}: {count:6d} ({percentage:5.1f}%)")

    click.echo("\n🔧 By Component:")
    for component, count in sorted(stats["by_component"].items(), key=lambda x: x[1], reverse=True)[:10]:
        click.echo(f"  {component:25s}: {count:6d}")


if __name__ == "__main__":
    diag_command()
