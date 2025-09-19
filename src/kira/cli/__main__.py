#!/usr/bin/env python3
"""
Главный модуль CLI для Kira
Использование: python -m kira.cli <команда> [аргументы]
"""
import argparse
import sys
from pathlib import Path

# Добавляем src в путь для импорта модулей
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from .kira_calendar import main as calendar_main
from .kira_code import main as code_main
from .kira_ext import main as ext_main
from .kira_inbox import main as inbox_main
from .kira_rollup import main as rollup_main


def create_parser():
    """Создает парсер аргументов командной строки"""
    parser = argparse.ArgumentParser(
        prog="kira",
        description="Kira - система управления знаниями и задачами",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
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
        """
    )

    subparsers = parser.add_subparsers(
        dest='command',
        help='Доступные команды',
        required=True
    )

    # Команда inbox
    inbox_parser = subparsers.add_parser(
        'inbox',
        help='Запустить inbox-конвейер'
    )
    inbox_parser.set_defaults(func=inbox_main)

    # Команда calendar
    calendar_parser = subparsers.add_parser(
        'calendar',
        help='Работа с календарем'
    )
    calendar_subparsers = calendar_parser.add_subparsers(
        dest='calendar_action',
        help='Действие с календарем',
        required=True
    )

    calendar_subparsers.add_parser(
        'pull',
        help='Синхронизировать календарь (получить данные)'
    ).set_defaults(func=lambda args: calendar_main(['pull']))

    calendar_subparsers.add_parser(
        'push',
        help='Синхронизировать календарь (отправить данные)'
    ).set_defaults(func=lambda args: calendar_main(['push']))

    # Команда rollup
    rollup_parser = subparsers.add_parser(
        'rollup',
        help='Создать rollup отчеты'
    )
    rollup_subparsers = rollup_parser.add_subparsers(
        dest='rollup_period',
        help='Период rollup',
        required=True
    )

    rollup_subparsers.add_parser(
        'daily',
        help='Создать дневной rollup'
    ).set_defaults(func=lambda args: rollup_main(['daily']))

    rollup_subparsers.add_parser(
        'weekly',
        help='Создать недельный rollup'
    ).set_defaults(func=lambda args: rollup_main(['weekly']))

    # Команда code
    code_parser = subparsers.add_parser(
        'code',
        help='Работа с кодом'
    )
    code_parser.set_defaults(func=code_main)

    # Команда ext (расширения)
    ext_parser = subparsers.add_parser(
        'ext',
        help='Управление расширениями'
    )
    ext_subparsers = ext_parser.add_subparsers(
        dest='ext_action',
        help='Действие с расширениями',
        required=True
    )

    ext_subparsers.add_parser(
        'list',
        help='Показать список расширений'
    ).set_defaults(func=lambda args: ext_main(['list']))

    install_parser = ext_subparsers.add_parser(
        'install',
        help='Установить расширение'
    )
    install_parser.add_argument('name', help='Имя расширения для установки')
    install_parser.set_defaults(func=lambda args: ext_main(['install', args.name]))

    enable_parser = ext_subparsers.add_parser(
        'enable',
        help='Включить расширение'
    )
    enable_parser.add_argument('name', help='Имя расширения для включения')
    enable_parser.set_defaults(func=lambda args: ext_main(['enable', args.name]))

    disable_parser = ext_subparsers.add_parser(
        'disable',
        help='Отключить расширение'
    )
    disable_parser.add_argument('name', help='Имя расширения для отключения')
    disable_parser.set_defaults(func=lambda args: ext_main(['disable', args.name]))

    # Команда validate
    validate_parser = subparsers.add_parser(
        'validate',
        help='Валидация Vault против схем'
    )
    validate_parser.set_defaults(func=validate_vault)

    return parser


def validate_vault(args):
    """Валидация Vault против схем"""
    try:
        from kira.core.config import load_config
        from kira.core.schemas import validate_vault_schemas

        # Загружаем конфигурацию
        config = load_config()
        vault_path = config.get('vault', {}).get('path')

        if not vault_path:
            print("❌ Путь к Vault не указан в конфигурации")
            return 1

        print(f"🔍 Валидация Vault: {vault_path}")

        # Выполняем валидацию
        errors = validate_vault_schemas(vault_path)

        if errors:
            print("❌ Найдены ошибки валидации:")
            for error in errors:
                print(f"  - {error}")
            return 1
        else:
            print("✅ Vault валиден")
            return 0

    except Exception as e:
        print(f"❌ Ошибка валидации: {e}")
        return 1


def main():
    """Главная функция CLI"""
    parser = create_parser()
    args = parser.parse_args()

    try:
        # Выполняем команду
        if hasattr(args, 'func'):
            return args.func(args)
        else:
            parser.print_help()
            return 1

    except KeyboardInterrupt:
        print("\n❌ Операция прервана пользователем")
        return 130
    except Exception as e:
        print(f"❌ Ошибка выполнения команды: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
