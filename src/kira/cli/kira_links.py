#!/usr/bin/env python3
"""CLI модуль для работы со связями между entities"""

import re
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
    help="Управление связями между entities",
)
def cli() -> None:
    """Корневая команда для работы со связями."""


@cli.command("show")
@click.argument("entity_id")
@click.option("--direction", type=click.Choice(["out", "in", "both"]), default="both", help="Направление связей")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def show_command(entity_id: str, direction: str, verbose: bool) -> int:
    """Показать связи entity."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        if not vault_path.exists():
            click.echo(f"❌ Vault не найден: {vault_path}")
            return 1

        # Найти entity
        entity_file = find_entity_file(vault_path, entity_id)
        if not entity_file:
            click.echo(f"❌ Entity не найдена: {entity_id}")
            return 1

        # Загрузить метаданные
        metadata = load_metadata(entity_file)
        title = metadata.get("title", "Untitled")

        click.echo(f"\n🔗 Связи для: {title} ({metadata.get('id')})\n")

        # Исходящие связи (из этой entity)
        if direction in ["out", "both"]:
            outgoing = find_outgoing_links(entity_file)
            if outgoing:
                click.echo(f"📤 Исходящие связи ({len(outgoing)}):")
                for link_id in outgoing:
                    link_file = find_entity_file(vault_path, link_id)
                    if link_file:
                        link_meta = load_metadata(link_file)
                        link_title = link_meta.get("title", "Untitled")
                        click.echo(f"  → {link_title} ({link_id})")
                        if verbose:
                            click.echo(f"     {link_file}")
                    else:
                        click.echo(f"  → {link_id} (не найдено)")
                click.echo()
            else:
                click.echo("📤 Исходящих связей нет\n")

        # Входящие связи (ссылающиеся на эту entity)
        if direction in ["in", "both"]:
            incoming = find_incoming_links(vault_path, metadata.get("id"))
            if incoming:
                click.echo(f"📥 Входящие связи ({len(incoming)}):")
                for link_file in incoming:
                    link_meta = load_metadata(link_file)
                    link_title = link_meta.get("title", "Untitled")
                    link_id = link_meta.get("id", "unknown")
                    click.echo(f"  ← {link_title} ({link_id})")
                    if verbose:
                        click.echo(f"     {link_file}")
                click.echo()
            else:
                click.echo("📥 Входящих связей нет\n")

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


@cli.command("add")
@click.argument("from_id")
@click.argument("to_id")
@click.option("--bidirectional", is_flag=True, help="Создать двунаправленную связь")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def add_command(from_id: str, to_id: str, bidirectional: bool, verbose: bool) -> int:
    """Добавить связь между entities."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        # Найти обе entities
        from_file = find_entity_file(vault_path, from_id)
        to_file = find_entity_file(vault_path, to_id)

        if not from_file:
            click.echo(f"❌ Entity не найдена: {from_id}")
            return 1

        if not to_file:
            click.echo(f"❌ Entity не найдена: {to_id}")
            return 1

        # Загрузить метаданные
        from_meta = load_metadata(from_file)
        to_meta = load_metadata(to_file)

        # Добавить связь
        add_link_to_file(from_file, to_meta.get("id"), to_meta.get("title"))

        click.echo(f"✅ Связь создана: {from_meta.get('title')} → {to_meta.get('title')}")

        if bidirectional:
            add_link_to_file(to_file, from_meta.get("id"), from_meta.get("title"))
            click.echo(f"✅ Обратная связь создана: {to_meta.get('title')} → {from_meta.get('title')}")

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


@cli.command("graph")
@click.argument("entity_id")
@click.option("--depth", type=int, default=2, help="Глубина обхода графа")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def graph_command(entity_id: str, depth: int, verbose: bool) -> int:
    """Показать граф связей entity."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        if not vault_path.exists():
            click.echo(f"❌ Vault не найден: {vault_path}")
            return 1

        # Найти entity
        entity_file = find_entity_file(vault_path, entity_id)
        if not entity_file:
            click.echo(f"❌ Entity не найдена: {entity_id}")
            return 1

        metadata = load_metadata(entity_file)
        
        click.echo(f"\n🕸️  Граф связей для: {metadata.get('title')} (глубина: {depth})\n")

        # Построить граф
        visited = set()
        graph = build_graph(vault_path, metadata.get("id"), depth, visited)

        # Отобразить граф
        display_graph(graph, vault_path, 0, verbose)

        click.echo(f"\n📊 Всего entities в графе: {len(visited)}")

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


@cli.command("orphans")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def orphans_command(verbose: bool) -> int:
    """Найти изолированные entities без связей."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        if not vault_path.exists():
            click.echo(f"❌ Vault не найден: {vault_path}")
            return 1

        orphans = []

        # Проверить все типы entities
        for entity_type in ["tasks", "notes", "events", "projects"]:
            entity_dir = vault_path / entity_type
            if not entity_dir.exists():
                continue

            prefix = entity_type.rstrip("s")
            for entity_file in entity_dir.glob(f"{prefix}-*.md"):
                try:
                    metadata = load_metadata(entity_file)
                    entity_id = metadata.get("id")

                    # Проверить исходящие и входящие связи
                    outgoing = find_outgoing_links(entity_file)
                    incoming = find_incoming_links(vault_path, entity_id)

                    if not outgoing and not incoming:
                        orphans.append((entity_file, metadata))

                except Exception:
                    continue

        if not orphans:
            click.echo("✅ Изолированных entities не найдено")
            return 0

        click.echo(f"⚠️  Найдено изолированных entities: {len(orphans)}\n")

        for entity_file, metadata in orphans:
            title = metadata.get("title", "Untitled")
            entity_id = metadata.get("id", "unknown")
            click.echo(f"  • {title} ({entity_id})")
            if verbose:
                click.echo(f"     {entity_file}")

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


