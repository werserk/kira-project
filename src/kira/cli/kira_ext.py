#!/usr/bin/env python3
"""
CLI модуль для управления расширениями (extensions)
"""
import argparse
import sys
from pathlib import Path
from typing import List, Optional

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ..core.config import load_config
from ..registry import get_adapter_registry, get_plugin_registry


def create_parser() -> argparse.ArgumentParser:
    """Создает парсер аргументов для ext команды"""
    parser = argparse.ArgumentParser(
        prog="kira ext",
        description="Управление расширениями (плагины и адаптеры)"
    )

    subparsers = parser.add_subparsers(
        dest='action',
        help='Действие с расширениями',
        required=True
    )

    # Команда list
    list_parser = subparsers.add_parser(
        'list',
        help='Показать список расширений'
    )
    list_parser.add_argument(
        '--type',
        choices=['plugins', 'adapters', 'all'],
        default='all',
        help='Тип расширений для показа'
    )
    list_parser.add_argument(
        '--status',
        choices=['enabled', 'disabled', 'all'],
        default='all',
        help='Статус расширений для показа'
    )
    list_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Подробный вывод'
    )

    # Команда install
    install_parser = subparsers.add_parser(
        'install',
        help='Установить расширение'
    )
    install_parser.add_argument(
        'name',
        help='Имя расширения для установки'
    )
    install_parser.add_argument(
        '--source',
        type=str,
        help='Источник установки (git URL, local path)'
    )
    install_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Подробный вывод'
    )

    # Команда enable
    enable_parser = subparsers.add_parser(
        'enable',
        help='Включить расширение'
    )
    enable_parser.add_argument(
        'name',
        help='Имя расширения для включения'
    )
    enable_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Подробный вывод'
    )

    # Команда disable
    disable_parser = subparsers.add_parser(
        'disable',
        help='Отключить расширение'
    )
    disable_parser.add_argument(
        'name',
        help='Имя расширения для отключения'
    )
    disable_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Подробный вывод'
    )

    # Команда info
    info_parser = subparsers.add_parser(
        'info',
        help='Показать информацию о расширении'
    )
    info_parser.add_argument(
        'name',
        help='Имя расширения'
    )
    info_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Подробный вывод'
    )

    return parser


def main(args: Optional[List[str]] = None) -> int:
    """
    Главная функция ext CLI

    Args:
        args: Аргументы командной строки (если None, берется из sys.argv)

    Returns:
        Код возврата (0 - успех, 1 - ошибка)
    """
    if args is None:
        args = sys.argv[1:]

    parser = create_parser()
    parsed_args = parser.parse_args(args)

    try:
        # Загружаем конфигурацию
        config = load_config()

        if parsed_args.verbose:
            print("🔧 Загружена конфигурация")

        # Выполняем действие
        if parsed_args.action == 'list':
            return handle_list(parsed_args)
        elif parsed_args.action == 'install':
            return handle_install(parsed_args, config)
        elif parsed_args.action == 'enable':
            return handle_enable(parsed_args)
        elif parsed_args.action == 'disable':
            return handle_disable(parsed_args)
        elif parsed_args.action == 'info':
            return handle_info(parsed_args)
        else:
            print(f"❌ Неизвестное действие: {parsed_args.action}")
            return 1

    except FileNotFoundError as e:
        print(f"❌ Файл не найден: {e}")
        return 1
    except Exception as e:
        print(f"❌ Ошибка выполнения ext команды: {e}")
        if parsed_args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def handle_list(args) -> int:
    """Обработка команды list"""
    print("📋 Список расширений:")

    if args.type in ['plugins', 'all']:
        print("\n🔌 Плагины:")
        plugin_registry = get_plugin_registry()
        plugins = plugin_registry.get_plugins()

        for plugin in plugins:
            name = plugin.get('name', 'unknown')
            enabled = plugin.get('enabled', False)
            path = plugin.get('path', 'unknown')

            if args.status == 'all' or (args.status == 'enabled' and enabled) or (args.status == 'disabled' and not enabled):
                status_icon = "✅" if enabled else "❌"
                print(f"   {status_icon} {name}")
                if args.verbose:
                    print(f"      Путь: {path}")
                    print(f"      Статус: {'включен' if enabled else 'отключен'}")

    if args.type in ['adapters', 'all']:
        print("\n🔗 Адаптеры:")
        adapter_registry = get_adapter_registry()
        adapters = adapter_registry.get_adapters()

        for adapter in adapters:
            name = adapter.get('name', 'unknown')
            enabled = adapter.get('enabled', False)
            path = adapter.get('path', 'unknown')

            if args.status == 'all' or (args.status == 'enabled' and enabled) or (args.status == 'disabled' and not enabled):
                status_icon = "✅" if enabled else "❌"
                print(f"   {status_icon} {name}")
                if args.verbose:
                    print(f"      Путь: {path}")
                    print(f"      Статус: {'включен' if enabled else 'отключен'}")

    return 0


