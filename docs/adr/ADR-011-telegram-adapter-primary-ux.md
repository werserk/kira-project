---
type: decision
id: ADR-011
title: Telegram adapter as primary UX (capture, confirm, review)
date: 2025-09-19
status: proposed
owners: [kira-adapters]
drivers: [максимальный UX, непрерывный захват]
---

## Контекст

Пользовательский ввод/вывод через Telegram: текст/вложения/кнопки.

## Решение

- `adapters/telegram/adapter.py` слушает апдейты → `events.publish('message.received', ...)`.
- Быстрое подтверждение сомнительных извлечений (inline‑кнопки) → вызовы команд плагинов.
- Ежедневные брифинги, сводки «кандидатов» из чатов.

## Альтернативы

- Только ручные команды из CLI → UX хуже → отклонено.

## Реализация

- Режимы `bot`/`userbot`; whitelist чатов; хранение оффсетов; idempotency.

## Риски

- Приватность/безопасность → конфиг листов, логгинг только метаданных.

## Метрики/DoD

- ≥85% корректных actionable‑извлечений по ручной выборке; NPS UX.
