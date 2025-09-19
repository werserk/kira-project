#!/usr/bin/env python3
"""CLI модуль для работы с календарем"""

import sys
from pathlib import Path
from typing import List, Optional

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import click

from ..adapters.gcal.adapter import GCalAdapter
from ..core.config import load_config
from ..registry import get_adapter_registry

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(
    context_settings=CONTEXT_SETTINGS,
    help="Работа с календарем (синхронизация)",
)
def cli() -> None:
    """Корневая команда календаря."""


@cli.command("pull")
@click.option(
    "--calendar",
    type=str,
    help="Конкретный календарь для синхронизации (по умолчанию: все)",
)
@click.option(
    "--days",
    type=int,
    default=30,
    show_default=True,
    help="Количество дней для синхронизации",
)
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def pull_command(calendar: str | None, days: int, verbose: bool) -> int:
    """Синхронизировать календарь (получить данные)."""

    try:
        config = load_config()

        if verbose:
            click.echo("🔧 Загружена конфигурация")
            click.echo(f"   Vault: {config.get('vault', {}).get('path', 'не указан')}")

        adapter_registry = get_adapter_registry()
        if not adapter_registry.is_adapter_enabled("kira-gcal"):
            click.echo("❌ Адаптер kira-gcal не включен")
            return 1

        if verbose:
            click.echo("✅ Адаптер kira-gcal включен")

        adapter = GCalAdapter(config)
        return handle_pull(adapter, calendar, days, config, verbose)
    except FileNotFoundError as exc:
        click.echo(f"❌ Файл не найден: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - вывод трейсбека ниже
        click.echo(f"❌ Ошибка выполнения calendar команды: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


@cli.command("push")
@click.option(
    "--calendar",
    type=str,
    help="Конкретный календарь для синхронизации (по умолчанию: все)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Показать что будет отправлено без выполнения",
)
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def push_command(calendar: str | None, dry_run: bool, verbose: bool) -> int:
    """Синхронизировать календарь (отправить данные)."""

    try:
        config = load_config()

        if verbose:
            click.echo("🔧 Загружена конфигурация")
            click.echo(f"   Vault: {config.get('vault', {}).get('path', 'не указан')}")

        adapter_registry = get_adapter_registry()
        if not adapter_registry.is_adapter_enabled("kira-gcal"):
            click.echo("❌ Адаптер kira-gcal не включен")
            return 1

        if verbose:
            click.echo("✅ Адаптер kira-gcal включен")

        adapter = GCalAdapter(config)
        return handle_push(adapter, calendar, dry_run, config, verbose)
    except FileNotFoundError as exc:
        click.echo(f"❌ Файл не найден: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - вывод трейсбека ниже
        click.echo(f"❌ Ошибка выполнения calendar команды: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


def handle_pull(
    adapter: GCalAdapter,
    calendar_id: str | None,
    days: int,
    config: dict,
    verbose: bool,
) -> int:
    """Обработка команды pull."""

    click.echo(f"📥 Синхронизация календаря (pull) на {days} дней...")

    if verbose:
        calendars = config.get("adapters", {}).get("gcal", {}).get("calendars", {})
        if calendar_id:
            click.echo(f"   Календарь: {calendar_id}")
        else:
            click.echo(f"   Календари: {list(calendars.keys())}")

    try:
        result = adapter.pull(calendar_id=calendar_id, days=days)

        if verbose:
            click.echo(f"   Получено событий: {result.get('events_count', 0)}")
            click.echo(f"   Обработано: {result.get('processed_count', 0)}")

        click.echo("✅ Синхронизация календаря завершена")
        return 0
    except Exception as exc:  # pragma: no cover - зависит от внешнего API
        click.echo(f"❌ Ошибка синхронизации календаря: {exc}")
        return 1


def handle_push(
    adapter: GCalAdapter,
    calendar_id: str | None,
    dry_run: bool,
    config: dict,
    verbose: bool,
) -> int:
    """Обработка команды push."""

    click.echo("📤 Синхронизация календаря (push)...")

    if verbose:
        calendars = config.get("adapters", {}).get("gcal", {}).get("calendars", {})
        if calendar_id:
            click.echo(f"   Календарь: {calendar_id}")
        else:
            click.echo(f"   Календари: {list(calendars.keys())}")
        click.echo(f"   Режим dry-run: {'да' if dry_run else 'нет'}")

    try:
        result = adapter.push(calendar_id=calendar_id, dry_run=dry_run)

        if verbose:
            click.echo(f"   Отправлено событий: {result.get('events_count', 0)}")
            click.echo(f"   Обработано: {result.get('processed_count', 0)}")

        click.echo("✅ Синхронизация календаря завершена")
        return 0
    except Exception as exc:  # pragma: no cover - зависит от внешнего API
        click.echo(f"❌ Ошибка синхронизации календаря: {exc}")
        return 1


def main(args: Optional[List[str]] = None) -> int:
    if args is None:
        args = sys.argv[1:]

    try:
        return cli.main(args=list(args), standalone_mode=False)
    except SystemExit as exc:  # pragma: no cover - click нормализует код выхода
        return int(exc.code) if exc.code is not None else 0


if __name__ == "__main__":  # pragma: no cover - исполняемый модуль
    sys.exit(main())
