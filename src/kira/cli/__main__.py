#!/usr/bin/env python3
"""Главный модуль CLI для Kira"""

import sys
from pathlib import Path
from typing import Any

# Добавляем src в путь для импорта модулей
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import click

# Core CLI imports (always available)
from .kira_backup import cli as backup_cli
from .kira_calendar import cli as calendar_cli
from .kira_code import cli as code_cli
from .kira_context import cli as context_cli
from .kira_diag import diag_command
from .kira_doctor import doctor as doctor_command
from .kira_ext import cli as ext_cli
from .kira_inbox import cli as inbox_cli
from .kira_links import cli as links_cli
from .kira_migrate import cli as migrate_cli
from .kira_note import cli as note_cli
from .kira_plugin_template import cli as plugin_cli
from .kira_project import cli as project_cli
from .kira_review import cli as review_cli
from .kira_rollup import cli as rollup_cli
from .kira_schedule import cli as schedule_cli
from .kira_search import cli as search_cli
from .kira_stats import cli as stats_cli
from .kira_sync import cli as sync_cli
from .kira_task import cli as task_cli
from .kira_today import cli as today_cli
from .kira_vault import cli as vault_cli

# Optional CLI imports (lazy loaded)
# These require extra dependencies and will be imported only when invoked

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}
EPILOG = """
Примеры использования:
  # Личный ассистент
  kira today                   # Что нужно сделать сегодня
  kira task list               # Список задач
  kira task add "Купить молоко"  # Быстро создать задачу
  kira task start <id>         # Начать работу над задачей
  kira task done <id>          # Завершить задачу
  kira search "отчет"          # Поиск по Vault

  # Работа с данными
  kira inbox                   # Запустить inbox-конвейер
  kira calendar pull           # Синхронизировать календарь (pull)
  kira calendar push           # Синхронизировать календарь (push)
  kira schedule view --today   # Показать расписание на сегодня
  kira schedule conflicts      # Найти конфликты в расписании
  kira rollup daily            # Создать дневной rollup

  # Управление
  kira vault init              # Инициализировать Vault
  kira vault new --type task --title "My Task"  # Создать entity
  kira migrate run --dry-run   # Preview migration changes (Phase 4)
  kira migrate run             # Migrate vault to new schema (Phase 4)
  kira ext list                # Показать список расширений
  kira validate                # Валидация Vault
""".strip()


@click.group(
    context_settings=CONTEXT_SETTINGS,
    help="Kira - система управления знаниями и задачами",
    epilog=EPILOG,
)
def cli() -> None:
    """Корневая команда CLI."""


# Lazy loading wrappers for optional commands
@click.group("agent", help="AI agent commands (requires: poetry install --extras agent)")
def agent_cli_wrapper() -> None:
    """Lazy-loaded agent commands."""


@agent_cli_wrapper.result_callback()
def load_agent_cli(result: Any, **kwargs: Any) -> Any:
    """Load agent CLI when invoked."""
    try:
        from .kira_agent import agent as agent_cli

        # Transfer subcommands from actual CLI
        agent_cli_wrapper.commands = agent_cli.commands
    except ImportError as e:
        click.echo(
            f"❌ Agent commands require additional dependencies.\n"
            f"   Install with: poetry install --extras agent\n"
            f"   Error: {e}",
            err=True,
        )
        sys.exit(1)
    return result


@click.group("telegram", help="Telegram bot commands (requires: poetry install --extras agent)")
def telegram_cli_wrapper() -> None:
    """Lazy-loaded telegram commands."""


@telegram_cli_wrapper.result_callback()
def load_telegram_cli(result: Any, **kwargs: Any) -> Any:
    """Load telegram CLI when invoked."""
    try:
        from .kira_telegram import cli as telegram_cli

        # Transfer subcommands from actual CLI
        telegram_cli_wrapper.commands = telegram_cli.commands
    except ImportError as e:
        click.echo(
            f"❌ Telegram commands require additional dependencies.\n"
            f"   Install with: poetry install --extras agent\n"
            f"   Error: {e}",
            err=True,
        )
        sys.exit(1)
    return result


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
# Core commands (always available)
cli.add_command(today_cli, "today")
cli.add_command(task_cli, "task")
cli.add_command(note_cli, "note")
cli.add_command(project_cli, "project")
cli.add_command(search_cli, "search")
cli.add_command(inbox_cli, "inbox")
cli.add_command(calendar_cli, "calendar")
cli.add_command(schedule_cli, "schedule")
cli.add_command(sync_cli, "sync")
cli.add_command(rollup_cli, "rollup")
cli.add_command(review_cli, "review")
cli.add_command(stats_cli, "stats")
cli.add_command(context_cli, "context")
cli.add_command(links_cli, "links")
cli.add_command(code_cli, "code")
cli.add_command(ext_cli, "ext")
cli.add_command(plugin_cli, "plugin")
cli.add_command(vault_cli, "vault")
cli.add_command(backup_cli, "backup")
cli.add_command(migrate_cli, "migrate")
cli.add_command(diag_command, "diag")
cli.add_command(doctor_command, "doctor")

# Optional commands (lazy loaded)
cli.add_command(agent_cli_wrapper, "agent")
cli.add_command(telegram_cli_wrapper, "telegram")


def main(args: list[str] | None = None) -> int:
    """Главная функция CLI."""

    try:
        normalized_args = list(args) if args is not None else None
        return cli.main(args=normalized_args, standalone_mode=False)
    except SystemExit as exc:  # pragma: no cover - click нормализует код выхода
        return int(exc.code) if exc.code is not None else 0


if __name__ == "__main__":  # pragma: no cover - исполняемый модуль
    sys.exit(main())
