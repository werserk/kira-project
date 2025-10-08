#!/usr/bin/env python3
"""CLI команды для работы с Vault и схемами (ADR-007)"""

import json
import sys
from pathlib import Path
from typing import cast

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from datetime import UTC, datetime

import click

from ..core.config import load_config
from ..core.host import create_host_api
from ..core.ids import generate_entity_id, get_known_entity_types
from ..core.schemas import get_schema_cache
from ..core.vault_init import VaultInitError, get_vault_info, init_vault, verify_vault_structure

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(
    context_settings=CONTEXT_SETTINGS,
    help="Управление Vault, схемами и entity",
)
def cli() -> None:
    """Команды для работы с Vault."""


@cli.command("init")
@click.option("--force", is_flag=True, help="Перезаписать существующий Vault")
@click.option("--vault-path", type=str, help="Путь к Vault (по умолчанию из конфигурации)")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def init_vault_cmd(force: bool, vault_path: str | None, verbose: bool) -> int:
    """Инициализировать новый Vault."""
    try:
        config = load_config()
        vault_dir = vault_path or config.get("vault", {}).get("path")

        if not vault_dir:
            click.echo("❌ Путь к Vault не указан в конфигурации или параметрах")
            return 1

        vault_path_obj = Path(vault_dir)

        if verbose:
            click.echo(f"🔧 Инициализация Vault: {vault_path_obj}")

        init_vault(vault_path_obj, force=force)

        click.echo(f"✅ Vault успешно инициализирован: {vault_path_obj}")

        if verbose:
            info = get_vault_info(vault_path_obj)
            click.echo("📊 Информация о Vault:")
            click.echo(f"  - Схемы: {info['schema_count']}")
            click.echo(f"  - Папки созданы: {len(info['entity_counts'])}")

        return 0

    except VaultInitError as exc:
        click.echo(f"❌ Ошибка инициализации: {exc}")
        return 1
    except Exception as exc:
        click.echo(f"❌ Неожиданная ошибка: {exc}")
        return 1


@cli.command("validate")
@click.option("--vault-path", type=str, help="Путь к Vault")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def validate_vault_cmd(vault_path: str | None, verbose: bool) -> int:
    """Валидировать структуру и содержимое Vault."""
    try:
        config = load_config()
        vault_dir = vault_path or config.get("vault", {}).get("path")

        if not vault_dir:
            click.echo("❌ Путь к Vault не указан")
            return 1

        vault_path_obj = Path(vault_dir)

        if verbose:
            click.echo(f"🔍 Валидация Vault: {vault_path_obj}")

        issues = verify_vault_structure(vault_path_obj)

        if issues:
            click.echo("❌ Найдены проблемы:")
            for issue in issues:
                click.echo(f"  - {issue}")
            return 1

        click.echo("✅ Vault структура валидна")

        if verbose:
            info = get_vault_info(vault_path_obj)
            click.echo("\n📊 Статистика Vault:")
            for entity_type, count in info["entity_counts"].items():
                click.echo(f"  - {entity_type}: {count} entities")
            click.echo(f"  - inbox: {info['inbox_items']} items")
            click.echo(f"  - processed: {info['processed_items']} items")

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка валидации: {exc}")
        return 1


@cli.command("new")
@click.option("--type", "entity_type", required=True, help="Тип entity (task, note, event, etc.)")
@click.option("--title", required=True, help="Название entity")
@click.option("--vault-path", type=str, help="Путь к Vault")
@click.option("--template", is_flag=True, help="Создать только шаблон (не файл)")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def new_entity_cmd(entity_type: str, title: str, vault_path: str | None, template: bool, verbose: bool) -> int:
    """Создать новую entity."""
    try:
        config = load_config()
        vault_dir = vault_path or config.get("vault", {}).get("path")

        if not vault_dir:
            click.echo("❌ Путь к Vault не указан")
            return 1

        vault_path_obj = Path(vault_dir)

        # Validate entity type
        known_types = get_known_entity_types()
        if entity_type not in known_types:
            click.echo(f"❌ Неизвестный тип entity: {entity_type}")
            click.echo(f"   Доступные типы: {', '.join(sorted(known_types))}")
            return 1

        # Generate entity data
        entity_id = generate_entity_id(entity_type, title=title)

        # Get schema for defaults
        schema_cache = get_schema_cache(vault_path_obj / ".kira" / "schemas")
        schema = schema_cache.get_schema(entity_type)

        entity_data = {
            "id": entity_id,
            "title": title,
            "created": datetime.now(UTC).isoformat(),
        }

        # Add schema defaults
        if schema:
            defaults = schema.get_default_values()
            for key, value in defaults.items():
                if "." not in key:  # Only root-level defaults
                    entity_data.setdefault(key, value)

        # Create full content template
        content_template = f"""---
id: {entity_id}
title: {title}
created: {datetime.now(UTC).isoformat()}
---

# {title}

<!-- Add your content here -->

*Created by Kira CLI*
"""

        if template:
            # Just show template
            click.echo(content_template)
            return 0

        # Create actual entity
        host_api = create_host_api(vault_path_obj)
        entity = host_api.create_entity(
            entity_type, entity_data, content="<!-- Add your content here -->\n\n*Created by Kira CLI*"
        )

        click.echo(f"✅ Entity создана: {entity.id}")
        click.echo(f"📁 Файл: {entity.path}")

        if verbose:
            click.echo(f"🔧 Тип: {entity_type}")
            click.echo(f"📝 Название: {title}")
            click.echo(f"🆔 ID: {entity_id}")

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка создания entity: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


