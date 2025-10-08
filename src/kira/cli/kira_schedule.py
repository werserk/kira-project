#!/usr/bin/env python3
"""CLI модуль для просмотра и управления расписанием"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import click

from ..core.config import load_config

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(
    context_settings=CONTEXT_SETTINGS,
    help="Просмотр и управление расписанием",
)
def cli() -> None:
    """Корневая команда расписания."""


@cli.command("view")
@click.option(
    "--today",
    "period",
    flag_value="today",
    default=True,
    help="Показать расписание на сегодня (по умолчанию)",
)
@click.option(
    "--tomorrow",
    "period",
    flag_value="tomorrow",
    help="Показать расписание на завтра",
)
@click.option(
    "--week",
    "period",
    flag_value="week",
    help="Показать расписание на неделю",
)
@click.option(
    "--date",
    type=str,
    help="Показать расписание на конкретную дату (YYYY-MM-DD)",
)
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def view_command(period: str, date: str | None, verbose: bool) -> int:
    """Показать расписание на указанный период."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        if not vault_path.exists():
            click.echo(f"❌ Vault не найден: {vault_path}")
            return 1

        # Определить даты для просмотра
        if date:
            start_date = datetime.fromisoformat(date)
            end_date = start_date
        elif period == "tomorrow":
            start_date = datetime.now() + timedelta(days=1)
            end_date = start_date
        elif period == "week":
            start_date = datetime.now()
            end_date = start_date + timedelta(days=7)
        else:  # today
            start_date = datetime.now()
            end_date = start_date

        # Загрузить события и задачи
        events = load_events(vault_path, start_date, end_date)
        tasks = load_tasks_with_deadlines(vault_path, start_date, end_date)

        # Отобразить расписание
        display_schedule(events, tasks, start_date, end_date, verbose)

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


@cli.command("conflicts")
@click.option(
    "--today",
    "period",
    flag_value="today",
    default=True,
    help="Проверить конфликты на сегодня (по умолчанию)",
)
@click.option(
    "--week",
    "period",
    flag_value="week",
    help="Проверить конфликты на неделю",
)
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def conflicts_command(period: str, verbose: bool) -> int:
    """Найти конфликты в расписании (overlapping events)."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        if not vault_path.exists():
            click.echo(f"❌ Vault не найден: {vault_path}")
            return 1

        # Определить период
        start_date = datetime.now()
        end_date = start_date + timedelta(days=7 if period == "week" else 1)

        # Загрузить события
        events = load_events(vault_path, start_date, end_date)

        # Найти конфликты
        conflicts = find_conflicts(events)

        if not conflicts:
            click.echo("✅ Конфликтов не найдено")
            return 0

        # Отобразить конфликты
        click.echo(f"⚠️  Найдено конфликтов: {len(conflicts)}\n")
        for i, conflict in enumerate(conflicts, 1):
            event1, event2 = conflict
            click.echo(f"{i}. {format_datetime(event1['start'])}")
            click.echo(f"   ⚔️  {event1['title']}")
            click.echo(f"   ⚔️  {event2['title']}")
            if verbose:
                click.echo(f"       {event1['file']}")
                click.echo(f"       {event2['file']}")
            click.echo()

        return 1  # Exit code 1 if conflicts found

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


@cli.command("quick")
@click.argument("description")
@click.option("--date", type=str, help="Дата (YYYY-MM-DD), по умолчанию сегодня")
@click.option("--time", type=str, help="Время (HH:MM), по умолчанию 09:00")
@click.option("--duration", type=int, default=60, help="Длительность в минутах")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def quick_command(description: str, date: str | None, time: str | None, duration: int, verbose: bool) -> int:
    """Быстро создать событие."""
    try:
        from ..core.host import create_host_api

        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        # Parse date and time
        event_date = datetime.fromisoformat(date) if date else datetime.now()

        if time:
            hour, minute = map(int, time.split(":"))
            event_date = event_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            event_date = event_date.replace(hour=9, minute=0, second=0, microsecond=0)

        end_date = event_date + timedelta(minutes=duration)

        # Create event
        host_api = create_host_api(vault_path)
        entity = host_api.create_entity(
            entity_type="event",
            data={
                "title": description,
                "start": event_date.isoformat(),
                "end": end_date.isoformat(),
            },
            content=f"# {description}\n\n<!-- Notes -->\n",
        )
        entity_id = entity.id

        click.echo(f"✅ Событие создано: {entity_id}")
        if verbose:
            click.echo(f"   Начало: {format_datetime(event_date)}")
            click.echo(f"   Конец: {format_datetime(end_date)}")
            click.echo(f"   Длительность: {duration} мин")

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка создания события: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


# Helper functions


def load_events(vault_path: Path, start_date: datetime, end_date: datetime) -> list[dict[str, Any]]:
    """Загрузить события из Vault за указанный период."""
    events = []
    events_dir = vault_path / "events"

    if not events_dir.exists():
        return events

    for event_file in events_dir.glob("event-*.md"):
        try:
            # Parse frontmatter
            with open(event_file, encoding="utf-8") as f:
                content = f.read()

            if not content.startswith("---"):
                continue

            # Extract frontmatter
            parts = content.split("---", 2)
            if len(parts) < 3:
                continue

            import yaml

            metadata = yaml.safe_load(parts[1])

            # Parse event start/end
            start_str = metadata.get("start")
            if not start_str:
                continue

            event_start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))

            # Check if in range
            if start_date.date() <= event_start.date() <= end_date.date():
                end_str = metadata.get("end")
                event_end = datetime.fromisoformat(end_str.replace("Z", "+00:00")) if end_str else event_start

                events.append(
                    {
                        "id": metadata.get("id"),
                        "title": metadata.get("title", "Untitled"),
                        "start": event_start,
                        "end": event_end,
                        "location": metadata.get("location"),
                        "file": str(event_file),
                    }
                )
        except Exception:
            continue

    # Sort by start time
    events.sort(key=lambda e: e["start"])
    return events


def load_tasks_with_deadlines(vault_path: Path, start_date: datetime, end_date: datetime) -> list[dict[str, Any]]:
    """Загрузить задачи с дедлайнами за указанный период."""
    tasks = []
    tasks_dir = vault_path / "tasks"

    if not tasks_dir.exists():
        return tasks

    for task_file in tasks_dir.glob("task-*.md"):
        try:
            # Parse frontmatter
            with open(task_file, encoding="utf-8") as f:
                content = f.read()

            if not content.startswith("---"):
                continue

            parts = content.split("---", 2)
            if len(parts) < 3:
                continue

            import yaml

            metadata = yaml.safe_load(parts[1])

            # Check if has deadline
            due_str = metadata.get("due")
            if not due_str:
                continue

            due_date = datetime.fromisoformat(due_str.replace("Z", "+00:00"))

            # Check if in range
            if start_date.date() <= due_date.date() <= end_date.date():
                status = metadata.get("status", "todo")

                tasks.append(
                    {
                        "id": metadata.get("id"),
                        "title": metadata.get("title", "Untitled"),
                        "due": due_date,
                        "status": status,
                        "file": str(task_file),
                    }
                )
        except Exception:
            continue

    # Sort by due date
    tasks.sort(key=lambda t: t["due"])
    return tasks


def find_conflicts(events: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Найти overlapping события (конфликты)."""
    conflicts = []

    for i, event1 in enumerate(events):
        for event2 in events[i + 1 :]:
            # Check if events overlap
            if event1["end"] > event2["start"] and event1["start"] < event2["end"]:
                conflicts.append((event1, event2))

    return conflicts


