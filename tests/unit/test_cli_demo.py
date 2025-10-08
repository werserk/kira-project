#!/usr/bin/env python3
"""
Тестовый скрипт для демонстрации CLI
"""
import sys
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent / "src"))

from kira.cli.kira_calendar import main as calendar_main
from kira.cli.kira_code import main as code_main
from kira.cli.kira_ext import main as ext_main
from kira.cli.kira_inbox import main as inbox_main
from kira.cli.kira_rollup import main as rollup_main


def test_inbox():
    """Тест inbox команды"""
    print("=== Тест inbox ===")
    return inbox_main(["--verbose"])


def test_calendar():
    """Тест calendar команды"""
    print("\n=== Тест calendar ===")
    print("Calendar pull:")
    result1 = calendar_main(["pull", "--verbose"])
    print("Calendar push:")
    result2 = calendar_main(["push", "--dry-run", "--verbose"])
    return result1 or result2


def test_rollup():
    """Тест rollup команды"""
    print("\n=== Тест rollup ===")
    print("Daily rollup:")
    result1 = rollup_main(["daily", "--verbose"])
    print("Weekly rollup:")
    result2 = rollup_main(["weekly", "--verbose"])
    return result1 or result2


def test_code():
    """Тест code команды"""
    print("\n=== Тест code ===")
    print("Code analyze:")
    result1 = code_main(["analyze", "--verbose"])
    print("Code search:")
    result2 = code_main(["search", "function", "--verbose"])
    return result1 or result2


def test_ext():
    """Тест ext команды"""
    print("\n=== Тест ext ===")
    print("Ext list:")
    result1 = ext_main(["list", "--verbose"])
    print("Ext info:")
    result2 = ext_main(["info", "kira-inbox", "--verbose"])
    return result1 or result2


def main():
    """Главная функция тестирования"""
    print("🚀 Тестирование CLI команд Kira")

    results = []

    # Тестируем все команды
    results.append(test_inbox())
    results.append(test_calendar())
    results.append(test_rollup())
    results.append(test_code())
    results.append(test_ext())

    # Подводим итоги
    print("\n=== Результаты тестирования ===")
    success_count = sum(1 for r in results if r == 0)
    total_count = len(results)

    print(f"Успешно: {success_count}/{total_count}")

    if success_count == total_count:
        print("✅ Все тесты прошли успешно!")
        return 0
    else:
        print("❌ Некоторые тесты завершились с ошибками")
        return 1


if __name__ == "__main__":
    sys.exit(main())
