#!/usr/bin/env python3
"""CLI модуль для периодических обзоров (review)"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import click
import yaml

from ..core.config import load_config

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(
    context_settings=CONTEXT_SETTINGS,
    help="Периодические обзоры задач и событий",
)
def cli() -> None:
    """Корневая команда для review."""


@cli.command("weekly")
@click.option("--save", type=str, help="Сохранить обзор в файл")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def weekly_command(save: str | None, verbose: bool) -> int:
    """Недельный обзор."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        if not vault_path.exists():
            click.echo(f"❌ Vault не найден: {vault_path}")
            return 1

        # Определить период (последняя неделя)
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)

        click.echo("\n📊 Недельный обзор")
        click.echo(f"Период: {week_ago.strftime('%Y-%m-%d')} - {now.strftime('%Y-%m-%d')}\n")
        click.echo("=" * 60)

        # Собрать данные
        review_data = collect_review_data(vault_path, week_ago, now)

        # Отобразить обзор
        display_weekly_review(review_data, verbose)

        # Сохранить в файл
        if save:
            save_review_to_file(review_data, Path(save), "weekly")
            click.echo(f"\n✅ Обзор сохранен: {save}")

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


@cli.command("monthly")
@click.option("--save", type=str, help="Сохранить обзор в файл")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def monthly_command(save: str | None, verbose: bool) -> int:
    """Месячный обзор."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        if not vault_path.exists():
            click.echo(f"❌ Vault не найден: {vault_path}")
            return 1

        # Определить период (последний месяц)
        now = datetime.now(timezone.utc)
        month_ago = now - timedelta(days=30)

        click.echo("\n📊 Месячный обзор")
        click.echo(f"Период: {month_ago.strftime('%Y-%m-%d')} - {now.strftime('%Y-%m-%d')}\n")
        click.echo("=" * 60)

        # Собрать данные
        review_data = collect_review_data(vault_path, month_ago, now)

        # Отобразить обзор
        display_monthly_review(review_data, verbose)

        # Сохранить в файл
        if save:
            save_review_to_file(review_data, Path(save), "monthly")
            click.echo(f"\n✅ Обзор сохранен: {save}")

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


@cli.command("pending")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def pending_command(verbose: bool) -> int:
    """Обзор задач, требующих внимания."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        if not vault_path.exists():
            click.echo(f"❌ Vault не найден: {vault_path}")
            return 1

        click.echo("\n⚠️  Задачи, требующие внимания\n")
        click.echo("=" * 60)

        tasks_dir = vault_path / "tasks"
        if not tasks_dir.exists():
            click.echo("📋 Задач нет")
            return 0

        now = datetime.now(timezone.utc)

        # Категории задач
        overdue = []
        due_soon = []
        blocked = []
        long_todo = []
        long_doing = []

        for task_file in tasks_dir.glob("task-*.md"):
            try:
                metadata = load_metadata(task_file)
                status = metadata.get("status", "todo")
                created = parse_date(metadata.get("created"))
                due = parse_date(metadata.get("due"))

                # Просроченные
                if due and status not in ["done"] and due < now:
                    overdue.append(metadata)

                # Скоро истекающие (в течение 3 дней)
                elif due and status not in ["done"] and due < now + timedelta(days=3):
                    due_soon.append(metadata)

                # Заблокированные
                if status == "blocked":
                    blocked.append(metadata)

                # Долго в todo (больше 30 дней)
                if status == "todo" and created:
                    days_old = (now - created).days
                    if days_old > 30:
                        long_todo.append((metadata, days_old))

                # Долго в doing (больше 7 дней)
                if status == "doing" and created:
                    days_old = (now - created).days
                    if days_old > 7:
                        long_doing.append((metadata, days_old))

            except Exception:
                continue

        # Отобразить
        total_issues = len(overdue) + len(due_soon) + len(blocked) + len(long_todo) + len(long_doing)

        if total_issues == 0:
            click.echo("✅ Нет задач, требующих внимания")
            return 0

        click.echo(f"📊 Найдено проблем: {total_issues}\n")

        # Просроченные
        if overdue:
            click.echo(f"🔴 Просроченные задачи ({len(overdue)}):")
            for task in overdue:
                title = task.get("title", "Untitled")
                due_date = parse_date(task.get("due"))
                days_overdue = (now - due_date).days if due_date else 0
                click.echo(f"  • {title} (просрочено на {days_overdue} дн.)")
                if verbose:
                    click.echo(f"     ID: {task.get('id')}")
            click.echo()

        # Скоро истекающие
        if due_soon:
            click.echo(f"🟡 Скоро истекают ({len(due_soon)}):")
            for task in due_soon:
                title = task.get("title", "Untitled")
                due_date = parse_date(task.get("due"))
                days_left = (due_date - now).days if due_date else 0
                click.echo(f"  • {title} (через {days_left} дн.)")
                if verbose:
                    click.echo(f"     ID: {task.get('id')}")
            click.echo()

        # Заблокированные
        if blocked:
            click.echo(f"🚫 Заблокированные задачи ({len(blocked)}):")
            for task in blocked:
                title = task.get("title", "Untitled")
                click.echo(f"  • {title}")
                if verbose:
                    click.echo(f"     ID: {task.get('id')}")
            click.echo()

        # Долго в todo
        if long_todo:
            click.echo(f"⏰ Давно в очереди ({len(long_todo)}):")
            for task, days in sorted(long_todo, key=lambda x: x[1], reverse=True)[:10]:
                title = task.get("title", "Untitled")
                click.echo(f"  • {title} ({days} дн. в todo)")
                if verbose:
                    click.echo(f"     ID: {task.get('id')}")
            click.echo()

        # Долго в doing
        if long_doing:
            click.echo(f"🔄 Давно в работе ({len(long_doing)}):")
            for task, days in sorted(long_doing, key=lambda x: x[1], reverse=True):
                title = task.get("title", "Untitled")
                click.echo(f"  • {title} ({days} дн. в doing)")
                if verbose:
                    click.echo(f"     ID: {task.get('id')}")
            click.echo()

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


