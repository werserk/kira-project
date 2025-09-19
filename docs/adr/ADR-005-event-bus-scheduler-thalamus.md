---
type: decision
id: ADR-005
title: Event-bus and scheduler as system thalamus
date: 2025-09-19
status: accepted
owners: [kira-core]
drivers: [низкая связность, реактивность, предсказуемость]
---

## Контекст

Нужна реактивная архитектура для adapters→pipelines→plugins.

## Решение

- `core/events.py`: publish/subscribe, фильтры, ретраи, журналирование.
- `core/scheduler.py`: cron/interval/at; интеграция с pipelines.
- Канонические события: `message.received`, `file.dropped`, `entity.created`, `task.due_soon`, `meeting.finished`, `sync.tick`.

## Альтернативы

- Жёсткие вызовы между модулями → сильная связность → отклонено.

## Реализация

- Подписки объявляют плагины (через `@on_event`). Pipelines подписываются централизованно.

## Риски

- Потеря событий → persistence/журнал и ретраи.

## Метрики/DoD

- Задержка доставки < 100 мс; 0 потерянных событий в нагрузочном тесте.
