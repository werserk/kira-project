#!/usr/bin/env python3
"""Главный модуль CLI для Kira"""

import sys
from pathlib import Path

# Добавляем src в путь для импорта модулей
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import click

from .kira_calendar import cli as calendar_cli
from .kira_code import cli as code_cli
from .kira_ext import cli as ext_cli
from .kira_inbox import cli as inbox_cli
from .kira_plugin_template import cli as plugin_cli
from .kira_rollup import cli as rollup_cli

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}
EPILOG = """
Примеры использования:
  kira inbox                    # Запустить inbox-конвейер
  kira calendar pull           # Синхронизировать календарь (pull)
  kira calendar push           # Синхронизировать календарь (push)
  kira rollup daily            # Создать дневной rollup
  kira rollup weekly           # Создать недельный rollup
  kira ext list               # Показать список расширений
  kira ext install <name>     # Установить расширение
  kira ext enable <name>      # Включить расширение
  kira ext disable <name>     # Отключить расширение
  kira validate               # Валидация Vault
""".strip()


@click.group(
    context_settings=CONTEXT_SETTINGS,
    help="Kira - система управления знаниями и задачами",
    epilog=EPILOG,
)
def cli() -> None:
    """Корневая команда CLI."""


@cli.command("validate")
def validate_vault() -> int:
    """Валидация Vault против схем."""

    try:
        from ..core.config import load_config
        from ..core.schemas import validate_vault_schemas

        config = load_config()
        vault_path = config.get("vault", {}).get("path")

        if not vault_path:
            click.echo("❌ Путь к Vault не указан в конфигурации")
            return 1

        click.echo(f"🔍 Валидация Vault: {vault_path}")

        errors = validate_vault_schemas(vault_path)

        if errors:
            click.echo("❌ Найдены ошибки валидации:")
            for error in errors:
                click.echo(f"  - {error}")
            return 1

        click.echo("✅ Vault валиден")
        return 0
    except Exception as exc:  # pragma: no cover - вывод трейсбека ниже
        click.echo(f"❌ Ошибка валидации: {exc}")
        return 1


# Подключаем подкоманды
cli.add_command(inbox_cli, "inbox")
cli.add_command(calendar_cli, "calendar")
cli.add_command(rollup_cli, "rollup")
cli.add_command(code_cli, "code")
cli.add_command(ext_cli, "ext")
cli.add_command(plugin_cli, "plugin")


def main(args: list[str] | None = None) -> int:
    """Главная функция CLI."""

    try:
        normalized_args = list(args) if args is not None else None
        return cli.main(args=normalized_args, standalone_mode=False)
    except SystemExit as exc:  # pragma: no cover - click нормализует код выхода
        return int(exc.code) if exc.code is not None else 0


if __name__ == "__main__":  # pragma: no cover - исполняемый модуль
    sys.exit(main())
