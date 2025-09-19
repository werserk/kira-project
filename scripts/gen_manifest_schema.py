#!/usr/bin/env python3
"""
Генерация JSON Schema для манифеста плагина из Python кода
"""
import json
import sys
from pathlib import Path

# Добавляем src в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from kira.plugin_sdk.manifest import get_manifest_schema


def main():
    """Генерирует JSON Schema файл"""
    schema = get_manifest_schema()

    # Путь к файлу схемы
    schema_path = Path(__file__).parent.parent / "src" / "kira" / "plugin_sdk" / "manifest-schema.json"

    # Записываем схему в файл
    with open(schema_path, 'w', encoding='utf-8') as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)

    print(f"JSON Schema сохранена в: {schema_path}")

    # Также создаем README с описанием схемы
    readme_path = Path(__file__).parent.parent / "src" / "kira" / "plugin_sdk" / "MANIFEST_SCHEMA.md"

    readme_content = """# Схема манифеста плагина Kira

Этот файл содержит JSON Schema для валидации манифеста плагина `kira-plugin.json`.

## Использование

### Валидация через Python

```python
from kira.plugin_sdk.manifest import PluginManifestValidator

validator = PluginManifestValidator()
errors = validator.validate_manifest_file("path/to/kira-plugin.json")

if errors:
    for error in errors:
        print(f"Ошибка: {error}")
else:
    print("Манифест валиден!")
```

### Валидация через JSON Schema

```bash
# Установка ajv-cli
npm install -g ajv-cli

# Валидация
ajv validate -s manifest-schema.json -d kira-plugin.json
```

## Структура манифеста

### Обязательные поля

- `name` - уникальное имя плагина (kebab-case)
- `version` - версия в формате semver
- `displayName` - человекочитаемое название
- `description` - описание функциональности
- `publisher` - имя издателя
- `engines.kira` - требуемая версия ядра
- `permissions` - список разрешений
- `entry` - точка входа (module:function)
- `capabilities` - возможности плагина
- `contributes` - вклад в систему

### Разрешения

- `calendar.read/write` - доступ к календарю
- `vault.read/write` - доступ к хранилищу
- `fs.read/write` - доступ к файловой системе
- `net` - сетевой доступ
- `secrets.read/write` - доступ к секретам
- `events.publish/subscribe` - работа с событиями
- `scheduler.create/cancel` - планировщик
- `sandbox.execute` - выполнение в песочнице

### Возможности

- `pull` - получение данных
- `push` - отправка данных
- `timebox` - работа с временными блоками
- `notify` - уведомления
- `schedule` - планирование
- `transform` - преобразование данных
- `validate` - валидация
- `sync` - синхронизация

### Стратегии изоляции

- `subprocess` - отдельный процесс (по умолчанию)
- `thread` - отдельный поток
- `inline` - выполнение в основном потоке
"""

    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)

    print(f"Документация сохранена в: {readme_path}")


if __name__ == "__main__":
    main()
