#!/usr/bin/env python3
"""CLI модуль для работы с проектами"""

import sys
from datetime import UTC, datetime
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
    help="Управление проектами",
)
def cli() -> None:
    """Корневая команда для проектов."""


@cli.command("list")
@click.option(
    "--status",
    type=click.Choice(["active", "completed", "archived", "all"]),
    default="active",
    help="Фильтр по статусу",
)
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def list_command(status: str, verbose: bool) -> int:
    """Показать список проектов."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        if not vault_path.exists():
            click.echo(f"❌ Vault не найден: {vault_path}")
            return 1

        projects_dir = vault_path / "projects"
        if not projects_dir.exists():
            click.echo("📁 Проектов пока нет")
            return 0

        # Загрузить проекты
        projects = load_projects(projects_dir)

        # Применить фильтры
        if status != "all":
            projects = [p for p in projects if p.get("status") == status]

        if not projects:
            click.echo("📁 Проекты не найдены")
            return 0

        # Отобразить
        display_project_list(projects, verbose)

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


@cli.command("show")
@click.argument("project_id")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def show_command(project_id: str, verbose: bool) -> int:
    """Показать детали проекта."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        project = find_project_by_id(vault_path, project_id)
        if not project:
            click.echo(f"❌ Проект не найден: {project_id}")
            return 1

        display_project_details(project, vault_path, verbose)
        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


@cli.command("add")
@click.argument("title")
@click.option("--description", type=str, help="Описание проекта")
@click.option("--tag", multiple=True, help="Теги (можно указать несколько)")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def add_command(title: str, description: str | None, tag: tuple[str, ...], verbose: bool) -> int:
    """Создать новый проект."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        if not vault_path.exists():
            click.echo(f"❌ Vault не найден: {vault_path}")
            return 1

        # Создание проекта
        host_api = create_host_api(vault_path)

        entity_data = {
            "title": title,
            "status": "active",
            "created": datetime.now(UTC).isoformat(),
        }

        if tag:
            entity_data["tags"] = list(tag)

        project_content = f"# {title}\n\n"
        if description:
            project_content += f"{description}\n\n"
        else:
            project_content += "## Описание\n\n<!-- Опишите проект -->\n\n"

        project_content += "## Задачи\n\n<!-- Связанные задачи появятся здесь -->\n\n"
        project_content += "## Заметки\n\n<!-- Заметки по проекту -->\n\n"

        entity = host_api.create_entity("project", entity_data, content=project_content)

        click.echo(f"✅ Проект создан: {entity.id}")
        if verbose:
            click.echo(f"📁 Файл: {entity.path}")
            if tag:
                click.echo(f"🏷️  Теги: {', '.join(tag)}")

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка создания проекта: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


@cli.command("tasks")
@click.argument("project_id")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def tasks_command(project_id: str, verbose: bool) -> int:
    """Показать задачи проекта."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        project = find_project_by_id(vault_path, project_id)
        if not project:
            click.echo(f"❌ Проект не найден: {project_id}")
            return 1

        # Найти задачи, связанные с проектом
        tasks = find_project_tasks(vault_path, project.get("id"))

        if not tasks:
            click.echo("📋 Задач для проекта нет")
            return 0

        click.echo(f"\n📋 Задачи проекта: {project.get('title')} ({len(tasks)})\n")

        # Группировать по статусу
        by_status = {}
        for task in tasks:
            status = task.get("status", "todo")
            if status not in by_status:
                by_status[status] = []
            by_status[status].append(task)

        # Отобразить по группам
        status_order = ["doing", "todo", "review", "blocked", "done"]
        status_icons = {
            "todo": "⏳",
            "doing": "🔄",
            "review": "👀",
            "done": "✅",
            "blocked": "🚫",
        }

        for status in status_order:
            if status in by_status:
                tasks_list = by_status[status]
                click.echo(f"{status_icons.get(status, '❓')} {status.upper()} ({len(tasks_list)}):")
                for task in tasks_list:
                    title = task.get("title", "Untitled")
                    click.echo(f"  • {title}")
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


@cli.command("progress")
@click.argument("project_id")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def progress_command(project_id: str, verbose: bool) -> int:
    """Показать прогресс проекта."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        project = find_project_by_id(vault_path, project_id)
        if not project:
            click.echo(f"❌ Проект не найден: {project_id}")
            return 1

        # Найти задачи проекта
        tasks = find_project_tasks(vault_path, project.get("id"))

        click.echo(f"\n📊 Прогресс проекта: {project.get('title')}\n")

        if not tasks:
            click.echo("📋 Задач нет")
            return 0

        # Статистика
        total = len(tasks)
        completed = len([t for t in tasks if t.get("status") == "done"])
        in_progress = len([t for t in tasks if t.get("status") == "doing"])
        blocked = len([t for t in tasks if t.get("status") == "blocked"])

        # Процент выполнения
        completion_rate = (completed / total * 100) if total > 0 else 0

        click.echo(f"Всего задач: {total}")
        click.echo(f"✅ Завершено: {completed} ({completion_rate:.1f}%)")
        click.echo(f"🔄 В работе: {in_progress}")
        click.echo(f"🚫 Заблокировано: {blocked}")
        click.echo(f"⏳ Осталось: {total - completed}")

        # Прогресс-бар
        bar_length = 30
        filled = int(bar_length * completion_rate / 100)
        bar = "█" * filled + "░" * (bar_length - filled)
        click.echo(f"\n[{bar}] {completion_rate:.1f}%")

        # Оценка статуса
        if completion_rate == 100:
            click.echo("\n🎉 Проект завершен!")
        elif blocked > 0:
            click.echo(f"\n⚠️  Есть заблокированные задачи ({blocked})")
        elif in_progress > 0:
            click.echo("\n🚀 Проект в активной разработке")
        elif completion_rate > 0:
            click.echo("\n📈 Проект начат")
        else:
            click.echo("\n💡 Проект в планировании")

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


@cli.command("complete")
@click.argument("project_id")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def complete_command(project_id: str, verbose: bool) -> int:
    """Завершить проект."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        project_path = find_project_path(vault_path, project_id)
        if not project_path:
            click.echo(f"❌ Проект не найден: {project_id}")
            return 1

        # Обновить статус
        update_project_metadata(
            project_path,
            {
                "status": "completed",
                "completed": datetime.now(UTC).isoformat(),
            },
        )

        click.echo(f"✅ Проект завершен: {project_id}")
        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


