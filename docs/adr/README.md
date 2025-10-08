# Architecture Decision Records (ADR)

This folder contains Architecture Decision Records (ADR) for Kira. ADRs document important architectural choices, their context, and consequences.

## ADR statuses

- **proposed** - proposed, under discussion
- **accepted** - accepted, being implemented
- **deprecated** - deprecated, replaced
- **superseded** - superseded by another ADR

## ADR list

### Foundational

| ID | Название | Статус | Дата | Владельцы |
|----|----------|--------|------|-----------|
| [ADR-001](ADR-001-monorepo-src-layout.md) | Monorepo with src-layout and co-located built-in plugins | accepted | 2025-09-19 | werserk |
| [ADR-002](ADR-002-stable-plugin-sdk.md) | Stable Plugin SDK (context, decorators, types) | accepted | 2025-09-19 | kira-core |
| [ADR-003](ADR-003-plugin-manifest-json-schema.md) | Plugin manifest (kira-plugin.json) with JSON Schema validation | accepted | 2025-09-19 | kira-core |
| [ADR-004](ADR-004-sandbox-permissions-subprocess.md) | Sandbox & Permissions (subprocess + JSON-RPC) | accepted | 2025-09-19 | kira-core |
| [ADR-005](ADR-005-event-bus-scheduler-thalamus.md) | Event-bus and scheduler as system thalamus | accepted | 2025-09-19 | kira-core |

### Архитектура данных

| ID | Название | Статус | Дата | Владельцы |
|----|----------|--------|------|-----------|
| [ADR-006](ADR-006-vault-host-api-no-direct-fs.md) | Vault Host API; forbid direct FS writes by plugins | accepted | 2025-09-19 | kira-core |
| [ADR-007](ADR-007-schemas-folder-contracts-single-source.md) | Schemas & Folder-Contracts as the single source of truth | accepted | 2025-09-19 | kira-core |
| [ADR-008](ADR-008-ids-naming-conventions.md) | Stable identifiers and naming rules | accepted | 2025-09-19 | kira-core |

### Интеграции и интерфейсы

| ID | Название | Статус | Дата | Владельцы |
|----|----------|--------|------|-----------|
| [ADR-009](ADR-009-pipelines-thin-orchestration.md) | Pipelines as thin orchestration (adapters↔plugins) | accepted | 2025-09-19 | kira-core |
| [ADR-010](ADR-010-cli-make-canonical-interface.md) | CLI & Make targets as canonical interface | accepted | 2025-09-19 | kira-core |
| [ADR-011](ADR-011-telegram-adapter-primary-ux.md) | Telegram adapter as primary UX (capture, confirm, review) | accepted | 2025-09-19 | kira-adapters |
| [ADR-012](ADR-012-google-calendar-adapter-plugin.md) | Google Calendar adapter + calendar plugin for sync & timeboxing | accepted | 2025-09-19 | kira-adapters, kira-plugins |

### Плагины и функциональность

| ID | Название | Статус | Дата | Владельцы |
|----|----------|--------|------|-----------|
| [ADR-013](ADR-013-inbox-normalizer-plugin.md) | Inbox normalizer plugin (free-text → typed entities) | accepted | 2025-09-19 | kira-plugins |
| [ADR-014](ADR-014-task-fsm-timeboxing-hooks.md) | Task FSM (todo→doing→review→done|blocked) with timeboxing hooks | accepted | 2025-09-19 | kira-core, kira-plugins |

### Наблюдаемость и качество

| ID | Название | Статус | Дата | Владельцы |
|----|----------|--------|------|-----------|
| [ADR-015](ADR-015-logs-telemetry-jsonl-trace.md) | Structured logs/telemetry for core/adapters/plugins/pipelines | accepted | 2025-09-19 | kira-core |
| [ADR-016](ADR-016-graph-consistency-dedup-guardrails.md) | Graph consistency checks and deduplication guardrails | accepted | 2025-09-19 | kira-core |

## Создание нового ADR

1. Скопируйте шаблон `_template.md`
2. Присвойте следующий номер ADR
3. Заполните все разделы
4. Добавьте ссылку в этот README
5. Создайте PR для обсуждения

## Связанные документы

- [Архитектура системы](../architecture.md)
- [Документация плагинов](../plugins.md)
- [Конфигурация](../configuration.md)
- [CLI команды](../cli.md)
