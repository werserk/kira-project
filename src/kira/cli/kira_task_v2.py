#!/usr/bin/env python3
"""CLI module for task management with Phase 2 enhancements (JSON output, stable exit codes, audit logging)."""

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import click

from ..core.config import load_config
from ..core.host import create_host_api
from ..core.task_fsm import FSMGuardError
from .cli_common import CLIContext, ExitCode, cli_command, handle_cli_error, handle_cli_success

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(
    context_settings=CONTEXT_SETTINGS,
    help="Task management with JSON output, stable exit codes, and audit logging",
)
def cli() -> None:
    """Root command for tasks (Phase 2)."""


@cli.command("create")
@click.option("--title", required=True, help="Task title")
@click.option("--due", type=str, help="Due date (YYYY-MM-DD or 'today', 'tomorrow')")
@click.option("--tag", multiple=True, help="Tags (can specify multiple)")
@click.option("--priority", type=click.Choice(["low", "medium", "high"]), default="medium")
@cli_command
def create_command(ctx: CLIContext, title: str, due: str | None, tag: tuple[str, ...], priority: str) -> int:
    """Create a new task (Phase 2 with JSON output and audit)."""
    cmd = "task.create"
    args = {"title": title, "due": due, "tags": list(tag), "priority": priority}

    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        if not vault_path.exists():
            raise FileNotFoundError(f"Vault not found: {vault_path}")

        # Dry-run mode
        if ctx.dry_run:
            plan = {
                "action": "create_task",
                "title": title,
                "priority": priority,
                "vault_path": str(vault_path),
            }
            if due:
                plan["due"] = due
            if tag:
                plan["tags"] = list(tag)

            ctx.output(plan, status="success", meta={"dry_run": True})
            return int(ExitCode.SUCCESS)

        # Parse due date
        due_date = None
        if due:
            due_date = parse_due_date(due)

        # Create task via Host API
        host_api = create_host_api(vault_path)

        entity_data = {
            "title": title,
            "status": "todo",
            "priority": priority,
            "created": datetime.now(UTC).isoformat(),
        }

        if due_date:
            entity_data["due"] = due_date.isoformat()

        if tag:
            entity_data["tags"] = list(tag)

        entity = host_api.create_entity("task", entity_data, content=f"# {title}\n\n")

        result = {
            "task_id": entity.id,
            "title": title,
            "status": "todo",
            "priority": priority,
            "file_path": str(entity.path),
        }

        if due_date:
            result["due"] = due_date.isoformat()

        return handle_cli_success(ctx, result, cmd, args)

    except Exception as exc:
        return handle_cli_error(ctx, exc, cmd, args)


@cli.command("update")
@click.argument("task_id")
@click.option("--status", type=click.Choice(["todo", "doing", "review", "done", "blocked"]))
@click.option("--title", type=str)
@click.option("--priority", type=click.Choice(["low", "medium", "high"]))
@cli_command
def update_command(ctx: CLIContext, task_id: str, status: str | None, title: str | None, priority: str | None) -> int:
    """Update a task (Phase 2 with FSM guards and audit)."""
    cmd = "task.update"
    args = {"task_id": task_id, "status": status, "title": title, "priority": priority}

    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        # Find task
        task_path = find_task_path(vault_path, task_id)
        if not task_path:
            raise FileNotFoundError(f"Task not found: {task_id}")

        # Prepare updates
        updates = {}
        if status:
            updates["status"] = status
        if title:
            updates["title"] = title
        if priority:
            updates["priority"] = priority

        if not updates:
            raise ValueError("No updates specified")

        # Dry-run mode
        if ctx.dry_run:
            plan = {"action": "update_task", "task_id": task_id, "updates": updates}
            ctx.output(plan, status="success", meta={"dry_run": True})
            return int(ExitCode.SUCCESS)

        # Update via Host API
        host_api = create_host_api(vault_path)
        updated_entity = host_api.update_entity(task_id, updates)

        result = {
            "task_id": updated_entity.id,
            "updated_fields": list(updates.keys()),
            "file_path": str(updated_entity.path),
        }

        return handle_cli_success(ctx, result, cmd, args)

    except FSMGuardError as exc:
        # FSM guard violation - specific exit code
        return handle_cli_error(ctx, exc, cmd, args)
    except Exception as exc:
        return handle_cli_error(ctx, exc, cmd, args)


