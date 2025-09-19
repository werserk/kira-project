#!/usr/bin/env python3
"""CLI модуль для работы с inbox-конвейером"""

import sys
from pathlib import Path
from typing import List, Optional

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import click

from ..core.config import load_config
from ..pipelines.inbox_pipeline import InboxPipeline
from ..registry import get_plugin_registry

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.command(
    context_settings=CONTEXT_SETTINGS,
    help="Запустить inbox-конвейер для обработки входящих элементов",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Показать что будет обработано без выполнения",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Подробный вывод",
)
@click.option(
    "--config",
    type=str,
    help="Путь к файлу конфигурации (по умолчанию: kira.yaml)",
)
def cli(dry_run: bool, verbose: bool, config: str | None) -> int:
    """Запуск inbox-конвейера."""

    try:
        loaded_config = load_config(config)

        if verbose:
            click.echo("🔧 Загружена конфигурация")
            click.echo(
                f"   Vault: {loaded_config.get('vault', {}).get('path', 'не указан')}"
            )

        plugin_registry = get_plugin_registry()
        if not plugin_registry.is_plugin_enabled("kira-inbox"):
            click.echo("❌ Плагин kira-inbox не включен")
            return 1

        if verbose:
            click.echo("✅ Плагин kira-inbox включен")

        pipeline = InboxPipeline(loaded_config)

        if dry_run:
            click.echo("🔍 Режим dry-run: показываем что будет обработано")
            items = pipeline.scan_inbox_items()
            click.echo(f"   Найдено элементов для обработки: {len(items)}")

            for item in items[:5]:
                click.echo(f"   - {item}")

            if len(items) > 5:
                click.echo(f"   ... и еще {len(items) - 5} элементов")

            return 0

        click.echo("🚀 Запуск inbox-конвейера...")

        if verbose:
            click.echo("   Сканирование inbox...")

        processed_count = pipeline.run()

        click.echo(f"✅ Обработано элементов: {processed_count}")

        if verbose:
            click.echo("   Конвейер завершен успешно")

        return 0
    except FileNotFoundError as exc:
        click.echo(f"❌ Файл не найден: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - защищено проверками ниже
        click.echo(f"❌ Ошибка выполнения inbox-конвейера: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
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
