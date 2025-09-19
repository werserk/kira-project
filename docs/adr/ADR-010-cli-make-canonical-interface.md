---
type: decision
id: ADR-010
title: CLI & Make targets as canonical interface
date: 2025-09-19
status: accepted
owners: [kira-core]
drivers: [DX, автоматизация, воспроизводимость]
---

## Контекст

Нужна единая точка входа для ручных запусков и CI.

## Решение

- CLI команды: `kira inbox`, `kira calendar pull|push`, `kira rollup daily|weekly`, `kira ext list|install|enable|disable`, `kira validate`.
- Makefile таргеты маппят CLI; примеры в `docs/`.

## Альтернативы

- Скрипты россыпью — нет единообразия → отклонено.

## Реализация

- `src/kira/cli/*`, entry‑points; автодока CLI.

## Риски

- Разрастание CLI → группировка по подкомандам.

## Метрики/DoD

- Все сценарии покрыты CLI; инструкции в README воспроизводимы.
