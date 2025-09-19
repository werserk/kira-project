# Реестры плагинов и адаптеров

## Обзор

Kira использует YAML-файлы для управления локальными плагинами и адаптерами в монорепо. Это позволяет легко включать/отключать компоненты без изменения кода.

## Структура реестров

### plugins_local.yaml

```yaml
plugins:
  - name: kira-inbox
    path: "src/kira/plugins/inbox"
    enabled: true
  - name: kira-calendar
    path: "src/kira/plugins/calendar"
    enabled: true
  - name: kira-deadlines
    path: "src/kira/plugins/deadlines"
    enabled: false
```

### adapters_local.yaml

```yaml
adapters:
  - name: kira-telegram
    path: "src/kira/adapters/telegram"
    enabled: true
  - name: kira-gcal
    path: "src/kira/adapters/gcal"
    enabled: true
  - name: kira-filesystem
    path: "src/kira/adapters/filesystem"
    enabled: false
```

## API для работы с реестрами

### Реестр плагинов

```python
from kira.registry import get_plugin_registry

registry = get_plugin_registry()

# Получить все плагины
plugins = registry.get_plugins()

# Получить только включенные плагины
enabled_plugins = registry.get_enabled_plugins()

# Получить конкретный плагин
plugin = registry.get_plugin('kira-inbox')

# Проверить, включен ли плагин
is_enabled = registry.is_plugin_enabled('kira-calendar')

# Получить путь к плагину
plugin_path = registry.get_plugin_path('kira-inbox')
```

### Реестр адаптеров

```python
from kira.registry import get_adapter_registry

registry = get_adapter_registry()

# Получить все адаптеры
adapters = registry.get_adapters()

# Получить только включенные адаптеры
enabled_adapters = registry.get_enabled_adapters()

# Получить конкретный адаптер
adapter = registry.get_adapter('kira-telegram')

# Проверить, включен ли адаптер
is_enabled = registry.is_adapter_enabled('kira-gcal')

# Получить путь к адаптеру
adapter_path = registry.get_adapter_path('kira-telegram')
```

## Управление компонентами

### Включение/отключение плагинов

Чтобы отключить плагин, измените `enabled: false` в `plugins_local.yaml`:

```yaml
plugins:
  - name: kira-calendar
    path: "src/kira/plugins/calendar"
    enabled: false  # Плагин отключен
```

### Включение/отключение адаптеров

Аналогично для адаптеров в `adapters_local.yaml`:

```yaml
adapters:
  - name: kira-filesystem
    path: "src/kira/adapters/filesystem"
    enabled: false  # Адаптер отключен
```

## Добавление новых компонентов

### Добавление плагина

1. Создайте директорию плагина в `src/kira/plugins/`
2. Добавьте `kira-plugin.json` с манифестом
3. Добавьте запись в `plugins_local.yaml`:

```yaml
plugins:
  - name: kira-my-plugin
    path: "src/kira/plugins/my-plugin"
    enabled: true
```

### Добавление адаптера

1. Создайте директорию адаптера в `src/kira/adapters/`
2. Реализуйте адаптер
3. Добавьте запись в `adapters_local.yaml`:

```yaml
adapters:
  - name: kira-my-adapter
    path: "src/kira/adapters/my-adapter"
    enabled: true
```

## Интеграция с загрузчиком плагинов

Реестры интегрируются с системой загрузки плагинов:

```python
from kira.registry import get_plugin_registry
from kira.core.plugin_loader import PluginLoader

# Получить включенные плагины из реестра
registry = get_plugin_registry()
enabled_plugins = registry.get_enabled_plugins()

# Загрузить плагины
loader = PluginLoader()
for plugin_info in enabled_plugins:
    plugin_path = plugin_info['path']
    loader.load_plugin(plugin_path)
```

## Тестирование

Реестры имеют полное покрытие тестами:

```bash
python -m pytest tests/unit/test_registry.py
```

Тесты проверяют:
- Загрузку реестров из YAML файлов
- Фильтрацию включенных/отключенных компонентов
- Поиск компонентов по имени
- Обработку ошибок и пустых реестров

## Лучшие практики

1. **Именование**: Используйте префикс `kira-` для всех компонентов
2. **Пути**: Относительные пути от корня проекта
3. **Состояние**: Явно указывайте `enabled: true/false`
4. **Версионирование**: Реестры не версионируются, только код компонентов
5. **Документация**: Обновляйте реестры при добавлении новых компонентов
