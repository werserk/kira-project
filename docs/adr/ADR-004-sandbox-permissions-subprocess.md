---
type: decision
id: ADR-004
title: Sandbox & Permissions (subprocess + JSON-RPC)
date: 2025-09-19
status: accepted
owners: [kira-core]
drivers: [безопасность, отказоустойчивость, изоляция]
---

## Контекст

Плагины потенциально нестабильны/не доверены. Нужна изоляция и явные права.

## Решение

- Каждый плагин по умолчанию исполняется в subprocess; IPC = JSON‑RPC.
- Модель разрешений: `net`, `secrets.read`, `calendar.write`, `git.write`, и т.д.
- Таймауты, рестарты (watchdog), лимиты ресурсов (по возможности ОС).

## Альтернативы

- In‑process плагины — просто, но бьёт стабильность ядра → отклонено.

## Реализация

- `core/sandbox.py` (launcher, rpc), `plugin_sdk/permissions.py` (гварды), перехват внешних действий через `core/policy.py`.

## Риски

- IPC overhead → приемлем в обмен на надёжность.

## Метрики/DoD

- Крах плагина не валит ядро; попытка запрещённого действия логируется и блокируется.
