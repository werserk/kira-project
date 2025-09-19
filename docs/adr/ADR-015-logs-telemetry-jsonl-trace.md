---
type: decision
id: ADR-015
title: Structured logs/telemetry for core/adapters/plugins/pipelines
date: 2025-09-19
status: accepted
owners: [kira-core]
drivers: [объяснимость, отладка, доверие]
---

## Контекст

Нужна трассируемость EtE и метрики производительности/ошибок.

## Решение

- JSONL‑логи в `logs/{core,adapters,plugins,pipelines}`; поля: `timestamp, trace_id, component, input_hash, latency_ms, outcome, refs[]`.
- Команда `kira diag tail --component X`.

## Альтернативы

- Разрозненные принты → непригодно для эксплуатации → отклонено.

## Реализация

- Единый логгер, прокидывается в `ctx.log`; trace_id по событию.

## Риски

- Объём логов → ротация/сжатие.

## Метрики/DoD

- Любой баг воспроизводится по trace; SLO: средняя латентность < целевых порогов.
