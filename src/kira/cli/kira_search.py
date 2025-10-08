#!/usr/bin/env python3
"""CLI модуль для глобального поиска по Vault"""

import re
import sys
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import click
import yaml

from ..core.config import load_config

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.command(
    context_settings=CONTEXT_SETTINGS,
    help="Поиск по всему Vault",
)
@click.argument("query")
@click.option(
    "--type",
    "entity_type",
    type=click.Choice(["task", "note", "event", "project", "all"]),
    default="all",
    show_default=True,
    help="Тип entities для поиска",
)
@click.option(
    "--tag",
    type=str,
    help="Фильтр по тегу",
)
@click.option(
    "--status",
    type=str,
    help="Фильтр по статусу (для задач)",
)
@click.option(
    "--limit",
    type=int,
    default=20,
    show_default=True,
    help="Максимальное количество результатов",
)
@click.option(
    "--case-sensitive",
    is_flag=True,
    help="Регистрозависимый поиск",
)
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def cli(
    query: str,
    entity_type: str,
    tag: str | None,
    status: str | None,
    limit: int,
    case_sensitive: bool,
    verbose: bool,
) -> int:
    """Поиск по Vault."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        if not vault_path.exists():
            click.echo(f"❌ Vault не найден: {vault_path}")
            return 1

        # Выполнить поиск
        results = search_vault(
            vault_path,
            query,
            entity_type,
            tag,
            status,
            case_sensitive,
        )

        if not results:
            click.echo(f"🔍 Ничего не найдено по запросу: {query}")
            return 0

        # Ограничить результаты
        total_results = len(results)
        results = results[:limit]

        # Вывод результатов
        click.echo(f"🔍 Найдено: {total_results} результатов\n")

        for i, result in enumerate(results, 1):
            display_search_result(result, query, verbose, case_sensitive)
            if i < len(results):
                click.echo()

        if total_results > limit:
            click.echo(f"\n... и еще {total_results - limit} результатов")
            click.echo(f"Используйте --limit {total_results} для показа всех результатов")

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка поиска: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 1


def search_vault(
    vault_path: Path,
    query: str,
    entity_type: str,
    tag: str | None,
    status: str | None,
    case_sensitive: bool,
) -> list[dict]:
    """Выполнить поиск по Vault."""
    results = []

    # Определить типы для поиска
    if entity_type == "all":
        search_types = ["tasks", "notes", "events", "projects"]
    else:
        type_to_folder = {
            "task": "tasks",
            "note": "notes",
            "event": "events",
            "project": "projects",
        }
        search_types = [type_to_folder[entity_type]]

    # Подготовить запрос
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile(re.escape(query), flags)

    # Поиск по каждому типу
    for folder_name in search_types:
        folder_path = vault_path / folder_name
        if not folder_path.exists():
            continue

        # Получить префикс файла
        file_prefix = folder_name.rstrip("s")  # tasks -> task

        for entity_file in folder_path.glob(f"{file_prefix}-*.md"):
            try:
                with open(entity_file, encoding="utf-8") as f:
                    content = f.read()

                if not content.startswith("---"):
                    continue

                parts = content.split("---", 2)
                if len(parts) < 3:
                    continue

                metadata = yaml.safe_load(parts[1])
                body = parts[2]

                # Применить фильтры
                if tag and tag not in metadata.get("tags", []):
                    continue

                if status and metadata.get("status") != status:
                    continue

                # Поиск в заголовке
                title = metadata.get("title", "")
                title_matches = list(pattern.finditer(title))

                # Поиск в теле
                body_matches = list(pattern.finditer(body))

                # Если есть совпадения
                if title_matches or body_matches:
                    result = {
                        "file": entity_file,
                        "type": file_prefix,
                        "metadata": metadata,
                        "title_matches": title_matches,
                        "body_matches": body_matches,
                        "body": body,
                    }
                    results.append(result)

            except Exception:
                continue

    # Сортировка: сначала с совпадениями в заголовке
    def sort_key(r):
        return (
            -len(r["title_matches"]),  # Больше совпадений в заголовке
            -len(r["body_matches"]),   # Больше совпадений в теле
            r["metadata"].get("updated", r["metadata"].get("created", "")),  # Новее
        )

    results.sort(key=sort_key, reverse=True)
    return results


def display_search_result(result: dict, query: str, verbose: bool, case_sensitive: bool) -> None:
    """Отобразить результат поиска."""
    metadata = result["metadata"]
    entity_type = result["type"]
    title = metadata.get("title", "Untitled")
    entity_id = metadata.get("id", "unknown")

    # Иконки типов
    type_icons = {
        "task": "📋",
        "note": "📝",
        "event": "📅",
        "project": "📁",
    }
    type_icon = type_icons.get(entity_type, "📄")

    # Заголовок с подсветкой
    title_highlighted = highlight_text(title, query, case_sensitive)

    click.echo(f"{type_icon} {title_highlighted}")
    click.echo(f"   ID: {entity_id}")

    # Дополнительная информация
    if entity_type == "task":
        status = metadata.get("status", "todo")
        status_icon = {"todo": "⏳", "doing": "🔄", "review": "👀", "done": "✅", "blocked": "🚫"}.get(status, "❓")
        click.echo(f"   Статус: {status_icon} {status}")

        due = metadata.get("due")
        if due:
            click.echo(f"   Дедлайн: {due}")

    elif entity_type == "event":
        start = metadata.get("start")
        if start:
            click.echo(f"   Начало: {start}")

    # Теги
    tags = metadata.get("tags", [])
    if tags:
        click.echo(f"   Теги: {', '.join(f'#{t}' for t in tags)}")

    # Контекст из тела (первое совпадение)
    if result["body_matches"]:
        match = result["body_matches"][0]
        context = extract_context(result["body"], match, query, case_sensitive)
        click.echo(f"   Контекст: {context}")

    if verbose:
        click.echo(f"   Файл: {result['file']}")
        click.echo(f"   Совпадений: {len(result['title_matches'])} в заголовке, {len(result['body_matches'])} в тексте")


def highlight_text(text: str, query: str, case_sensitive: bool) -> str:
    """Подсветить совпадения в тексте."""
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile(f"({re.escape(query)})", flags)

    # Заменить совпадения на подсвеченный текст
    def replace_match(match):
        return click.style(match.group(1), fg="yellow", bold=True)

    return pattern.sub(lambda m: click.style(m.group(1), fg="yellow", bold=True), text)


def extract_context(text: str, match: re.Match, query: str, case_sensitive: bool, context_chars: int = 60) -> str:
    """Извлечь контекст вокруг совпадения."""
    start = max(0, match.start() - context_chars)
    end = min(len(text), match.end() + context_chars)

    context = text[start:end].strip()

    # Очистить от переводов строк
    context = " ".join(context.split())

    # Обрезать по словам
    if start > 0:
        context = "..." + context
    if end < len(text):
        context = context + "..."

    # Подсветить совпадение
    return highlight_text(context, query, case_sensitive)


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]

    try:
        return cli.main(args=list(args), standalone_mode=False)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 0


if __name__ == "__main__":
    sys.exit(main())

