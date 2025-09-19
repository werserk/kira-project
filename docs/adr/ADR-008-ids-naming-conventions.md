---
type: decision
id: ADR-008
title: Stable identifiers and naming rules
date: 2025-09-19
status: accepted
owners: [kira-core]
drivers: [идемпотентность, адресация, отсутствие дублей]
---

## Контекст

Непоследовательное именование рвёт ссылки и плодит дубли.

## Решение

- `id:` обязателен: `<type>-YYYYMMDD-HHmm-<slug>`; имя файла сущности = `id.md`.
- TZ по умолчанию: Europe/Brussels; `kebab-case` для путей.

## Альтернативы

- Авто‑uuid без смысла → хуже UX и поиска → отклонено.

## Реализация

- `core/ids.py` + мигратор `scripts/rename_move.py` для обновления wikilinks.

## Риски

- Старые ссылки → авто‑перелинковка.

## Метрики/DoD

- 0 коллизий; поиск по `id` < 1s; нет «осиротевших» ссылок.
