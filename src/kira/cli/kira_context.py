#!/usr/bin/env python3
"""CLI модуль для работы с контекстами (GTD)"""

import sys
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import click
import yaml

from ..core.config import load_config

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(
    context_settings=CONTEXT_SETTINGS,
    help="Управление контекстами задач (GTD)",
)
def cli() -> None:
    """Корневая команда для контекстов."""


@cli.command("list")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def list_command(verbose: bool) -> int:
    """Показать все используемые контексты."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        if not vault_path.exists():
            click.echo(f"❌ Vault не найден: {vault_path}")
            return 1

        # Собрать все контексты из задач
        contexts = collect_contexts(vault_path)

        if not contexts:
            click.echo("🏷️  Контекстов пока нет")
            click.echo("\nПодсказка: Контексты добавляются к задачам через теги начинающиеся с @")
            click.echo("Например: @home, @office, @phone, @computer")
            return 0

        click.echo(f"🏷️  Контексты ({len(contexts)}):\n")

        # Отсортировать по количеству задач
        sorted_contexts = sorted(contexts.items(), key=lambda x: x[1], reverse=True)

        for context, count in sorted_contexts:
            click.echo(f"  @{context}: {count} задач(и)")

        if verbose:
            click.echo("\nПримеры использования:")
            click.echo("  kira task list --tag @home")
            click.echo("  kira context show @office")

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


@cli.command("show")
@click.argument("context")
@click.option("--status", type=click.Choice(["todo", "doing", "all"]), default="all", help="Фильтр по статусу")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def show_command(context: str, status: str, verbose: bool) -> int:
    """Показать задачи для контекста."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        if not vault_path.exists():
            click.echo(f"❌ Vault не найден: {vault_path}")
            return 1

        # Нормализовать контекст (убрать @ если есть)
        context_name = context.lstrip("@")

        # Найти задачи с этим контекстом
        tasks = find_tasks_by_context(vault_path, context_name, status)

        if not tasks:
            click.echo(f"📋 Задач для контекста @{context_name} не найдено")
            return 0

        click.echo(f"\n📋 Задачи для контекста @{context_name} ({len(tasks)}):\n")

        # Группировать по статусу
        by_status = {}
        for task in tasks:
            task_status = task.get("status", "todo")
            if task_status not in by_status:
                by_status[task_status] = []
            by_status[task_status].append(task)

        # Отобразить
        status_order = ["doing", "todo", "review", "blocked", "done"]
        status_icons = {
            "todo": "⏳",
            "doing": "🔄",
            "review": "👀",
            "done": "✅",
            "blocked": "🚫",
        }

        for task_status in status_order:
            if task_status in by_status:
                tasks_list = by_status[task_status]
                click.echo(f"{status_icons.get(task_status, '❓')} {task_status.upper()} ({len(tasks_list)}):")
                for task in tasks_list:
                    title = task.get("title", "Untitled")
                    click.echo(f"  • {title}")
                    if verbose:
                        task_id = task.get("id", "unknown")
                        click.echo(f"     ID: {task_id}")
                        due = task.get("due")
                        if due:
                            click.echo(f"     Дедлайн: {due}")
                click.echo()

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


@cli.command("add")
@click.argument("task_id")
@click.argument("context")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def add_command(task_id: str, context: str, verbose: bool) -> int:
    """Добавить контекст к задаче."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        # Найти задачу
        task_path = find_task_path(vault_path, task_id)
        if not task_path:
            click.echo(f"❌ Задача не найдена: {task_id}")
            return 1

        # Нормализовать контекст (добавить @ если нет)
        context_name = context if context.startswith("@") else f"@{context}"

        # Загрузить метаданные
        with open(task_path, "r", encoding="utf-8") as f:
            content = f.read()

        parts = content.split("---", 2)
        if len(parts) < 3:
            click.echo("❌ Неверный формат файла задачи")
            return 1

        metadata = yaml.safe_load(parts[1])
        current_tags = set(metadata.get("tags", []))

        # Добавить контекст
        current_tags.add(context_name)
        
        # Use HostAPI for single writer pattern (Phase 0, Point 2)
        entity_id = metadata.get("id")
        if not entity_id:
            click.echo("❌ Задача не имеет ID")
            return 1
        
        host_api = create_host_api(vault_path)
        host_api.update_entity(entity_id, {"tags": sorted(current_tags)})

        click.echo(f"✅ Контекст {context_name} добавлен к задаче {task_id}")
        
        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


@cli.command("remove")
@click.argument("task_id")
@click.argument("context")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def remove_command(task_id: str, context: str, verbose: bool) -> int:
    """Удалить контекст у задачи."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        # Найти задачу
        task_path = find_task_path(vault_path, task_id)
        if not task_path:
            click.echo(f"❌ Задача не найдена: {task_id}")
            return 1

        # Нормализовать контекст
        context_name = context if context.startswith("@") else f"@{context}"

        # Загрузить метаданные
        with open(task_path, "r", encoding="utf-8") as f:
            content = f.read()

        parts = content.split("---", 2)
        if len(parts) < 3:
            click.echo("❌ Неверный формат файла задачи")
            return 1

        metadata = yaml.safe_load(parts[1])
        current_tags = set(metadata.get("tags", []))

        # Удалить контекст
        if context_name in current_tags:
            current_tags.remove(context_name)
            
            # Use HostAPI for single writer pattern (Phase 0, Point 2)
            entity_id = metadata.get("id")
            if not entity_id:
                click.echo("❌ Задача не имеет ID")
                return 1
            
            host_api = create_host_api(vault_path)
            host_api.update_entity(entity_id, {"tags": sorted(current_tags)})

            click.echo(f"✅ Контекст {context_name} удален у задачи {task_id}")
        else:
            click.echo(f"⚠️  Контекст {context_name} не найден у задачи")

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


# Helper functions

def collect_contexts(vault_path: Path) -> dict[str, int]:
    """Собрать все контексты и их частоту использования."""
    contexts = {}
    tasks_dir = vault_path / "tasks"
    
    if not tasks_dir.exists():
        return contexts

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
            tags = metadata.get("tags", [])

            # Контексты - это теги начинающиеся с @
            for tag in tags:
                if tag.startswith("@"):
                    context_name = tag.lstrip("@")
                    contexts[context_name] = contexts.get(context_name, 0) + 1

        except Exception:
            continue

    return contexts


def find_tasks_by_context(vault_path: Path, context: str, status_filter: str) -> list[dict]:
    """Найти задачи по контексту."""
    tasks = []
    tasks_dir = vault_path / "tasks"
    
    if not tasks_dir.exists():
        return tasks

    context_tag = f"@{context}"

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
            tags = metadata.get("tags", [])
            task_status = metadata.get("status", "todo")

            # Проверить контекст
            if context_tag in tags:
                # Применить фильтр статуса
                if status_filter == "all" or task_status == status_filter:
                    tasks.append(metadata)

        except Exception:
            continue

    # Сортировка: doing первыми
    def sort_key(task):
        status = task.get("status", "todo")
        status_order = {"doing": 0, "todo": 1, "review": 2, "blocked": 3, "done": 4}
        return status_order.get(status, 5)

    tasks.sort(key=sort_key)
    return tasks


def find_task_path(vault_path: Path, task_id: str) -> Path | None:
    """Найти путь к файлу задачи."""
    tasks_dir = vault_path / "tasks"
    if not tasks_dir.exists():
        return None

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
            if metadata.get("id") == task_id or metadata.get("id", "").startswith(task_id):
                return task_file

        except Exception:
            continue

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

