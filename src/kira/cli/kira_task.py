#!/usr/bin/env python3
"""CLI модуль для работы с задачами"""

import sys
from datetime import datetime, timezone
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import click
import yaml

from ..core.config import load_config
from ..core.host import create_host_api

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(
    context_settings=CONTEXT_SETTINGS,
    help="Управление задачами",
)
def cli() -> None:
    """Корневая команда для задач."""


@cli.command("list")
@click.option(
    "--status",
    type=click.Choice(["todo", "doing", "review", "done", "blocked", "all"]),
    default="all",
    show_default=True,
    help="Фильтр по статусу",
)
@click.option(
    "--due",
    type=click.Choice(["today", "tomorrow", "week", "overdue", "all"]),
    default="all",
    show_default=True,
    help="Фильтр по дедлайну",
)
@click.option("--tag", type=str, help="Фильтр по тегу")
@click.option("--limit", type=int, default=50, help="Максимальное количество задач")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def list_command(status: str, due: str, tag: str | None, limit: int, verbose: bool) -> int:
    """Показать список задач."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        if not vault_path.exists():
            click.echo(f"❌ Vault не найден: {vault_path}")
            return 1

        tasks_dir = vault_path / "tasks"
        if not tasks_dir.exists():
            click.echo("📋 Задач пока нет")
            return 0

        # Загрузить задачи
        tasks = load_tasks(tasks_dir)

        # Применить фильтры
        filtered_tasks = filter_tasks(tasks, status, due, tag)

        if not filtered_tasks:
            click.echo("📋 Задачи не найдены")
            return 0

        # Ограничить количество
        filtered_tasks = filtered_tasks[:limit]

        # Отобразить
        display_task_list(filtered_tasks, verbose)

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


@cli.command("show")
@click.argument("task_id")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def show_command(task_id: str, verbose: bool) -> int:
    """Показать подробности задачи."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        task = find_task_by_id(vault_path, task_id)
        if not task:
            click.echo(f"❌ Задача не найдена: {task_id}")
            return 1

        display_task_details(task, verbose)
        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


@cli.command("add")
@click.argument("title")
@click.option("--due", type=str, help="Дедлайн (YYYY-MM-DD или 'today', 'tomorrow')")
@click.option("--tag", multiple=True, help="Теги (можно указать несколько)")
@click.option("--priority", type=click.Choice(["low", "medium", "high"]), default="medium")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def add_command(title: str, due: str | None, tag: tuple[str, ...], priority: str, verbose: bool) -> int:
    """Быстро создать задачу."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        if not vault_path.exists():
            click.echo(f"❌ Vault не найден: {vault_path}")
            return 1

        # Парсинг дедлайна
        due_date = None
        if due:
            due_date = parse_due_date(due)

        # Создание задачи
        host_api = create_host_api(vault_path)

        entity_data = {
            "title": title,
            "status": "todo",
            "priority": priority,
            "created": datetime.now(timezone.utc).isoformat(),
        }

        if due_date:
            entity_data["due"] = due_date.isoformat()

        if tag:
            entity_data["tags"] = list(tag)

        entity = host_api.create_entity("task", entity_data, content=f"# {title}\n\n")

        click.echo(f"✅ Задача создана: {entity.id}")
        if verbose:
            click.echo(f"📁 Файл: {entity.path}")
            click.echo(f"📊 Статус: {entity_data['status']}")
            if due_date:
                click.echo(f"📅 Дедлайн: {due_date.strftime('%Y-%m-%d')}")

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка создания задачи: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


@cli.command("start")
@click.argument("task_id")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def start_command(task_id: str, verbose: bool) -> int:
    """Начать работу над задачей (todo → doing)."""
    return change_task_status(task_id, "doing", verbose)


@cli.command("done")
@click.argument("task_id")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def done_command(task_id: str, verbose: bool) -> int:
    """Завершить задачу (→ done)."""
    return change_task_status(task_id, "done", verbose)


@cli.command("block")
@click.argument("task_id")
@click.argument("reason", required=False)
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def block_command(task_id: str, reason: str | None, verbose: bool) -> int:
    """Заблокировать задачу."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        task_path = find_task_path(vault_path, task_id)
        if not task_path:
            click.echo(f"❌ Задача не найдена: {task_id}")
            return 1

        # Обновить статус
        update_task_metadata(task_path, {"status": "blocked"})

        # Добавить причину в контент, если указана
        if reason:
            with open(task_path, "r+", encoding="utf-8") as f:
                content = f.read()
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = parts[1]
                    body = parts[2]

                    # Добавить блок с причиной блокировки
                    block_note = f"\n\n## 🚫 Заблокировано\n\n{reason}\n\n*Заблокировано: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n"
                    new_content = f"---{frontmatter}---{body.rstrip()}{block_note}"

                    f.seek(0)
                    f.write(new_content)
                    f.truncate()

        click.echo(f"🚫 Задача заблокирована: {task_id}")
        if reason and verbose:
            click.echo(f"   Причина: {reason}")

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


