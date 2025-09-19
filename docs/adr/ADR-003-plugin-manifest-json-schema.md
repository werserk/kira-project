---
type: decision
id: ADR-003
title: Plugin manifest (kira-plugin.json) with JSON Schema validation
date: 2025-09-19
status: accepted
owners: [kira-core]
related: [ADR-002]
drivers: [однозначность контрактов, автозагрузка, безопасные разрешения]
---

## Контекст

Нужен самодокументируемый контракт плагина и автоматическая валидация.

## Решение

- Вводим `kira-plugin.json` (манифест). Поля: `name, version, engines.kira, permissions, entry, capabilities, contributes{events,commands}, configSchema, sandbox{strategy,timeoutMs}`.
- JSON Schema для манифеста, валидация на старте загрузки.

## Альтернативы

- Python entry points без явного манифеста → теряется совместимость и пермишены → отклонено.

## Реализация

- `plugin_sdk/manifest.py` (schema + validator); пример манифеста в каждом встроенном плагине.

## Риски

- Разрастание схемы → версионирование схемы и backward‑shims в загрузчике.

## Метрики/DoD

- Все встроенные плагины проходят валидацию; ошибки читаемы (с указанием поля).