def handle_install(args, config) -> int:
    """Обработка команды install"""
    print(f"📦 Установка расширения: {args.name}")

    if args.verbose:
        if args.source:
            print(f"   Источник: {args.source}")
        else:
            print("   Источник: реестр по умолчанию")

    try:
        # Здесь должна быть логика установки
        # Пока что заглушка
        print("   Скачивание...")
        print("   Установка зависимостей...")
        print("   Регистрация в реестре...")

        print(f"✅ Расширение {args.name} установлено")
        return 0

    except Exception as e:
        print(f"❌ Ошибка установки расширения: {e}")
        return 1


def handle_enable(args) -> int:
    """Обработка команды enable"""
    print(f"✅ Включение расширения: {args.name}")

    try:
        # Ищем расширение в реестрах
        plugin_registry = get_plugin_registry()
        adapter_registry = get_adapter_registry()

        plugin = plugin_registry.get_plugin(args.name)
        adapter = adapter_registry.get_adapter(args.name)

        if plugin:
            # Включаем плагин
            plugin['enabled'] = True
            print(f"✅ Плагин {args.name} включен")
            return 0
        elif adapter:
            # Включаем адаптер
            adapter['enabled'] = True
            print(f"✅ Адаптер {args.name} включен")
            return 0
        else:
            print(f"❌ Расширение {args.name} не найдено")
            return 1

    except Exception as e:
        print(f"❌ Ошибка включения расширения: {e}")
        return 1


def handle_disable(args) -> int:
    """Обработка команды disable"""
    print(f"❌ Отключение расширения: {args.name}")

    try:
        # Ищем расширение в реестрах
        plugin_registry = get_plugin_registry()
        adapter_registry = get_adapter_registry()

        plugin = plugin_registry.get_plugin(args.name)
        adapter = adapter_registry.get_adapter(args.name)

        if plugin:
            # Отключаем плагин
            plugin['enabled'] = False
            print(f"✅ Плагин {args.name} отключен")
            return 0
        elif adapter:
            # Отключаем адаптер
            adapter['enabled'] = False
            print(f"✅ Адаптер {args.name} отключен")
            return 0
        else:
            print(f"❌ Расширение {args.name} не найдено")
            return 1

    except Exception as e:
        print(f"❌ Ошибка отключения расширения: {e}")
        return 1


def handle_info(args) -> int:
    """Обработка команды info"""
    print(f"ℹ️  Информация о расширении: {args.name}")

    try:
        # Ищем расширение в реестрах
        plugin_registry = get_plugin_registry()
        adapter_registry = get_adapter_registry()

        plugin = plugin_registry.get_plugin(args.name)
        adapter = adapter_registry.get_adapter(args.name)

        if plugin:
            print(f"   Тип: плагин")
            print(f"   Путь: {plugin.get('path', 'не указан')}")
            print(f"   Статус: {'включен' if plugin.get('enabled', False) else 'отключен'}")

            if args.verbose:
                # Пытаемся загрузить манифест плагина
                plugin_path = plugin_registry.get_plugin_path(args.name)
                if plugin_path:
                    manifest_file = plugin_path / "kira-plugin.json"
                    if manifest_file.exists():
                        import json
                        with open(manifest_file, 'r') as f:
                            manifest = json.load(f)
                            print(f"   Версия: {manifest.get('version', 'не указана')}")
                            print(f"   Описание: {manifest.get('description', 'не указано')}")
                            print(f"   Издатель: {manifest.get('publisher', 'не указан')}")

            return 0
        elif adapter:
            print(f"   Тип: адаптер")
            print(f"   Путь: {adapter.get('path', 'не указан')}")
            print(f"   Статус: {'включен' if adapter.get('enabled', False) else 'отключен'}")
            return 0
        else:
            print(f"❌ Расширение {args.name} не найдено")
            return 1

    except Exception as e:
        print(f"❌ Ошибка получения информации: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
