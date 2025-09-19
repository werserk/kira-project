#!/usr/bin/env python3
"""
CLI модуль для работы с inbox-конвейером
"""
import argparse
import sys
from pathlib import Path
from typing import List, Optional

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from ..core.config import load_config
from ..pipelines.inbox_pipeline import InboxPipeline
from ..registry import get_plugin_registry


def create_parser() -> argparse.ArgumentParser:
    """Создает парсер аргументов для inbox команды"""
    parser = argparse.ArgumentParser(
        prog="kira inbox",
        description="Запустить inbox-конвейер для обработки входящих элементов"
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Показать что будет обработано без выполнения'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Подробный вывод'
    )

    parser.add_argument(
        '--config',
        type=str,
        help='Путь к файлу конфигурации (по умолчанию: kira.yaml)'
    )

    return parser


def main(args: Optional[List[str]] = None) -> int:
    """
    Главная функция inbox CLI

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
        config = load_config(parsed_args.config)

        if parsed_args.verbose:
            print("🔧 Загружена конфигурация")
            print(f"   Vault: {config.get('vault', {}).get('path', 'не указан')}")

        # Проверяем, что inbox плагин включен
        plugin_registry = get_plugin_registry()
        if not plugin_registry.is_plugin_enabled('kira-inbox'):
            print("❌ Плагин kira-inbox не включен")
            return 1

        if parsed_args.verbose:
            print("✅ Плагин kira-inbox включен")

        # Создаем и запускаем pipeline
        pipeline = InboxPipeline(config)

        if parsed_args.dry_run:
            print("🔍 Режим dry-run: показываем что будет обработано")
            items = pipeline.scan_inbox_items()
            print(f"   Найдено элементов для обработки: {len(items)}")

            for item in items[:5]:  # Показываем первые 5
                print(f"   - {item}")

            if len(items) > 5:
                print(f"   ... и еще {len(items) - 5} элементов")

            return 0

        # Запускаем обработку
        print("🚀 Запуск inbox-конвейера...")

        if parsed_args.verbose:
            print("   Сканирование inbox...")

        processed_count = pipeline.run()

        print(f"✅ Обработано элементов: {processed_count}")

        if parsed_args.verbose:
            print("   Конвейер завершен успешно")

        return 0

    except FileNotFoundError as e:
        print(f"❌ Файл не найден: {e}")
        return 1
    except Exception as e:
        print(f"❌ Ошибка выполнения inbox-конвейера: {e}")
        if parsed_args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
