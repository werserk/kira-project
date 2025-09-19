---
type: decision
id: ADR-006
title: Vault Host API; forbid direct FS writes by plugins
date: 2025-09-19
status: accepted
owners: [kira-core]
drivers: [целостность данных, контракты папок, валидация]
---

## Контекст

Сущности Vault должны создаваться/меняться консистентно и валидироваться.

## Решение

- Все плагинные операции чтения/записи идут через `core/host.py` (`ctx.vault`).
- Перед записью: валидация YAML по `.kira/schemas`, соблюдение folder‑contracts, генерация `id`, обратные ссылки.

## Альтернативы

- Свободная запись файлов → дубли/битые ссылки → отклонено.

## Реализация

- `core/md_io.py`, `core/schemas.py`, `core/links.py`; транзакционная запись + событие `entity.updated`.

## Риски

- Латентность на валидации → кэширование схем и быстрый парсер frontmatter.

## Метрики/DoD

- `make validate` выдаёт 0 критических ошибок на EtE циклах.
