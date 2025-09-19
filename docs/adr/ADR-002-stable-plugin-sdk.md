---
type: decision
id: ADR-002
title: Stable Plugin SDK (context, decorators, types)
date: 2025-09-19
status: accepted
owners: [kira-core]
drivers: [расширяемость, совместимость, безопасность]
---

## Контекст

Плагины должны развиваться независимо от ядра, иметь стабильный API.

## Решение

- Пакет `src/kira/plugin_sdk`: `context.py`, `decorators.py` (@on_event, @command), `types.py`, `permissions.py`, `rpc.py`, `manifest.py`.
- Контекст предоставляет фасады: `ctx.vault`, `ctx.events`, `ctx.scheduler`, `ctx.kv`, `ctx.secrets`, `ctx.fs`, `ctx.log`.
- SemVer: SDK = 1.x, совместимость по `"engines": {"kira": "^1.0.0"}`.

## Альтернативы

- Прямые импорты ядра из плагинов — ломко и небезопасно → отклонено.

## Реализация

- Типы сущностей Vault (Pydantic/TypedDict) — в SDK; автоген доки SDK.

## Риски

- Рост SDK → модульность, контрактные тесты.

## Метрики/DoD

- Примерный плагин компилируется без импорта из `kira.core.*`; 100% публичных типов покрыты контракт‑тестами.
