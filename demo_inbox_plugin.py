#!/usr/bin/env python3
"""
Демонстрация плагина Inbox Normalizer
"""
import sys
import tempfile
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent / "src"))

from kira.plugin_sdk.context import PluginContext
from kira.plugins.inbox.src.kira_plugin_inbox.plugin import (
    activate,
    handle_file_dropped,
    handle_message_received,
    normalize_command,
)


def demo_plugin():
    """Демонстрация работы плагина"""
    print("🚀 Демонстрация плагина Inbox Normalizer")
    print("=" * 50)

    # Создаем временную директорию для Vault
    temp_dir = tempfile.mkdtemp()
    print(f"📁 Временный Vault: {temp_dir}")

    try:
        # Создаем контекст плагина
        config = {
            'vault': {
                'path': temp_dir
            }
        }
        context = PluginContext(config)

        # Активируем плагин
        print("\n🔌 Активация плагина...")
        activate(context)
        print("✅ Плагин активирован")

        # Демонстрация 1: Обработка сообщения
        print("\n📨 Демонстрация 1: Обработка сообщения")
        print("-" * 40)

        event_data = {
            'message': '# Важная задача\n\nНужно сделать что-то срочно! #работа #срочно',
            'source': 'telegram'
        }

        print(f"Входящее сообщение: {event_data['message']}")
        handle_message_received(context, event_data)

        # Демонстрация 2: Обработка файла
        print("\n📁 Демонстрация 2: Обработка файла")
        print("-" * 40)

        # Создаем тестовый файл
        inbox_dir = Path(temp_dir) / 'inbox'
        inbox_dir.mkdir(parents=True, exist_ok=True)

        test_file = inbox_dir / 'note.txt'
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("Заметка из файла\n\nЭто важная информация #заметка")

        print(f"Создан файл: {test_file}")

        event_data = {
            'file_path': str(test_file)
        }

        handle_file_dropped(context, event_data)

        # Демонстрация 3: Команда нормализации
        print("\n⚡ Демонстрация 3: Команда нормализации")
        print("-" * 40)

        result = normalize_command(context, ['Встреча', 'завтра', 'в', '15:00', '#встреча'])
        print(f"Результат команды: {result}")

        # Показываем созданные файлы
        print("\n📋 Созданные файлы:")
        print("-" * 40)

        processed_dir = Path(temp_dir) / 'processed'
        if processed_dir.exists():
            files = list(processed_dir.glob('*.md'))
            for i, file_path in enumerate(files, 1):
                print(f"{i}. {file_path.name}")

                # Показываем содержимое файла
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                    print(f"   Заголовок: {lines[0] if lines else 'N/A'}")
                    print(f"   Размер: {len(content)} символов")
                    print()

        print("✅ Демонстрация завершена успешно!")

    except Exception as e:
        print(f"❌ Ошибка демонстрации: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Очищаем временную директорию
        import shutil
        shutil.rmtree(temp_dir)
        print(f"\n🧹 Временная директория очищена")


def demo_validation():
    """Демонстрация валидации манифеста плагина"""
    print("\n🔍 Валидация манифеста плагина")
    print("=" * 50)

    from kira.plugin_sdk.manifest import PluginManifestValidator

    # Загружаем манифест плагина
    manifest_file = Path(__file__).parent / "src" / "kira" / "plugins" / "inbox" / "kira-plugin.json"

    validator = PluginManifestValidator()
    errors = validator.validate_manifest_file(str(manifest_file))

    if errors:
        print("❌ Ошибки валидации:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("✅ Манифест плагина валиден!")

        # Показываем информацию о плагине
        import json
        with open(manifest_file, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        print(f"\n📋 Информация о плагине:")
        print(f"  Название: {manifest['displayName']}")
        print(f"  Версия: {manifest['version']}")
        print(f"  Издатель: {manifest['publisher']}")
        print(f"  Возможности: {', '.join(manifest['capabilities'])}")
        print(f"  События: {', '.join(manifest['contributes']['events'])}")
        print(f"  Команды: {', '.join(manifest['contributes']['commands'])}")


if __name__ == "__main__":
    demo_plugin()
    demo_validation()
