#!/usr/bin/env python3
"""CLI модуль для работы с кодом"""

import sys
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import click

from ..core.config import load_config
from ..registry import get_plugin_registry

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(
    context_settings=CONTEXT_SETTINGS,
    help="Работа с кодом и проектами",
)
def cli() -> None:
    """Корневая команда для code."""


def prepare_environment(verbose: bool) -> tuple[dict | None, int]:
    """Загрузить конфигурацию и убедиться, что плагин включен."""

    config = load_config()

    if verbose:
        click.echo("🔧 Загружена конфигурация")
        click.echo(f"   Vault: {config.get('vault', {}).get('path', 'не указан')}")

    plugin_registry = get_plugin_registry()
    if not plugin_registry.is_plugin_enabled("kira-code"):
        click.echo("❌ Плагин kira-code не включен")
        return None, 1

    if verbose:
        click.echo("✅ Плагин kira-code включен")

    return config, 0


@cli.command("analyze")
@click.option("--path", type=str, help="Путь для анализа (по умолчанию: весь Vault)")
@click.option("--output", type=str, help="Файл для сохранения результатов анализа")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def analyze_command(path: str | None, output: str | None, verbose: bool) -> int:
    """Анализ кода в Vault."""

    try:
        config, exit_code = prepare_environment(verbose)
        if exit_code:
            return exit_code

        assert config is not None
        return handle_analyze(path, output, verbose, config)
    except FileNotFoundError as exc:
        click.echo(f"❌ Файл не найден: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - вывод трейсбека ниже
        click.echo(f"❌ Ошибка выполнения code команды: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


@cli.command("index")
@click.option("--rebuild", is_flag=True, help="Пересоздать индекс с нуля")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def index_command(rebuild: bool, verbose: bool) -> int:
    """Индексация кода для поиска."""

    try:
        config, exit_code = prepare_environment(verbose)
        if exit_code:
            return exit_code

        assert config is not None
        return handle_index(rebuild, verbose, config)
    except FileNotFoundError as exc:
        click.echo(f"❌ Файл не найден: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - вывод трейсбека ниже
        click.echo(f"❌ Ошибка выполнения code команды: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


@cli.command("search")
@click.argument("query")
@click.option(
    "--type",
    "search_type",
    type=click.Choice(["function", "class", "variable", "comment", "all"]),
    default="all",
    show_default=True,
    help="Тип поиска",
)
@click.option(
    "--limit",
    type=int,
    default=20,
    show_default=True,
    help="Максимальное количество результатов",
)
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def search_command(query: str, search_type: str, limit: int, verbose: bool) -> int:
    """Поиск в коде."""

    try:
        config, exit_code = prepare_environment(verbose)
        if exit_code:
            return exit_code

        assert config is not None
        return handle_search(query, search_type, limit, verbose, config)
    except FileNotFoundError as exc:
        click.echo(f"❌ Файл не найден: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - вывод трейсбека ниже
        click.echo(f"❌ Ошибка выполнения code команды: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


def handle_analyze(path: str | None, output: str | None, verbose: bool, _config: dict) -> int:
    """Обработка команды analyze."""

    click.echo("🔍 Анализ кода...")

    if verbose:
        if path:
            click.echo(f"   Путь: {path}")
        else:
            click.echo("   Путь: весь Vault")
        if output:
            click.echo(f"   Результаты будут сохранены в: {output}")

    # Заглушка логики анализа
    click.echo("✅ Анализ завершен")
    return 0


def handle_index(rebuild: bool, verbose: bool, _config: dict) -> int:
    """Обработка команды index."""

    click.echo("🗂️ Индексация кода...")

    if verbose:
        click.echo(f"   Пересоздание индекса: {'да' if rebuild else 'нет'}")

    # Заглушка логики индексации
    click.echo("✅ Индексация завершена")
    return 0


def handle_search(
    query: str,
    search_type: str,
    limit: int,
    verbose: bool,
    _config: dict,
) -> int:
    """Обработка команды search."""

    click.echo(f"🔎 Поиск в коде: {query}")

    if verbose:
        click.echo(f"   Тип поиска: {search_type}")
        click.echo(f"   Лимит результатов: {limit}")

    # Заглушка логики поиска
    results = [
        {
            "path": "src/example.py",
            "line": 42,
            "snippet": "def example_function(): ...",
        }
    ]

    for result in results[:limit]:
        click.echo(f" - {result['path']}:{result['line']} - {result['snippet']}")

    click.echo("✅ Поиск завершен")
    return 0


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]

    try:
        return cli.main(args=list(args), standalone_mode=False)
    except SystemExit as exc:  # pragma: no cover - click нормализует код выхода
        return int(exc.code) if exc.code is not None else 0


if __name__ == "__main__":  # pragma: no cover - исполняемый модуль
    sys.exit(main())
