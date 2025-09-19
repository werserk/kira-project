---
type: decision
id: ADR-014
title: Task FSM (todo→doing→review→done|blocked) with timeboxing hooks
date: 2025-09-19
status: proposed
owners: [kira-core, kira-plugins]
drivers: [предсказуемость, осмысленная занятость]
---

## Контекст

Единая модель состояний задач и автоматические действия при переходах.

## Решение

- FSM: `todo→doing→review→done|blocked`; `enter_doing` → таймбокс в календаре, `enter_review` → черновик письма ревьюеру, `enter_done` → апдейт Weekly/KR.

## Альтернативы

- Без FSM — хаотично → отклонено.

## Реализация

- `.kira/ontology/fsm-task.yaml` + хуки в `plugins/deadlines` и `plugins/mailer`.

## Риски

- Перетаймбоксинг → политика, квоты, пользовательские override.

## Метрики/DoD

- ≥90% задач в `doing` имеют таймбокс; снижение просрочек WoW.
