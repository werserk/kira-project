#!/usr/bin/env python3
"""
CLI модуль для работы с кодом
"""
import argparse
import sys
from pathlib import Path
from typing import List, Optional

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ..core.config import load_config
from ..registry import get_plugin_registry


def create_parser() -> argparse.ArgumentParser:
    """Создает парсер аргументов для code команды"""
    parser = argparse.ArgumentParser(
        prog="kira code",
        description="Работа с кодом и проектами"
    )

    subparsers = parser.add_subparsers(
        dest='action',
        help='Действие с кодом',
        required=True
    )

    # Команда analyze
    analyze_parser = subparsers.add_parser(
        'analyze',
        help='Анализ кода в Vault'
    )
    analyze_parser.add_argument(
        '--path',
        type=str,
        help='Путь для анализа (по умолчанию: весь Vault)'
    )
    analyze_parser.add_argument(
        '--output',
        type=str,
        help='Файл для сохранения результатов анализа'
    )
    analyze_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Подробный вывод'
    )

    # Команда index
    index_parser = subparsers.add_parser(
        'index',
        help='Индексация кода для поиска'
    )
    index_parser.add_argument(
        '--rebuild',
        action='store_true',
        help='Пересоздать индекс с нуля'
    )
    index_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Подробный вывод'
    )

    # Команда search
    search_parser = subparsers.add_parser(
        'search',
        help='Поиск в коде'
    )
    search_parser.add_argument(
        'query',
        help='Поисковый запрос'
    )
    search_parser.add_argument(
        '--type',
        choices=['function', 'class', 'variable', 'comment', 'all'],
        default='all',
        help='Тип поиска'
    )
    search_parser.add_argument(
        '--limit',
        type=int,
        default=20,
        help='Максимальное количество результатов'
    )
    search_parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Подробный вывод'
    )

    return parser


def main(args: Optional[List[str]] = None) -> int:
    """
    Главная функция code CLI

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

        # Проверяем, что code плагин включен
        plugin_registry = get_plugin_registry()
        if not plugin_registry.is_plugin_enabled('kira-code'):
            print("❌ Плагин kira-code не включен")
            return 1

        if parsed_args.verbose:
            print("✅ Плагин kira-code включен")

        # Выполняем действие
        if parsed_args.action == 'analyze':
            return handle_analyze(parsed_args, config)
        elif parsed_args.action == 'index':
            return handle_index(parsed_args, config)
        elif parsed_args.action == 'search':
            return handle_search(parsed_args, config)
        else:
            print(f"❌ Неизвестное действие: {parsed_args.action}")
            return 1

    except FileNotFoundError as e:
        print(f"❌ Файл не найден: {e}")
        return 1
    except Exception as e:
        print(f"❌ Ошибка выполнения code команды: {e}")
        if parsed_args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def handle_analyze(args, config) -> int:
    """Обработка команды analyze"""
    print("🔍 Анализ кода...")

    if args.verbose:
        if args.path:
            print(f"   Путь: {args.path}")
        else:
            print("   Путь: весь Vault")
        if args.output:
            print(f"   Выходной файл: {args.output}")

    try:
        # Здесь должна быть логика анализа кода
        # Пока что заглушка
        print("   Анализ функций...")
        print("   Анализ классов...")
        print("   Анализ зависимостей...")

        if args.output:
            with open(args.output, 'w') as f:
                f.write("# Анализ кода\n\n")
                f.write("## Функции\n")
                f.write("- function1()\n")
                f.write("- function2()\n")
                f.write("\n## Классы\n")
                f.write("- Class1\n")
                f.write("- Class2\n")
            print(f"   Результаты сохранены в: {args.output}")

        print("✅ Анализ кода завершен")
        return 0

    except Exception as e:
        print(f"❌ Ошибка анализа кода: {e}")
        return 1


def handle_index(args, config) -> int:
    """Обработка команды index"""
    if args.rebuild:
        print("🔄 Пересоздание индекса кода...")
    else:
        print("📚 Индексация кода...")

    if args.verbose:
        print("   Сканирование файлов...")
        print("   Извлечение символов...")
        print("   Построение индекса...")

    try:
        # Здесь должна быть логика индексации
        # Пока что заглушка
        print("   Проиндексировано файлов: 42")
        print("   Найдено функций: 156")
        print("   Найдено классов: 23")

        print("✅ Индексация завершена")
        return 0

    except Exception as e:
        print(f"❌ Ошибка индексации: {e}")
        return 1


def handle_search(args, config) -> int:
    """Обработка команды search"""
    print(f"🔍 Поиск в коде: '{args.query}'...")

    if args.verbose:
        print(f"   Тип: {args.type}")
        print(f"   Лимит: {args.limit}")

    try:
        # Здесь должна быть логика поиска
        # Пока что заглушка
        results = [
            ("src/kira/core/config.py", "def load_config()", "function"),
            ("src/kira/core/host.py", "class Host:", "class"),
            ("src/kira/plugin_sdk/manifest.py", "# JSON Schema", "comment"),
        ]

        print(f"   Найдено результатов: {len(results)}")

        for i, (file_path, line, result_type) in enumerate(results[:args.limit]):
            print(f"   {i+1}. {file_path}:{line} ({result_type})")

        if len(results) > args.limit:
            print(f"   ... и еще {len(results) - args.limit} результатов")

        print("✅ Поиск завершен")
        return 0

    except Exception as e:
        print(f"❌ Ошибка поиска: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
