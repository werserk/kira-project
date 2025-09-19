---
type: decision
id: ADR-012
title: Google Calendar adapter + calendar plugin for sync & timeboxing
date: 2025-09-19
status: proposed
owners: [kira-adapters, kira-plugins]
drivers: [не пропускать встречи/дедлайны]
---

## Контекст

Синхронизация событий и due‑задач с внешним календарём.

## Решение

- Источник истины (MVP): GCal. Мэппинг: `event(sync:gcal) ↔ 1:1`, `task with due → all‑day` или `time_hint` блок.
- Команды: `calendar.pull|push`; таймбокс при `enter_doing` (FSM).

## Альтернативы

- Локальный календарь → хуже экосистема → отложено.

## Реализация

- Adapter `gcal.adapter`, плагин `plugins/calendar`.

## Риски

- Расхождения GCal↔Vault → reconcile и nightly сверка.

## Метрики/DoD

- 0 расхождений по nightly; латентность операции < 2с.
