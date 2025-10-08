#!/usr/bin/env python3
"""CLI модуль для персональной статистики и аналитики"""

import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import click
import yaml

from ..core.config import load_config

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.command(
    context_settings=CONTEXT_SETTINGS,
    help="Показать личную статистику и аналитику",
)
@click.option(
    "--period",
    type=click.Choice(["week", "month", "year", "all"]),
    default="week",
    show_default=True,
    help="Период для статистики",
)
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def cli(period: str, verbose: bool) -> int:
    """Показать персональную статистику."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        if not vault_path.exists():
            click.echo(f"❌ Vault не найден: {vault_path}")
            return 1

        # Определить временной диапазон
        now = datetime.now(timezone.utc)
        if period == "week":
            start_date = now - timedelta(days=7)
            period_name = "за последнюю неделю"
        elif period == "month":
            start_date = now - timedelta(days=30)
            period_name = "за последний месяц"
        elif period == "year":
            start_date = now - timedelta(days=365)
            period_name = "за последний год"
        else:  # all
            start_date = datetime.min.replace(tzinfo=timezone.utc)
            period_name = "за всё время"

        # Собрать статистику
        stats = collect_statistics(vault_path, start_date, now)

        # Отобразить статистику
        display_statistics(stats, period_name, verbose)

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


def collect_statistics(vault_path: Path, start_date: datetime, end_date: datetime) -> dict:
    """Собрать статистику по Vault."""
    stats = {
        "tasks": {
            "total": 0,
            "completed": 0,
            "in_progress": 0,
            "todo": 0,
            "blocked": 0,
            "completion_rate": 0.0,
            "by_status": Counter(),
            "by_tag": Counter(),
            "overdue": 0,
        },
        "notes": {
            "total": 0,
            "by_tag": Counter(),
        },
        "events": {
            "total": 0,
            "attended": 0,
        },
        "productivity": {
            "avg_completion_time": None,
            "most_productive_day": None,
            "streak_days": 0,
        },
    }

    # Статистика по задачам
    tasks_dir = vault_path / "tasks"
    if tasks_dir.exists():
        for task_file in tasks_dir.glob("task-*.md"):
            try:
                metadata = load_metadata(task_file)
                
                # Проверить, попадает ли в период
                created = parse_date(metadata.get("created"))
                if not created or created < start_date or created > end_date:
                    continue

                stats["tasks"]["total"] += 1
                status = metadata.get("status", "todo")
                stats["tasks"]["by_status"][status] += 1

                if status == "done":
                    stats["tasks"]["completed"] += 1
                elif status == "doing":
                    stats["tasks"]["in_progress"] += 1
                elif status == "todo":
                    stats["tasks"]["todo"] += 1
                elif status == "blocked":
                    stats["tasks"]["blocked"] += 1

                # Теги
                for tag in metadata.get("tags", []):
                    stats["tasks"]["by_tag"][tag] += 1

                # Просроченные
                due = metadata.get("due")
                if due and status not in ["done"]:
                    due_date = parse_date(due)
                    if due_date and due_date < datetime.now(timezone.utc):
                        stats["tasks"]["overdue"] += 1

            except Exception:
                continue

    # Процент выполнения
    if stats["tasks"]["total"] > 0:
        stats["tasks"]["completion_rate"] = (
            stats["tasks"]["completed"] / stats["tasks"]["total"] * 100
        )

    # Статистика по заметкам
    notes_dir = vault_path / "notes"
    if notes_dir.exists():
        for note_file in notes_dir.glob("note-*.md"):
            try:
                metadata = load_metadata(note_file)
                
                created = parse_date(metadata.get("created"))
                if not created or created < start_date or created > end_date:
                    continue

                stats["notes"]["total"] += 1

                # Теги
                for tag in metadata.get("tags", []):
                    stats["notes"]["by_tag"][tag] += 1

            except Exception:
                continue

    # Статистика по событиям
    events_dir = vault_path / "events"
    if events_dir.exists():
        for event_file in events_dir.glob("event-*.md"):
            try:
                metadata = load_metadata(event_file)
                
                start = parse_date(metadata.get("start"))
                if not start or start < start_date or start > end_date:
                    continue

                stats["events"]["total"] += 1

                # Учитываем только прошедшие события
                if start < datetime.now(timezone.utc):
                    stats["events"]["attended"] += 1

            except Exception:
                continue

    return stats


def display_statistics(stats: dict, period_name: str, verbose: bool) -> None:
    """Отобразить статистику."""
    click.echo(f"\n📊 Персональная статистика {period_name}\n")
    click.echo("=" * 60)

    # Задачи
    task_stats = stats["tasks"]
    click.echo(f"\n📋 Задачи:")
    click.echo(f"  Всего создано: {task_stats['total']}")
    
    if task_stats["total"] > 0:
        click.echo(f"  ✅ Завершено: {task_stats['completed']} ({task_stats['completion_rate']:.1f}%)")
        click.echo(f"  🔄 В работе: {task_stats['in_progress']}")
        click.echo(f"  ⏳ В очереди: {task_stats['todo']}")
        click.echo(f"  🚫 Заблокировано: {task_stats['blocked']}")
        
        if task_stats["overdue"] > 0:
            click.echo(f"  🔴 Просрочено: {task_stats['overdue']}")

        # Топ-5 тегов для задач
        if task_stats["by_tag"] and verbose:
            click.echo(f"\n  📌 Топ-5 тегов:")
            for tag, count in task_stats["by_tag"].most_common(5):
                click.echo(f"     #{tag}: {count}")

    # Заметки
    note_stats = stats["notes"]
    click.echo(f"\n📝 Заметки:")
    click.echo(f"  Всего создано: {note_stats['total']}")

    if note_stats["by_tag"] and verbose:
        click.echo(f"\n  📌 Топ-5 тегов:")
        for tag, count in note_stats["by_tag"].most_common(5):
            click.echo(f"     #{tag}: {count}")

    # События
    event_stats = stats["events"]
    click.echo(f"\n📆 События:")
    click.echo(f"  Всего запланировано: {event_stats['total']}")
    click.echo(f"  Посещено: {event_stats['attended']}")

    # Общая продуктивность
    click.echo(f"\n🎯 Продуктивность:")
    
    total_items = task_stats["total"] + note_stats["total"]
    click.echo(f"  Всего создано: {total_items} элементов")
    
    if task_stats["total"] > 0:
        if task_stats["completion_rate"] >= 80:
            productivity_emoji = "🔥"
            productivity_msg = "Отличная продуктивность!"
        elif task_stats["completion_rate"] >= 60:
            productivity_emoji = "👍"
            productivity_msg = "Хорошая продуктивность"
        elif task_stats["completion_rate"] >= 40:
            productivity_emoji = "📈"
            productivity_msg = "Средняя продуктивность"
        else:
            productivity_emoji = "💪"
            productivity_msg = "Есть куда расти"

        click.echo(f"  {productivity_emoji} {productivity_msg}")

    click.echo("\n" + "=" * 60)


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

