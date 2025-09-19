---
type: decision
id: ADR-016
title: Graph consistency checks and deduplication guardrails
date: 2025-09-19
status: proposed
owners: [kira-core]
drivers: [целостность знаний, отсутствие двоякости]
---

## Контекст

При росте базы появляются осиротевшие узлы, циклы `depends_on`, дубли по названию.

## Решение

- Инструмент `core/links.py` + `scripts/graph_report.py`: поиск орфанов, циклов, дублей (`title+context`), битых wikilinks.
- Ночной `kira validate` + отчёт в `@Indexes/graph_report.md` в Vault.

## Альтернативы

- Ручной контроль → плохо масштабируется → отклонено.

## Реализация

- Интеграционный тест на примерном Vault; auto‑fix опционально (pull‑request в Vault).

## Риски

- Агрессивные авто‑фиксы → только отчёт по умолчанию.

## Метрики/DoD

- 0 циклов и 0 битых ссылок после первых прогонов; тренд на убывание дублей.
