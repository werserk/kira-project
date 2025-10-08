#!/usr/bin/env python3
"""CLI модуль для управления расширениями (extensions)"""

import sys
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import click

from ..core.config import load_config
from ..registry import get_adapter_registry, get_plugin_registry

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(
    context_settings=CONTEXT_SETTINGS,
    help="Управление расширениями (плагины и адаптеры)",
)
def cli() -> None:
    """Корневая команда для работы с расширениями."""


@cli.command("list")
@click.option(
    "--type",
    "extension_type",
    type=click.Choice(["plugins", "adapters", "all"]),
    default="all",
    show_default=True,
    help="Тип расширений для показа",
)
@click.option(
    "--status",
    type=click.Choice(["enabled", "disabled", "all"]),
    default="all",
    show_default=True,
    help="Статус расширений для показа",
)
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def list_command(extension_type: str, status: str, verbose: bool) -> int:
    """Показать список расширений."""

    try:
        load_config()
        return handle_list(extension_type, status, verbose)
    except FileNotFoundError as exc:
        click.echo(f"❌ Файл не найден: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - вывод трейсбека ниже
        click.echo(f"❌ Ошибка выполнения ext команды: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


@cli.command("install")
@click.argument("name")
@click.option("--source", type=str, help="Источник установки (git URL, local path)")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def install_command(name: str, source: str | None, verbose: bool) -> int:
    """Установить расширение."""

    try:
        config = load_config()
        return handle_install(name, source, verbose, config)
    except FileNotFoundError as exc:
        click.echo(f"❌ Файл не найден: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - вывод трейсбека ниже
        click.echo(f"❌ Ошибка выполнения ext команды: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


@cli.command("enable")
@click.argument("name")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def enable_command(name: str, verbose: bool) -> int:
    """Включить расширение."""

    try:
        load_config()
        return handle_enable(name, verbose)
    except FileNotFoundError as exc:
        click.echo(f"❌ Файл не найден: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - вывод трейсбека ниже
        click.echo(f"❌ Ошибка выполнения ext команды: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


@cli.command("disable")
@click.argument("name")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def disable_command(name: str, verbose: bool) -> int:
    """Отключить расширение."""

    try:
        load_config()
        return handle_disable(name, verbose)
    except FileNotFoundError as exc:
        click.echo(f"❌ Файл не найден: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - вывод трейсбека ниже
        click.echo(f"❌ Ошибка выполнения ext команды: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


@cli.command("info")
@click.argument("name")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def info_command(name: str, verbose: bool) -> int:
    """Показать информацию о расширении."""

    try:
        load_config()
        return handle_info(name, verbose)
    except FileNotFoundError as exc:
        click.echo(f"❌ Файл не найден: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - вывод трейсбека ниже
        click.echo(f"❌ Ошибка выполнения ext команды: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


def handle_list(extension_type: str, status: str, verbose: bool) -> int:
    """Обработка команды list."""

    click.echo("📋 Список расширений:")

    if extension_type in ["plugins", "all"]:
        click.echo("\n🔌 Плагины:")
        plugin_registry = get_plugin_registry()
        plugins = plugin_registry.get_plugins()

        for plugin in plugins:
            name = plugin.get("name", "unknown")
            enabled = plugin.get("enabled", False)
            path = plugin.get("path", "unknown")

            if status == "all" or (status == "enabled" and enabled) or (status == "disabled" and not enabled):
                status_icon = "✅" if enabled else "❌"
                click.echo(f"   {status_icon} {name}")
                if verbose:
                    click.echo(f"      Путь: {path}")
                    click.echo(f"      Статус: {'включен' if enabled else 'отключен'}")

    if extension_type in ["adapters", "all"]:
        click.echo("\n🔗 Адаптеры:")
        adapter_registry = get_adapter_registry()
        adapters = adapter_registry.get_adapters()

        for adapter in adapters:
            name = adapter.get("name", "unknown")
            enabled = adapter.get("enabled", False)
            path = adapter.get("path", "unknown")

            if status == "all" or (status == "enabled" and enabled) or (status == "disabled" and not enabled):
                status_icon = "✅" if enabled else "❌"
                click.echo(f"   {status_icon} {name}")
                if verbose:
                    click.echo(f"      Путь: {path}")
                    click.echo(f"      Статус: {'включен' if enabled else 'отключен'}")

    return 0


def handle_install(name: str, source: str | None, verbose: bool, config: dict) -> int:
    """Обработка команды install."""

    click.echo(f"⬇️ Установка расширения {name}...")

    if source:
        click.echo(f"   Источник: {source}")

    if verbose:
        click.echo("   Проверка конфигурации завершена")

    click.echo("✅ Расширение установлено (заглушка)")
    return 0


def handle_enable(name: str, verbose: bool) -> int:
    """Обработка команды enable."""

    plugin_registry = get_plugin_registry()
    adapter_registry = get_adapter_registry()

    if plugin_registry.enable_plugin(name):
        click.echo(f"✅ Плагин {name} включен")
        return 0

    if adapter_registry.enable_adapter(name):
        click.echo(f"✅ Адаптер {name} включен")
        return 0

    click.echo(f"❌ Расширение {name} не найдено")
    return 1


def handle_disable(name: str, verbose: bool) -> int:
    """Обработка команды disable."""

    plugin_registry = get_plugin_registry()
    adapter_registry = get_adapter_registry()

    if plugin_registry.disable_plugin(name):
        click.echo(f"✅ Плагин {name} отключен")
        return 0

    if adapter_registry.disable_adapter(name):
        click.echo(f"✅ Адаптер {name} отключен")
        return 0

    click.echo(f"❌ Расширение {name} не найдено")
    return 1


def handle_info(name: str, verbose: bool) -> int:
    """Обработка команды info."""

    plugin_registry = get_plugin_registry()
    adapter_registry = get_adapter_registry()

    plugin = plugin_registry.get_plugin(name)
    adapter = adapter_registry.get_adapter(name)

    if plugin:
        click.echo(f"ℹ️ Информация о плагине {name}:")
        click.echo(f"   Статус: {'включен' if plugin.get('enabled') else 'отключен'}")
        click.echo(f"   Путь: {plugin.get('path', 'unknown')}")
        return 0

    if adapter:
        click.echo(f"ℹ️ Информация об адаптере {name}:")
        click.echo(f"   Статус: {'включен' if adapter.get('enabled') else 'отключен'}")
        click.echo(f"   Путь: {adapter.get('path', 'unknown')}")
        return 0

    click.echo(f"❌ Расширение {name} не найдено")
    return 1


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]

    try:
        return cli.main(args=list(args), standalone_mode=False)
    except SystemExit as exc:  # pragma: no cover - click нормализует код выхода
        return int(exc.code) if exc.code is not None else 0


if __name__ == "__main__":  # pragma: no cover - исполняемый модуль
    sys.exit(main())
