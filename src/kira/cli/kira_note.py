#!/usr/bin/env python3
"""CLI модуль для работы с заметками"""

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
    help="Управление заметками",
)
def cli() -> None:
    """Корневая команда для заметок."""


@cli.command("list")
@click.option("--tag", type=str, help="Фильтр по тегу")
@click.option("--limit", type=int, default=50, help="Максимальное количество заметок")
@click.option("--sort", type=click.Choice(["created", "updated", "title"]), default="updated", help="Сортировка")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def list_command(tag: str | None, limit: int, sort: str, verbose: bool) -> int:
    """Показать список заметок."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        if not vault_path.exists():
            click.echo(f"❌ Vault не найден: {vault_path}")
            return 1

        notes_dir = vault_path / "notes"
        if not notes_dir.exists():
            click.echo("📝 Заметок пока нет")
            return 0

        # Загрузить заметки
        notes = load_notes(notes_dir)

        # Применить фильтры
        if tag:
            notes = [n for n in notes if tag in n.get("tags", [])]

        # Сортировка
        if sort == "created":
            notes.sort(key=lambda n: n.get("created", ""), reverse=True)
        elif sort == "updated":
            notes.sort(key=lambda n: n.get("updated", n.get("created", "")), reverse=True)
        elif sort == "title":
            notes.sort(key=lambda n: n.get("title", "").lower())

        if not notes:
            click.echo("📝 Заметки не найдены")
            return 0

        # Ограничить количество
        notes = notes[:limit]

        # Отобразить
        display_note_list(notes, verbose)

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


@cli.command("show")
@click.argument("note_id")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def show_command(note_id: str, verbose: bool) -> int:
    """Показать содержимое заметки."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        note = find_note_by_id(vault_path, note_id)
        if not note:
            click.echo(f"❌ Заметка не найдена: {note_id}")
            return 1

        display_note_details(note, verbose)
        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