@cli.command("list")
@click.option(
    "--status",
    type=click.Choice(["todo", "doing", "review", "done", "blocked", "all"]),
    default="all",
)
@click.option("--tag", type=str)
@click.option("--limit", type=int, default=50)
@cli_command
def list_command(ctx: CLIContext, status: str, tag: str | None, limit: int) -> int:
    """List tasks (Phase 2 with JSON output)."""
    cmd = "task.list"
    args = {"status": status, "tag": tag, "limit": limit}

    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        if not vault_path.exists():
            raise FileNotFoundError(f"Vault not found: {vault_path}")

        tasks_dir = vault_path / "tasks"
        if not tasks_dir.exists():
            return handle_cli_success(ctx, [], cmd, args, meta={"total": 0})

        # Load and filter tasks
        from .kira_task import filter_tasks, load_tasks

        tasks = load_tasks(tasks_dir)
        filtered_tasks = filter_tasks(tasks, status, "all", tag)[:limit]

        # Format for output
        result = []
        for task in filtered_tasks:
            task_data = {
                "id": task.get("id"),
                "title": task.get("title"),
                "status": task.get("status"),
                "priority": task.get("priority"),
            }
            if task.get("due"):
                task_data["due"] = task.get("due")
            if task.get("tags"):
                task_data["tags"] = task.get("tags")

            result.append(task_data)

        return handle_cli_success(ctx, result, cmd, args, meta={"total": len(result)})

    except Exception as exc:
        return handle_cli_error(ctx, exc, cmd, args)


@cli.command("get")
@click.argument("task_id")
@cli_command
def get_command(ctx: CLIContext, task_id: str) -> int:
    """Get task details (Phase 2 with JSON output)."""
    cmd = "task.get"
    args = {"task_id": task_id}

    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        from .kira_task import find_task_by_id

        task = find_task_by_id(vault_path, task_id)
        if not task:
            raise FileNotFoundError(f"Task not found: {task_id}")

        # Format task data
        result = {
            "id": task.get("id"),
            "title": task.get("title"),
            "status": task.get("status"),
            "priority": task.get("priority"),
            "created": task.get("created"),
            "updated": task.get("updated"),
            "file_path": str(task.get("_path")),
        }

        if task.get("due"):
            result["due"] = task.get("due")
        if task.get("tags"):
            result["tags"] = task.get("tags")
        if task.get("_body"):
            result["content"] = task.get("_body")

        return handle_cli_success(ctx, result, cmd, args)

    except Exception as exc:
        return handle_cli_error(ctx, exc, cmd, args)


@cli.command("delete")
@click.argument("task_id")
@cli_command
def delete_command(ctx: CLIContext, task_id: str) -> int:
    """Delete a task (Phase 2 with confirmation and audit)."""
    cmd = "task.delete"
    args = {"task_id": task_id}

    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        task_path = find_task_path(vault_path, task_id)
        if not task_path:
            raise FileNotFoundError(f"Task not found: {task_id}")

        # Dry-run mode
        if ctx.dry_run:
            plan = {"action": "delete_task", "task_id": task_id, "file_path": str(task_path)}
            ctx.output(plan, status="success", meta={"dry_run": True})
            return int(ExitCode.SUCCESS)

        # Confirmation (unless --yes)
        if not ctx.confirm(f"Delete task {task_id}?"):
            result = {"action": "cancelled", "task_id": task_id}
            return handle_cli_success(ctx, result, cmd, args)

        # Delete file
        task_path.unlink()

        result = {"action": "deleted", "task_id": task_id, "file_path": str(task_path)}
        return handle_cli_success(ctx, result, cmd, args)

    except Exception as exc:
        return handle_cli_error(ctx, exc, cmd, args)


# Helper functions


def find_task_path(vault_path: Path, task_id: str) -> Path | None:
    """Find path to task file."""
    from .kira_task import find_task_by_id

    task = find_task_by_id(vault_path, task_id)
    if task:
        return task.get("_path")
    return None


def parse_due_date(due_str: str) -> datetime:
    """Parse due date from string."""
    from datetime import timedelta

    due_str = due_str.lower().strip()
    now = datetime.now(UTC)

    if due_str == "today":
        return now.replace(hour=23, minute=59, second=59, microsecond=0)
    if due_str == "tomorrow":
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=23, minute=59, second=59, microsecond=0)

    # Try ISO format
    try:
        return datetime.fromisoformat(due_str).replace(tzinfo=UTC)
    except ValueError:
        # Try YYYY-MM-DD
        date_obj = datetime.strptime(due_str, "%Y-%m-%d")
        return date_obj.replace(hour=23, minute=59, second=59, tzinfo=UTC)


def main(args: list[str] | None = None) -> int:
    """Main entry point."""
    if args is None:
        args = sys.argv[1:]

    try:
        return cli.main(args=list(args), standalone_mode=False) or 0
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 0


if __name__ == "__main__":
    sys.exit(main())