# Helper functions

def collect_review_data(vault_path: Path, start_date: datetime, end_date: datetime) -> dict:
    """Собрать данные для обзора."""
    data = {
        "period_start": start_date,
        "period_end": end_date,
        "tasks": {
            "created": [],
            "completed": [],
            "in_progress": [],
        },
        "notes": {
            "created": [],
        },
        "events": {
            "attended": [],
        },
    }

    # Задачи
    tasks_dir = vault_path / "tasks"
    if tasks_dir.exists():
        for task_file in tasks_dir.glob("task-*.md"):
            try:
                metadata = load_metadata(task_file)
                created = parse_date(metadata.get("created"))
                
                if created and start_date <= created <= end_date:
                    data["tasks"]["created"].append(metadata)
                
                # Завершенные
                if metadata.get("status") == "done":
                    updated = parse_date(metadata.get("updated"))
                    if updated and start_date <= updated <= end_date:
                        data["tasks"]["completed"].append(metadata)
                
                # В работе
                if metadata.get("status") == "doing":
                    data["tasks"]["in_progress"].append(metadata)

            except Exception:
                continue

    # Заметки
    notes_dir = vault_path / "notes"
    if notes_dir.exists():
        for note_file in notes_dir.glob("note-*.md"):
            try:
                metadata = load_metadata(note_file)
                created = parse_date(metadata.get("created"))
                
                if created and start_date <= created <= end_date:
                    data["notes"]["created"].append(metadata)

            except Exception:
                continue

    # События
    events_dir = vault_path / "events"
    if events_dir.exists():
        for event_file in events_dir.glob("event-*.md"):
            try:
                metadata = load_metadata(event_file)
                start = parse_date(metadata.get("start"))
                
                if start and start_date <= start <= end_date:
                    data["events"]["attended"].append(metadata)

            except Exception:
                continue

    return data


def display_weekly_review(data: dict, verbose: bool) -> None:
    """Отобразить недельный обзор."""
    click.echo(f"\n📋 Задачи:")
    click.echo(f"  Создано: {len(data['tasks']['created'])}")
    click.echo(f"  ✅ Завершено: {len(data['tasks']['completed'])}")
    click.echo(f"  🔄 В работе: {len(data['tasks']['in_progress'])}")

    if data['tasks']['completed'] and verbose:
        click.echo(f"\n  Завершенные задачи:")
        for task in data['tasks']['completed'][:10]:
            click.echo(f"    • {task.get('title', 'Untitled')}")

    click.echo(f"\n📝 Заметки:")
    click.echo(f"  Создано: {len(data['notes']['created'])}")

    click.echo(f"\n📆 События:")
    click.echo(f"  Посещено: {len(data['events']['attended'])}")

    # Completion rate
    created = len(data['tasks']['created'])
    completed = len(data['tasks']['completed'])
    if created > 0:
        rate = (completed / created) * 100
        click.echo(f"\n🎯 Процент завершения: {rate:.1f}%")

    click.echo("\n" + "=" * 60)


def display_monthly_review(data: dict, verbose: bool) -> None:
    """Отобразить месячный обзор."""
    display_weekly_review(data, verbose)  # Same structure for now


def save_review_to_file(data: dict, file_path: Path, review_type: str) -> None:
    """Сохранить обзор в markdown файл."""
    lines = []
    
    lines.append(f"# {review_type.title()} Review")
    lines.append(f"\nПериод: {data['period_start'].strftime('%Y-%m-%d')} - {data['period_end'].strftime('%Y-%m-%d')}\n")
    
    lines.append("## Задачи\n")
    lines.append(f"- Создано: {len(data['tasks']['created'])}")
    lines.append(f"- Завершено: {len(data['tasks']['completed'])}")
    lines.append(f"- В работе: {len(data['tasks']['in_progress'])}\n")
    
    if data['tasks']['completed']:
        lines.append("### Завершенные задачи\n")
        for task in data['tasks']['completed']:
            lines.append(f"- [x] {task.get('title', 'Untitled')}")
        lines.append("")
    
    lines.append("## Заметки\n")
    lines.append(f"- Создано: {len(data['notes']['created'])}\n")
    
    lines.append("## События\n")
    lines.append(f"- Посещено: {len(data['events']['attended'])}\n")
    
    file_path.write_text("\n".join(lines), encoding="utf-8")


def load_metadata(file_path: Path) -> dict:
    """Загрузить метаданные из файла."""
    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    if not content.startswith("---"):
        return {}

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}

    return yaml.safe_load(parts[1]) or {}


def parse_date(date_str: str | None) -> datetime | None:
    """Парсинг даты из строки."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except Exception:
        return None


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]

    try:
        return cli.main(args=list(args), standalone_mode=False)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 0


if __name__ == "__main__":
    sys.exit(main())

