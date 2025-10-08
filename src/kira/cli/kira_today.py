#!/usr/bin/env python3
"""CLI модуль для просмотра задач и событий на сегодня"""

import sys
from datetime import datetime, timezone
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import click
import yaml

from ..core.config import load_config

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.command(
    context_settings=CONTEXT_SETTINGS,
    help="Показать задачи и события на сегодня",
)
@click.option(
    "--tomorrow",
    is_flag=True,
    help="Показать на завтра вместо сегодня",
)
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def cli(tomorrow: bool, verbose: bool) -> int:
    """Показать задачи и события на сегодня."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        if not vault_path.exists():
            click.echo(f"❌ Vault не найден: {vault_path}")
            return 1

        # Определить целевую дату
        now = datetime.now(timezone.utc)
        from datetime import timedelta
        target_date = now.date() if not tomorrow else (now + timedelta(days=1)).date()

        # Заголовок
        date_str = target_date.strftime("%Y-%m-%d (%A)")
        if tomorrow:
            click.echo(f"📅 План на завтра: {date_str}\n")
        else:
            click.echo(f"📅 Сегодня: {date_str}\n")

        # 1. Активные задачи (в работе)
        doing_tasks = load_doing_tasks(vault_path)
        if doing_tasks:
            click.echo("🔄 В работе:")
            for task in doing_tasks:
                title = task.get("title", "Untitled")
                task_id = task.get("id", "")
                click.echo(f"  • {title}")
                if verbose:
                    click.echo(f"    ID: {task_id}")
            click.echo()

        # 2. Задачи с дедлайном на сегодня/завтра
        due_tasks = load_tasks_with_due_date(vault_path, target_date)
        if due_tasks:
            if tomorrow:
                click.echo("📋 Дедлайны завтра:")
            else:
                click.echo("📋 Дедлайны сегодня:")
            
            for task in due_tasks:
                title = task.get("title", "Untitled")
                status = task.get("status", "todo")
                task_id = task.get("id", "")
                
                status_icon = {"todo": "⏳", "doing": "🔄", "review": "👀", "done": "✅", "blocked": "🚫"}.get(status, "❓")
                
                click.echo(f"  {status_icon} {title}")
                if verbose:
                    click.echo(f"      ID: {task_id}, Статус: {status}")
            click.echo()

        # 3. События на сегодня/завтра
        events = load_events_for_date(vault_path, target_date)
        if events:
            click.echo("📆 События:")
            for event in events:
                title = event.get("title", "Untitled")
                start = event.get("start")
                end = event.get("end")
                location = event.get("location")
                
                time_str = format_time_range(start, end) if start else ""
                location_str = f" @ {location}" if location else ""
                
                click.echo(f"  • {time_str}: {title}{location_str}")
                if verbose:
                    click.echo(f"      ID: {event.get('id')}")
            click.echo()

        # 4. Просроченные задачи (только для сегодня)
        if not tomorrow:
            overdue_tasks = load_overdue_tasks(vault_path, target_date)
            if overdue_tasks:
                click.echo("🔴 Просроченные задачи:")
                for task in overdue_tasks:
                    title = task.get("title", "Untitled")
                    due = task.get("due")
                    task_id = task.get("id", "")
                    
                    due_date = parse_date(due).date() if due else None
                    days_overdue = (target_date - due_date).days if due_date else 0
                    
                    click.echo(f"  ⚠️  {title} (просрочено на {days_overdue} дн.)")
                    if verbose:
                        click.echo(f"      ID: {task_id}, Дедлайн: {due}")
                click.echo()

        # 5. Следующие задачи (todo без дедлайна)
        if not tomorrow:
            next_tasks = load_next_tasks(vault_path, limit=5)
            if next_tasks:
                click.echo("⏭️  Следующие задачи:")
                for task in next_tasks:
                    title = task.get("title", "Untitled")
                    click.echo(f"  • {title}")
                    if verbose:
                        click.echo(f"      ID: {task.get('id')}")
                click.echo()

        # Итоговая статистика
        total_items = len(doing_tasks) + len(due_tasks) + len(events)
        if not tomorrow:
            total_items += len(overdue_tasks)

        if total_items == 0:
            if tomorrow:
                click.echo("🎉 На завтра ничего не запланировано!")
            else:
                click.echo("🎉 Сегодня свободный день!")
        else:
            summary_parts = []
            if doing_tasks:
                summary_parts.append(f"{len(doing_tasks)} в работе")
            if due_tasks:
                summary_parts.append(f"{len(due_tasks)} дедлайнов")
            if events:
                summary_parts.append(f"{len(events)} событий")
            if not tomorrow and overdue_tasks:
                summary_parts.append(f"{len(overdue_tasks)} просрочено")

            click.echo(f"📊 Итого: {', '.join(summary_parts)}")

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


# Helper functions

def load_doing_tasks(vault_path: Path) -> list[dict]:
    """Загрузить задачи в статусе doing."""
    tasks_dir = vault_path / "tasks"
    if not tasks_dir.exists():
        return []

    doing_tasks = []
    for task_file in tasks_dir.glob("task-*.md"):
        try:
            with open(task_file, encoding="utf-8") as f:
                content = f.read()

            if not content.startswith("---"):
                continue

            parts = content.split("---", 2)
            if len(parts) < 3:
                continue

            metadata = yaml.safe_load(parts[1])
            if metadata.get("status") == "doing":
                doing_tasks.append(metadata)

        except Exception:
            continue

    return doing_tasks


def load_tasks_with_due_date(vault_path: Path, target_date) -> list[dict]:
    """Загрузить задачи с дедлайном на указанную дату."""
    tasks_dir = vault_path / "tasks"
    if not tasks_dir.exists():
        return []

    due_tasks = []
    for task_file in tasks_dir.glob("task-*.md"):
        try:
            with open(task_file, encoding="utf-8") as f:
                content = f.read()

            if not content.startswith("---"):
                continue

            parts = content.split("---", 2)
            if len(parts) < 3:
                continue

            metadata = yaml.safe_load(parts[1])
            due = metadata.get("due")
            status = metadata.get("status", "todo")

            if due and status not in ["done"]:
                due_date = parse_date(due).date()
                if due_date == target_date:
                    due_tasks.append(metadata)

        except Exception:
            continue

    # Сортировка по статусу
    def sort_key(task):
        status = task.get("status", "todo")
        status_order = {"doing": 0, "todo": 1, "review": 2, "blocked": 3}
        return status_order.get(status, 4)

    due_tasks.sort(key=sort_key)
    return due_tasks


def load_overdue_tasks(vault_path: Path, today) -> list[dict]:
    """Загрузить просроченные задачи."""
    tasks_dir = vault_path / "tasks"
    if not tasks_dir.exists():
        return []

    overdue_tasks = []
    for task_file in tasks_dir.glob("task-*.md"):
        try:
            with open(task_file, encoding="utf-8") as f:
                content = f.read()

            if not content.startswith("---"):
                continue

            parts = content.split("---", 2)
            if len(parts) < 3:
                continue

            metadata = yaml.safe_load(parts[1])
            due = metadata.get("due")
            status = metadata.get("status", "todo")

            if due and status not in ["done"]:
                due_date = parse_date(due).date()
                if due_date < today:
                    overdue_tasks.append(metadata)

        except Exception:
            continue

    # Сортировка по дате (самые старые первыми)
    overdue_tasks.sort(key=lambda t: t.get("due", ""))
    return overdue_tasks


def load_next_tasks(vault_path: Path, limit: int = 5) -> list[dict]:
    """Загрузить следующие задачи (todo без дедлайна)."""
    tasks_dir = vault_path / "tasks"
    if not tasks_dir.exists():
        return []

    next_tasks = []
    for task_file in tasks_dir.glob("task-*.md"):
        try:
            with open(task_file, encoding="utf-8") as f:
                content = f.read()

            if not content.startswith("---"):
                continue

            parts = content.split("---", 2)
            if len(parts) < 3:
                continue

            metadata = yaml.safe_load(parts[1])
            status = metadata.get("status", "todo")
            due = metadata.get("due")

            if status == "todo" and not due:
                next_tasks.append(metadata)

        except Exception:
            continue

    # Сортировка по дате создания
    next_tasks.sort(key=lambda t: t.get("created", ""))
    return next_tasks[:limit]


def load_events_for_date(vault_path: Path, target_date) -> list[dict]:
    """Загрузить события на указанную дату."""
    events_dir = vault_path / "events"
    if not events_dir.exists():
        return []

    events = []
    for event_file in events_dir.glob("event-*.md"):
        try:
            with open(event_file, encoding="utf-8") as f:
                content = f.read()

            if not content.startswith("---"):
                continue

            parts = content.split("---", 2)
            if len(parts) < 3:
                continue

            metadata = yaml.safe_load(parts[1])
            start = metadata.get("start")

            if start:
                start_date = parse_date(start).date()
                if start_date == target_date:
                    events.append(metadata)

        except Exception:
            continue

    # Сортировка по времени начала
    events.sort(key=lambda e: e.get("start", ""))
    return events


def parse_date(date_str: str) -> datetime:
    """Парсинг даты из строки."""
    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))


def format_time_range(start_str: str, end_str: str | None) -> str:
    """Форматировать диапазон времени."""
    start = parse_date(start_str)
    start_time = start.strftime("%H:%M")

    if end_str:
        end = parse_date(end_str)
        end_time = end.strftime("%H:%M")
        return f"{start_time}-{end_time}"
    else:
        return start_time


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]

    try:
        return cli.main(args=list(args), standalone_mode=False)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 0


if __name__ == "__main__":
    sys.exit(main())

