#!/usr/bin/env python3
"""
CLI модуль для создания rollup отчетов
"""
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ..core.config import load_config
from ..pipelines.rollup_pipeline import RollupPipeline
from ..registry import get_plugin_registry


def create_parser() -> argparse.ArgumentParser:
    """Создает парсер аргументов для rollup команды"""
    parser = argparse.ArgumentParser(
        prog="kira rollup",
        description="Создать rollup отчеты (дневные/недельные)"
    )

    subparsers = parser.add_subparsers(
        dest='period',
        help='Период rollup',
        required=True
    )

    # Команда daily
    daily_parser = subparsers.add_parser(
        'daily',
        help='Создать дневной rollup'
    )
    daily_parser.add_argument(
        '--date',
        type=str,
        help='Дата для rollup (YYYY-MM-DD, по умолчанию: вчера)'
    )
    daily_parser.add_argument(
        '--output',
        type=str,
        help='Путь для сохранения отчета'
    )
    daily_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Подробный вывод'
    )

    # Команда weekly
    weekly_parser = subparsers.add_parser(
        'weekly',
        help='Создать недельный rollup'
    )
    weekly_parser.add_argument(
        '--week',
        type=str,
        help='Неделя для rollup (YYYY-WW, по умолчанию: прошлая неделя)'
    )
    weekly_parser.add_argument(
        '--output',
        type=str,
        help='Путь для сохранения отчета'
    )
    weekly_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Подробный вывод'
    )

    return parser


def main(args: Optional[List[str]] = None) -> int:
    """
    Главная функция rollup CLI

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

        # Создаем pipeline
        pipeline = RollupPipeline(config)

        if parsed_args.period == 'daily':
            return handle_daily_rollup(pipeline, parsed_args)
        elif parsed_args.period == 'weekly':
            return handle_weekly_rollup(pipeline, parsed_args)
        else:
            print(f"❌ Неизвестный период: {parsed_args.period}")
            return 1

    except FileNotFoundError as e:
        print(f"❌ Файл не найден: {e}")
        return 1
    except Exception as e:
        print(f"❌ Ошибка выполнения rollup команды: {e}")
        if parsed_args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def handle_daily_rollup(pipeline: RollupPipeline, args) -> int:
    """Обработка дневного rollup"""
    # Определяем дату
    if args.date:
        try:
            target_date = datetime.strptime(args.date, '%Y-%m-%d').date()
        except ValueError:
            print(f"❌ Неверный формат даты: {args.date}. Используйте YYYY-MM-DD")
            return 1
    else:
        target_date = (datetime.now() - timedelta(days=1)).date()

    print(f"📊 Создание дневного rollup за {target_date}...")

    if args.verbose:
        print(f"   Дата: {target_date}")
        if args.output:
            print(f"   Выходной файл: {args.output}")

    try:
        # Создаем rollup
        result = pipeline.create_daily_rollup(
            date=target_date,
            output_path=args.output
        )

        if args.verbose:
            print(f"   Обработано задач: {result.get('tasks_count', 0)}")
            print(f"   Обработано событий: {result.get('events_count', 0)}")
            print(f"   Создано записей: {result.get('entries_count', 0)}")

        print("✅ Дневной rollup создан")
        return 0

    except Exception as e:
        print(f"❌ Ошибка создания дневного rollup: {e}")
        return 1


def handle_weekly_rollup(pipeline: RollupPipeline, args) -> int:
    """Обработка недельного rollup"""
    # Определяем неделю
    if args.week:
        try:
            year, week = args.week.split('-W')
            year = int(year)
            week = int(week)
            # Находим понедельник указанной недели
            jan_4 = datetime(year, 1, 4)
            monday = jan_4 - timedelta(days=jan_4.weekday()) + timedelta(weeks=week-1)
            start_date = monday.date()
        except (ValueError, IndexError):
            print(f"❌ Неверный формат недели: {args.week}. Используйте YYYY-WW")
            return 1
    else:
        # Прошлая неделя
        today = datetime.now().date()
        days_since_monday = today.weekday()
        last_monday = today - timedelta(days=days_since_monday + 7)
        start_date = last_monday

    end_date = start_date + timedelta(days=6)

    print(f"📊 Создание недельного rollup за {start_date} - {end_date}...")

    if args.verbose:
        print(f"   Неделя: {start_date} - {end_date}")
        if args.output:
            print(f"   Выходной файл: {args.output}")

    try:
        # Создаем rollup
        result = pipeline.create_weekly_rollup(
            start_date=start_date,
            end_date=end_date,
            output_path=args.output
        )

        if args.verbose:
            print(f"   Обработано задач: {result.get('tasks_count', 0)}")
            print(f"   Обработано событий: {result.get('events_count', 0)}")
            print(f"   Создано записей: {result.get('entries_count', 0)}")
            print(f"   Статистика по дням: {result.get('daily_stats', {})}")

        print("✅ Недельный rollup создан")
        return 0

    except Exception as e:
        print(f"❌ Ошибка создания недельного rollup: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