@cli.command("schemas")
@click.option("--vault-path", type=str, help="Путь к Vault")
@click.option("--list", "list_schemas", is_flag=True, help="Показать список схем")
@click.option("--validate", is_flag=True, help="Валидировать все схемы")
@click.option("--install", is_flag=True, help="Установить/обновить схемы")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def schemas_cmd(vault_path: str | None, list_schemas: bool, validate: bool, install: bool, verbose: bool) -> int:
    """Управление схемами entity."""
    try:
        config = load_config()
        vault_dir = vault_path or config.get("vault", {}).get("path")

        if not vault_dir:
            click.echo("❌ Путь к Vault не указан")
            return 1

        vault_path_obj = Path(vault_dir)
        schemas_dir = vault_path_obj / ".kira" / "schemas"

        if install:
            from ..core.vault_init import install_schemas

            install_schemas(vault_path_obj)
            click.echo("✅ Схемы установлены/обновлены")

        if list_schemas:
            if not schemas_dir.exists():
                click.echo("❌ Директория схем не найдена")
                return 1

            schema_files = list(schemas_dir.glob("*.json"))
            click.echo(f"📋 Схемы в {schemas_dir}:")

            for schema_file in sorted(schema_files):
                entity_type = schema_file.stem
                try:
                    with open(schema_file, encoding="utf-8") as f:
                        schema_data = json.load(f)
                    version = schema_data.get("version", "unknown")
                    title = schema_data.get("title", entity_type)
                    click.echo(f"  ✅ {entity_type}.json (v{version}) - {title}")
                except Exception:
                    click.echo(f"  ❌ {entity_type}.json - Invalid JSON")

        if validate:
            schema_cache = get_schema_cache(schemas_dir)
            try:
                schema_cache.load_schemas(force_reload=True)
                entity_types = schema_cache.get_entity_types()
                click.echo(f"✅ Валидация схем прошла успешно ({len(entity_types)} типов)")

                if verbose:
                    for entity_type in sorted(entity_types):
                        click.echo(f"  ✅ {entity_type}")

            except Exception as exc:
                click.echo(f"❌ Ошибка валидации схем: {exc}")
                return 1

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        return 1


@cli.command("info")
@click.option("--vault-path", type=str, help="Путь к Vault")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def info_cmd(vault_path: str | None, verbose: bool) -> int:
    """Показать информацию о Vault."""
    try:
        config = load_config()
        vault_dir = vault_path or config.get("vault", {}).get("path")

        if not vault_dir:
            click.echo("❌ Путь к Vault не указан")
            return 1

        vault_path_obj = Path(vault_dir)
        info = get_vault_info(vault_path_obj)

        if "error" in info:
            click.echo(f"❌ {info['error']}")
            return 1

        click.echo(f"📁 Vault: {info['vault_path']}")
        click.echo(f"✅ Структура: {'Валидна' if info['structure_valid'] else 'Невалидна'}")
        click.echo(f"📋 Схемы: {info['schema_count']}")

        click.echo("\n📊 Entities:")
        total_entities = sum(info["entity_counts"].values())
        for entity_type, count in info["entity_counts"].items():
            click.echo(f"  - {entity_type}: {count}")
        click.echo(f"  📈 Всего: {total_entities}")

        click.echo("\n📥 Обработка:")
        click.echo(f"  - В inbox: {info['inbox_items']}")
        click.echo(f"  - В processed: {info['processed_items']}")

        if not info["structure_valid"]:
            click.echo("\n❌ Проблемы:")
            for issue in info["issues"]:
                click.echo(f"  - {issue}")

        if verbose and info["structure_valid"]:
            # Show more details
            click.echo("\n🔧 Подробная информация:")
            known_types = get_known_entity_types()
            click.echo(f"  - Поддерживаемые типы: {', '.join(sorted(known_types))}")

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        return 1


def main(args: list[str] | None = None) -> int:
    """Main function."""
    if args is None:
        args = sys.argv[1:]

    try:
        result = cli.main(args=list(args), standalone_mode=False)
        return cast("int", result) if result is not None else 0
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 0


if __name__ == "__main__":
    sys.exit(main())