# Helper functions

def find_entity_file(vault_path: Path, entity_id: str) -> Path | None:
    """Найти файл entity по ID."""
    for entity_type in ["tasks", "notes", "events", "projects"]:
        entity_dir = vault_path / entity_type
        if not entity_dir.exists():
            continue

        prefix = entity_type.rstrip("s")
        for entity_file in entity_dir.glob(f"{prefix}-*.md"):
            try:
                metadata = load_metadata(entity_file)
                if metadata.get("id") == entity_id or metadata.get("id", "").startswith(entity_id):
                    return entity_file
            except Exception:
                continue

    return None


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


def find_outgoing_links(file_path: Path) -> list[str]:
    """Найти исходящие связи (wikilinks) в файле."""
    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    # Найти все wikilinks [[entity-id]]
    wikilink_pattern = r'\[\[([a-z]+-\d{8}-\d{4}(?:-[a-z0-9-]+)?)\]\]'
    matches = re.findall(wikilink_pattern, content)

    return list(set(matches))


def find_incoming_links(vault_path: Path, target_id: str) -> list[Path]:
    """Найти файлы, ссылающиеся на данный entity."""
    incoming = []

    for entity_type in ["tasks", "notes", "events", "projects"]:
        entity_dir = vault_path / entity_type
        if not entity_dir.exists():
            continue

        prefix = entity_type.rstrip("s")
        for entity_file in entity_dir.glob(f"{prefix}-*.md"):
            try:
                outgoing = find_outgoing_links(entity_file)
                if target_id in outgoing:
                    incoming.append(entity_file)
            except Exception:
                continue

    return incoming


def add_link_to_file(file_path: Path, target_id: str, target_title: str) -> None:
    """Добавить ссылку в конец файла."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Проверить, есть ли уже эта ссылка
    if f"[[{target_id}]]" in content:
        return

    # Добавить секцию связей если её нет
    if "## Связи" not in content and "## Links" not in content:
        content += f"\n\n## Связи\n\n"

    # Добавить ссылку
    link_text = f"- [[{target_id}]] - {target_title}\n"
    content += link_text

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)


def build_graph(vault_path: Path, entity_id: str, depth: int, visited: set) -> dict:
    """Построить граф связей."""
    if depth == 0 or entity_id in visited:
        return {}

    visited.add(entity_id)

    entity_file = find_entity_file(vault_path, entity_id)
    if not entity_file:
        return {}

    outgoing = find_outgoing_links(entity_file)
    
    graph = {
        "id": entity_id,
        "children": []
    }

    for link_id in outgoing:
        child_graph = build_graph(vault_path, link_id, depth - 1, visited)
        if child_graph:
            graph["children"].append(child_graph)

    return graph


def display_graph(graph: dict, vault_path: Path, level: int, verbose: bool) -> None:
    """Отобразить граф в виде дерева."""
    if not graph:
        return

    indent = "  " * level
    entity_id = graph.get("id")
    
    entity_file = find_entity_file(vault_path, entity_id)
    if entity_file:
        metadata = load_metadata(entity_file)
        title = metadata.get("title", "Untitled")
        click.echo(f"{indent}{'└─ ' if level > 0 else ''}📄 {title} ({entity_id})")
    else:
        click.echo(f"{indent}{'└─ ' if level > 0 else ''}❓ {entity_id} (не найдено)")

    for child in graph.get("children", []):
        display_graph(child, vault_path, level + 1, verbose)


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]

    try:
        return cli.main(args=list(args), standalone_mode=False)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 0


if __name__ == "__main__":
    sys.exit(main())