# Helper functions


def load_projects(projects_dir: Path) -> list[dict]:
    """Загрузить все проекты."""
    projects = []

    for project_file in projects_dir.glob("project-*.md"):
        try:
            with open(project_file, encoding="utf-8") as f:
                content = f.read()

            if not content.startswith("---"):
                continue

            parts = content.split("---", 2)
            if len(parts) < 3:
                continue

            metadata = yaml.safe_load(parts[1])
            metadata["_path"] = project_file
            metadata["_body"] = parts[2].strip()

            projects.append(metadata)

        except Exception:
            continue

    # Сортировка: active первыми
    def sort_key(project):
        status = project.get("status", "active")
        status_order = {"active": 0, "completed": 1, "archived": 2}
        return (status_order.get(status, 3), project.get("created", ""))

    projects.sort(key=sort_key)
    return projects


def display_project_list(projects: list[dict], verbose: bool) -> None:
    """Отобразить список проектов."""
    click.echo(f"📁 Проекты ({len(projects)}):\n")

    for project in projects:
        title = project.get("title", "Untitled")
        project_id = project.get("id", "unknown")
        status = project.get("status", "active")
        tags = project.get("tags", [])

        # Иконка статуса
        status_icons = {
            "active": "🚀",
            "completed": "✅",
            "archived": "📦",
        }
        status_icon = status_icons.get(status, "❓")

        # Теги
        tags_str = ""
        if tags:
            tags_str = " " + " ".join([f"#{t}" for t in tags])

        click.echo(f"  {status_icon} {title}{tags_str}")

        if verbose:
            click.echo(f"      ID: {project_id}")
            click.echo(f"      Статус: {status}")
            click.echo(f"      Файл: {project.get('_path')}")


def display_project_details(project: dict, vault_path: Path, verbose: bool) -> None:
    """Отобразить детали проекта."""
    click.echo(f"\n📁 {project.get('title', 'Untitled')}\n")
    click.echo(f"ID: {project.get('id')}")
    click.echo(f"Статус: {project.get('status', 'active')}")

    if project.get("tags"):
        click.echo(f"Теги: {', '.join(project.get('tags', []))}")

    if project.get("created"):
        click.echo(f"Создан: {project.get('created')}")

    if project.get("completed"):
        click.echo(f"Завершен: {project.get('completed')}")

    # Статистика по задачам
    tasks = find_project_tasks(vault_path, project.get("id"))
    if tasks:
        total = len(tasks)
        completed = len([t for t in tasks if t.get("status") == "done"])
        click.echo(f"\nЗадачи: {completed}/{total} завершено")

    # Контент
    body = project.get("_body", "")
    if body:
        click.echo(f"\n{body}")

    if verbose:
        click.echo(f"\nФайл: {project.get('_path')}")


def find_project_by_id(vault_path: Path, project_id: str) -> dict | None:
    """Найти проект по ID."""
    projects_dir = vault_path / "projects"
    if not projects_dir.exists():
        return None

    projects = load_projects(projects_dir)
    for project in projects:
        if project.get("id") == project_id or project.get("id", "").startswith(project_id):
            return project

    return None


def find_project_path(vault_path: Path, project_id: str) -> Path | None:
    """Найти путь к файлу проекта."""
    project = find_project_by_id(vault_path, project_id)
    if project:
        return project.get("_path")
    return None


def find_project_tasks(vault_path: Path, project_id: str) -> list[dict]:
    """Найти задачи, связанные с проектом."""
    tasks = []
    tasks_dir = vault_path / "tasks"

    if not tasks_dir.exists():
        return tasks

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

            # Проверить, связана ли задача с проектом
            # Через поле project_id или через wikilink
            if metadata.get("project") == project_id or f"[[{project_id}]]" in content:
                tasks.append(metadata)

        except Exception:
            continue

    return tasks


def update_project_metadata(project_path: Path, updates: dict) -> None:
    """Обновить метаданные проекта (Phase 0, Point 2: Single Writer).

    Uses HostAPI to route all mutations through vault.py.
    No direct file writes allowed.
    """
    # Extract entity ID from file
    from ..core.config import load_config
    from ..core.host import create_host_api
    from ..core.md_io import read_markdown

    doc = read_markdown(project_path)
    entity_id = doc.get_metadata("id")

    if not entity_id:
        raise ValueError("Project file missing 'id' field")

    # Use HostAPI for single writer pattern (Phase 0, Point 2)
    config = load_config()
    vault_path = Path(config.get("vault", {}).get("path", "vault"))
    host_api = create_host_api(vault_path)

    # Update through single writer
    host_api.update_entity(entity_id, updates)


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]

    try:
        return cli.main(args=list(args), standalone_mode=False)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 0


if __name__ == "__main__":
    sys.exit(main())