@cli.command("add")
@click.argument("title")
@click.option("--tag", multiple=True, help="Теги (можно указать несколько)")
@click.option("--content", type=str, help="Содержимое заметки")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def add_command(title: str, tag: tuple[str, ...], content: str | None, verbose: bool) -> int:
    """Быстро создать заметку."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        if not vault_path.exists():
            click.echo(f"❌ Vault не найден: {vault_path}")
            return 1

        # Создание заметки
        host_api = create_host_api(vault_path)
        
        entity_data = {
            "title": title,
            "created": datetime.now(timezone.utc).isoformat(),
        }

        if tag:
            entity_data["tags"] = list(tag)

        note_content = f"# {title}\n\n"
        if content:
            note_content += f"{content}\n\n"
        else:
            note_content += "<!-- Add your notes here -->\n\n"

        entity = host_api.create_entity("note", entity_data, content=note_content)

        click.echo(f"✅ Заметка создана: {entity.id}")
        if verbose:
            click.echo(f"📁 Файл: {entity.path}")
            if tag:
                click.echo(f"🏷️  Теги: {', '.join(tag)}")

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка создания заметки: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


@cli.command("edit")
@click.argument("note_id")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def edit_command(note_id: str, verbose: bool) -> int:
    """Редактировать заметку в $EDITOR."""
    try:
        import os
        import subprocess

        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        note_path = find_note_path(vault_path, note_id)
        if not note_path:
            click.echo(f"❌ Заметка не найдена: {note_id}")
            return 1

        # Получить редактор
        editor = os.environ.get("EDITOR", "nano")

        if verbose:
            click.echo(f"📝 Открываю {note_path} в {editor}...")

        # Открыть редактор
        subprocess.run([editor, str(note_path)])

        click.echo(f"✅ Редактирование завершено: {note_id}")
        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


@cli.command("tag")
@click.argument("note_id")
@click.argument("tags", nargs=-1, required=True)
@click.option("--remove", is_flag=True, help="Удалить теги вместо добавления")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def tag_command(note_id: str, tags: tuple[str, ...], remove: bool, verbose: bool) -> int:
    """Добавить или удалить теги у заметки."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        note_path = find_note_path(vault_path, note_id)
        if not note_path:
            click.echo(f"❌ Заметка не найдена: {note_id}")
            return 1

        # Загрузить метаданные
        with open(note_path, "r", encoding="utf-8") as f:
            content = f.read()

        parts = content.split("---", 2)
        if len(parts) < 3:
            click.echo("❌ Неверный формат файла заметки")
            return 1

        metadata = yaml.safe_load(parts[1])
        current_tags = set(metadata.get("tags", []))

        # Изменить теги
        if remove:
            current_tags -= set(tags)
            action = "удалены"
        else:
            current_tags |= set(tags)
            action = "добавлены"

        metadata["tags"] = sorted(current_tags)
        metadata["updated"] = datetime.now(timezone.utc).isoformat()

        # Сохранить
        new_content = f"---\n{yaml.dump(metadata, allow_unicode=True, default_flow_style=False)}---{parts[2]}"
        with open(note_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        click.echo(f"✅ Теги {action}: {', '.join(tags)}")
        if verbose:
            click.echo(f"📝 Все теги: {', '.join(metadata['tags'])}")

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


@cli.command("delete")
@click.argument("note_id")
@click.option("--force", is_flag=True, help="Не запрашивать подтверждение")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def delete_command(note_id: str, force: bool, verbose: bool) -> int:
    """Удалить заметку."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        note_path = find_note_path(vault_path, note_id)
        if not note_path:
            click.echo(f"❌ Заметка не найдена: {note_id}")
            return 1

        # Подтверждение
        if not force:
            if not click.confirm(f"Удалить заметку {note_id}?"):
                click.echo("Отменено")
                return 0

        # Удалить файл
        note_path.unlink()

        click.echo(f"✅ Заметка удалена: {note_id}")
        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка удаления: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


# Helper functions

def load_notes(notes_dir: Path) -> list[dict]:
    """Загрузить все заметки."""
    notes = []

    for note_file in notes_dir.glob("note-*.md"):
        try:
            with open(note_file, encoding="utf-8") as f:
                content = f.read()

            if not content.startswith("---"):
                continue

            parts = content.split("---", 2)
            if len(parts) < 3:
                continue

            metadata = yaml.safe_load(parts[1])
            metadata["_path"] = note_file
            metadata["_body"] = parts[2].strip()

            notes.append(metadata)

        except Exception:
            continue

    return notes


def display_note_list(notes: list[dict], verbose: bool) -> None:
    """Отобразить список заметок."""
    click.echo(f"📝 Заметки ({len(notes)}):\n")

    for note in notes:
        title = note.get("title", "Untitled")
        note_id = note.get("id", "unknown")
        tags = note.get("tags", [])
        updated = note.get("updated", note.get("created", ""))

        # Форматировать дату
        if updated:
            try:
                dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d")
            except Exception:
                date_str = updated[:10] if len(updated) >= 10 else ""
        else:
            date_str = ""

        # Теги
        tags_str = ""
        if tags:
            tags_str = " " + " ".join([f"#{t}" for t in tags])

        click.echo(f"  📄 {title} ({date_str}){tags_str}")

        if verbose:
            click.echo(f"      ID: {note_id}")
            click.echo(f"      Файл: {note.get('_path')}")


def display_note_details(note: dict, verbose: bool) -> None:
    """Отобразить подробности заметки."""
    click.echo(f"\n📝 {note.get('title', 'Untitled')}\n")
    click.echo(f"ID: {note.get('id')}")

    if note.get("tags"):
        click.echo(f"Теги: {', '.join(note.get('tags', []))}")

    if note.get("created"):
        click.echo(f"Создано: {note.get('created')}")

    if note.get("updated"):
        click.echo(f"Обновлено: {note.get('updated')}")

    # Контент
    body = note.get("_body", "")
    if body:
        click.echo(f"\n{body}")

    if verbose:
        click.echo(f"\nФайл: {note.get('_path')}")


def find_note_by_id(vault_path: Path, note_id: str) -> dict | None:
    """Найти заметку по ID."""
    notes_dir = vault_path / "notes"
    if not notes_dir.exists():
        return None

    notes = load_notes(notes_dir)
    for note in notes:
        if note.get("id") == note_id or note.get("id", "").startswith(note_id):
            return note

    return None


def find_note_path(vault_path: Path, note_id: str) -> Path | None:
    """Найти путь к файлу заметки."""
    note = find_note_by_id(vault_path, note_id)
    if note:
        return note.get("_path")
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