def display_schedule(
    events: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    start_date: datetime,
    end_date: datetime,
    verbose: bool,
) -> None:
    """Отобразить расписание."""
    # Header
    if start_date.date() == end_date.date():
        click.echo(f"📅 Расписание на {format_date(start_date)}\n")
    else:
        click.echo(f"📅 Расписание: {format_date(start_date)} - {format_date(end_date)}\n")

    # Events
    if events:
        click.echo("📆 События:")
        for event in events:
            time_str = format_time_range(event["start"], event["end"])
            location_str = f" @ {event['location']}" if event.get("location") else ""
            click.echo(f"  {time_str}: {event['title']}{location_str}")
            if verbose:
                click.echo(f"           {event['file']}")
        click.echo()
    else:
        click.echo("📆 События: нет\n")

    # Tasks with deadlines
    if tasks:
        click.echo("✅ Задачи с дедлайнами:")
        for task in tasks:
            status_icon = {"todo": "⏳", "doing": "🔄", "done": "✅", "blocked": "🚫"}.get(task["status"], "❓")
            time_str = format_time(task["due"])
            click.echo(f"  {status_icon} {time_str}: {task['title']}")
            if verbose:
                click.echo(f"           {task['file']}")
        click.echo()
    else:
        click.echo("✅ Задачи с дедлайнами: нет\n")

    # Summary
    total = len(events) + len(tasks)
    click.echo(f"📊 Всего: {len(events)} событий, {len(tasks)} задач (итого: {total})")


def format_date(dt: datetime) -> str:
    """Форматировать дату."""
    return dt.strftime("%Y-%m-%d (%A)")


def format_time(dt: datetime) -> str:
    """Форматировать время."""
    return dt.strftime("%H:%M")


def format_time_range(start: datetime, end: datetime) -> str:
    """Форматировать диапазон времени."""
    return f"{format_time(start)}-{format_time(end)}"


def format_datetime(dt: datetime) -> str:
    """Форматировать дату и время."""
    return dt.strftime("%Y-%m-%d %H:%M")


def main(args: list[str] | None = None) -> int:
    """Главная функция CLI."""
    if args is None:
        args = sys.argv[1:]

    try:
        return cli.main(args=list(args), standalone_mode=False)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 0


if __name__ == "__main__":
    sys.exit(main())
