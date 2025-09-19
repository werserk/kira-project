#!/usr/bin/env python3
"""
CLI модуль для работы с календарем
"""
import argparse
import sys
from pathlib import Path
from typing import List, Optional

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ..adapters.gcal.adapter import GCalAdapter
from ..core.config import load_config
from ..registry import get_adapter_registry


def create_parser() -> argparse.ArgumentParser:
    """Создает парсер аргументов для calendar команды"""
    parser = argparse.ArgumentParser(
        prog="kira calendar",
        description="Работа с календарем (синхронизация)"
    )

    subparsers = parser.add_subparsers(
        dest='action',
        help='Действие с календарем',
        required=True
    )

    # Команда pull
    pull_parser = subparsers.add_parser(
        'pull',
        help='Синхронизировать календарь (получить данные)'
    )
    pull_parser.add_argument(
        '--calendar',
        type=str,
        help='Конкретный календарь для синхронизации (по умолчанию: все)'
    )
    pull_parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Количество дней для синхронизации (по умолчанию: 30)'
    )
    pull_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Подробный вывод'
    )

    # Команда push
    push_parser = subparsers.add_parser(
        'push',
        help='Синхронизировать календарь (отправить данные)'
    )
    push_parser.add_argument(
        '--calendar',
        type=str,
        help='Конкретный календарь для синхронизации (по умолчанию: все)'
    )
    push_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Показать что будет отправлено без выполнения'
    )
    push_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Подробный вывод'
    )

    return parser


def main(args: Optional[List[str]] = None) -> int:
    """
    Главная функция calendar CLI

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
            print(f"   Vault: {config.get('vault', {}).get('path', 'не указан')}")

        # Проверяем, что gcal адаптер включен
        adapter_registry = get_adapter_registry()
        if not adapter_registry.is_adapter_enabled('kira-gcal'):
            print("❌ Адаптер kira-gcal не включен")
            return 1

        if parsed_args.verbose:
            print("✅ Адаптер kira-gcal включен")

        # Создаем адаптер
        adapter = GCalAdapter(config)

        if parsed_args.action == 'pull':
            return handle_pull(adapter, parsed_args, config)
        elif parsed_args.action == 'push':
            return handle_push(adapter, parsed_args, config)
        else:
            print(f"❌ Неизвестное действие: {parsed_args.action}")
            return 1

    except FileNotFoundError as e:
        print(f"❌ Файл не найден: {e}")
        return 1
    except Exception as e:
        print(f"❌ Ошибка выполнения calendar команды: {e}")
        if parsed_args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def handle_pull(adapter: GCalAdapter, args, config) -> int:
    """Обработка команды pull"""
    print(f"📥 Синхронизация календаря (pull) на {args.days} дней...")

    if args.verbose:
        calendars = config.get('adapters', {}).get('gcal', {}).get('calendars', {})
        if args.calendar:
            print(f"   Календарь: {args.calendar}")
        else:
            print(f"   Календари: {list(calendars.keys())}")

    try:
        # Выполняем pull
        result = adapter.pull(
            calendar_id=args.calendar,
            days=args.days
        )

        if args.verbose:
            print(f"   Получено событий: {result.get('events_count', 0)}")
            print(f"   Обработано: {result.get('processed_count', 0)}")

        print("✅ Синхронизация календаря завершена")
        return 0

    except Exception as e:
        print(f"❌ Ошибка синхронизации календаря: {e}")
        return 1


def handle_push(adapter: GCalAdapter, args, config) -> int:
    """Обработка команды push"""
    if args.dry_run:
        print("🔍 Режим dry-run: показываем что будет отправлено")
    else:
        print("📤 Синхронизация календаря (push)...")

    if args.verbose:
        calendars = config.get('adapters', {}).get('gcal', {}).get('calendars', {})
        if args.calendar:
            print(f"   Календарь: {args.calendar}")
        else:
            print(f"   Календари: {list(calendars.keys())}")

    try:
        # Выполняем push
        result = adapter.push(
            calendar_id=args.calendar,
            dry_run=args.dry_run
        )

        if args.verbose:
            print(f"   Найдено событий для отправки: {result.get('events_count', 0)}")
            if not args.dry_run:
                print(f"   Отправлено: {result.get('sent_count', 0)}")

        if args.dry_run:
            print("✅ Dry-run завершен")
        else:
            print("✅ Синхронизация календаря завершена")

        return 0

    except Exception as e:
        print(f"❌ Ошибка синхронизации календаря: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