@cli.command("delete")
@click.argument("task_id")
@click.option("--force", is_flag=True, help="Не запрашивать подтверждение")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def delete_command(task_id: str, force: bool, verbose: bool) -> int:
    """Удалить задачу."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        task_path = find_task_path(vault_path, task_id)
        if not task_path:
            click.echo(f"❌ Задача не найдена: {task_id}")
            return 1

        # Подтверждение
        if not force:
            if not click.confirm(f"Удалить задачу {task_id}?"):
                click.echo("Отменено")
                return 0

        # Удалить файл
        task_path.unlink()

        click.echo(f"✅ Задача удалена: {task_id}")
        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка удаления: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


@cli.command("edit")
@click.argument("task_id")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def edit_command(task_id: str, verbose: bool) -> int:
    """Редактировать задачу в $EDITOR."""
    try:
        import os
        import subprocess

        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        task_path = find_task_path(vault_path, task_id)
        if not task_path:
            click.echo(f"❌ Задача не найдена: {task_id}")
            return 1

        # Получить редактор
        editor = os.environ.get("EDITOR", "nano")

        if verbose:
            click.echo(f"📝 Открываю {task_path} в {editor}...")

        # Открыть редактор
        subprocess.run([editor, str(task_path)])

        click.echo(f"✅ Редактирование завершено: {task_id}")
        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


@cli.command("archive")
@click.argument("task_id", required=False)
@click.option("--done", is_flag=True, help="Архивировать все завершенные задачи")
@click.option("--older-than", type=int, help="Архивировать задачи старше N дней")
@click.option("--force", is_flag=True, help="Не запрашивать подтверждение")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def archive_command(task_id: str | None, done: bool, older_than: int | None, force: bool, verbose: bool) -> int:
    """Архивировать задачи."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        # Создать директорию архива
        archive_dir = vault_path / ".archive" / "tasks"
        archive_dir.mkdir(parents=True, exist_ok=True)

        if task_id:
            # Архивировать одну задачу
            task_path = find_task_path(vault_path, task_id)
            if not task_path:
                click.echo(f"❌ Задача не найдена: {task_id}")
                return 1

            if not force:
                if not click.confirm(f"Архивировать задачу {task_id}?"):
                    click.echo("Отменено")
                    return 0

            # Переместить в архив
            archive_path = archive_dir / task_path.name
            task_path.rename(archive_path)

            click.echo(f"✅ Задача архивирована: {task_id}")
            if verbose:
                click.echo(f"📁 Архив: {archive_path}")

            return 0

        elif done or older_than:
            # Массовая архивация
            tasks_dir = vault_path / "tasks"
            if not tasks_dir.exists():
                click.echo("📋 Задач нет")
                return 0

            tasks_to_archive = []
            now = datetime.now(timezone.utc)

            for task_file in tasks_dir.glob("task-*.md"):
                try:
                    with open(task_file, encoding="utf-8") as f:
                        content = f.read()

                    parts = content.split("---", 2)
                    if len(parts) < 3:
                        continue

                    metadata = yaml.safe_load(parts[1])

                    # Проверить условия архивации
                    should_archive = False

                    if done and metadata.get("status") == "done":
                        should_archive = True

                    if older_than:
                        updated = metadata.get("updated", metadata.get("created"))
                        if updated:
                            updated_date = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                            days_old = (now - updated_date).days
                            if days_old > older_than and metadata.get("status") == "done":
                                should_archive = True

                    if should_archive:
                        tasks_to_archive.append((task_file, metadata))

                except Exception:
                    continue

            if not tasks_to_archive:
                click.echo("📋 Нет задач для архивации")
                return 0

            click.echo(f"📦 Найдено задач для архивации: {len(tasks_to_archive)}")

            if not force:
                for task_file, metadata in tasks_to_archive[:5]:
                    click.echo(f"  • {metadata.get('title', 'Untitled')} ({metadata.get('id')})")
                if len(tasks_to_archive) > 5:
                    click.echo(f"  ... и еще {len(tasks_to_archive) - 5}")

                if not click.confirm("Архивировать все эти задачи?"):
                    click.echo("Отменено")
                    return 0

            # Архивировать
            archived_count = 0
            for task_file, metadata in tasks_to_archive:
                try:
                    archive_path = archive_dir / task_file.name
                    task_file.rename(archive_path)
                    archived_count += 1
                except Exception as exc:
                    if verbose:
                        click.echo(f"⚠️  Ошибка архивации {task_file.name}: {exc}")

            click.echo(f"✅ Архивировано задач: {archived_count}")
            return 0

        else:
            click.echo("❌ Укажите task_id, --done или --older-than")
            return 1

    except Exception as exc:
        click.echo(f"❌ Ошибка архивации: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


# Helper functions


def load_tasks(tasks_dir: Path) -> list[dict]:
    """Загрузить все задачи."""
    tasks = []

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
            metadata["_path"] = task_file
            metadata["_body"] = parts[2].strip()

            tasks.append(metadata)

        except Exception:
            continue

    # Сортировка: сначала doing, потом todo, потом остальные
    def sort_key(task):
        status = task.get("status", "todo")
        status_order = {"doing": 0, "todo": 1, "review": 2, "blocked": 3, "done": 4}
        return (status_order.get(status, 5), task.get("created", ""))

    tasks.sort(key=sort_key)
    return tasks


def filter_tasks(tasks: list[dict], status: str, due: str, tag: str | None) -> list[dict]:
    """Применить фильтры к задачам."""
    filtered = tasks

    # Фильтр по статусу
    if status != "all":
        filtered = [t for t in filtered if t.get("status") == status]

    # Фильтр по дедлайну
    if due != "all":
        now = datetime.now(timezone.utc)
        today = now.date()

        if due == "today":
            filtered = [t for t in filtered if t.get("due") and parse_date(t["due"]).date() == today]
        elif due == "tomorrow":
            tomorrow = (now.replace(hour=0, minute=0, second=0, microsecond=0)).date()
            from datetime import timedelta

            tomorrow = today + timedelta(days=1)
            filtered = [t for t in filtered if t.get("due") and parse_date(t["due"]).date() == tomorrow]
        elif due == "week":
            from datetime import timedelta

            week_end = today + timedelta(days=7)
            filtered = [t for t in filtered if t.get("due") and today <= parse_date(t["due"]).date() <= week_end]
        elif due == "overdue":
            filtered = [
                t
                for t in filtered
                if t.get("due") and parse_date(t["due"]).date() < today and t.get("status") != "done"
            ]

    # Фильтр по тегу
    if tag:
        filtered = [t for t in filtered if tag in t.get("tags", [])]

    return filtered


def display_task_list(tasks: list[dict], verbose: bool) -> None:
    """Отобразить список задач."""
    click.echo(f"📋 Задачи ({len(tasks)}):\n")

    for task in tasks:
        status = task.get("status", "todo")
        title = task.get("title", "Untitled")
        task_id = task.get("id", "unknown")
        due = task.get("due")
        tags = task.get("tags", [])

        # Иконка статуса
        status_icons = {
            "todo": "⏳",
            "doing": "🔄",
            "review": "👀",
            "done": "✅",
            "blocked": "🚫",
        }
        status_icon = status_icons.get(status, "❓")

        # Формат дедлайна
        due_str = ""
        if due:
            due_date = parse_date(due)
            today = datetime.now(timezone.utc).date()
            days_diff = (due_date.date() - today).days

            if days_diff < 0:
                due_str = click.style(f" 🔴 {due_date.strftime('%Y-%m-%d')}", fg="red", bold=True)
            elif days_diff == 0:
                due_str = click.style(f" 🟡 сегодня", fg="yellow")
            elif days_diff == 1:
                due_str = click.style(f" 🟢 завтра", fg="green")
            else:
                due_str = f" 📅 {due_date.strftime('%Y-%m-%d')}"

        # Теги
        tags_str = ""
        if tags:
            tags_str = " " + " ".join([f"#{t}" for t in tags])

        click.echo(f"  {status_icon} {title}{due_str}{tags_str}")

        if verbose:
            click.echo(f"      ID: {task_id}")
            click.echo(f"      Файл: {task.get('_path')}")


def display_task_details(task: dict, verbose: bool) -> None:
    """Отобразить подробности задачи."""
    click.echo(f"\n📋 {task.get('title', 'Untitled')}\n")
    click.echo(f"ID: {task.get('id')}")
    click.echo(f"Статус: {task.get('status', 'todo')}")

    if task.get("priority"):
        click.echo(f"Приоритет: {task.get('priority')}")

    if task.get("due"):
        click.echo(f"Дедлайн: {task.get('due')}")

    if task.get("tags"):
        click.echo(f"Теги: {', '.join(task.get('tags', []))}")

    if task.get("created"):
        click.echo(f"Создано: {task.get('created')}")

    if task.get("updated"):
        click.echo(f"Обновлено: {task.get('updated')}")

    # Контент
    body = task.get("_body", "")
    if body:
        click.echo(f"\n{body}")

    if verbose:
        click.echo(f"\nФайл: {task.get('_path')}")


def find_task_by_id(vault_path: Path, task_id: str) -> dict | None:
    """Найти задачу по ID."""
    tasks_dir = vault_path / "tasks"
    if not tasks_dir.exists():
        return None

    tasks = load_tasks(tasks_dir)
    for task in tasks:
        if task.get("id") == task_id or task.get("id", "").startswith(task_id):
            return task

    return None


def find_task_path(vault_path: Path, task_id: str) -> Path | None:
    """Найти путь к файлу задачи."""
    task = find_task_by_id(vault_path, task_id)
    if task:
        return task.get("_path")
    return None


def change_task_status(task_id: str, new_status: str, verbose: bool) -> int:
    """Изменить статус задачи."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        task_path = find_task_path(vault_path, task_id)
        if not task_path:
            click.echo(f"❌ Задача не найдена: {task_id}")
            return 1

        # Обновить статус
        update_task_metadata(
            task_path,
            {
                "status": new_status,
                "updated": datetime.now(timezone.utc).isoformat(),
            },
        )

        status_msgs = {
            "doing": "🔄 Задача в работе",
            "done": "✅ Задача завершена",
            "todo": "⏳ Задача в очереди",
            "review": "👀 Задача на проверке",
        }

        click.echo(f"{status_msgs.get(new_status, '✅ Статус обновлен')}: {task_id}")
        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


def update_task_metadata(task_path: Path, updates: dict) -> None:
    """Обновить метаданные задачи (Phase 0, Point 2: Single Writer).

    Uses HostAPI to route all mutations through vault.py.
    No direct file writes allowed.
    """
    # Extract entity ID from file
    from ..core.md_io import read_markdown

    doc = read_markdown(task_path)
    entity_id = doc.get_metadata("id")

    if not entity_id:
        raise ValueError("Task file missing 'id' field")

    # Use HostAPI for single writer pattern (Phase 0, Point 2)
    config = load_config()
    vault_path = Path(config.get("vault", {}).get("path", "vault"))
    host_api = create_host_api(vault_path)

    # Update through single writer
    host_api.update_entity(entity_id, updates)


def parse_date(date_str: str) -> datetime:
    """Парсинг даты из строки."""
    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))


def parse_due_date(due_str: str) -> datetime:
    """Парсинг дедлайна."""
    from datetime import timedelta

    due_str = due_str.lower().strip()
    now = datetime.now(timezone.utc)

    if due_str == "today":
        return now.replace(hour=23, minute=59, second=59, microsecond=0)
    elif due_str == "tomorrow":
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=23, minute=59, second=59, microsecond=0)
    else:
        # Попытаться распарсить как дату
        try:
            return datetime.fromisoformat(due_str).replace(tzinfo=timezone.utc)
        except ValueError:
            # Попробовать формат YYYY-MM-DD
            date_obj = datetime.strptime(due_str, "%Y-%m-%d")
            return date_obj.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]

    try:
        return cli.main(args=list(args), standalone_mode=False)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 0


if __name__ == "__main__":
    sys.exit(main())
