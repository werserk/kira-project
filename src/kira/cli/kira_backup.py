#!/usr/bin/env python3
"""CLI модуль для бэкапов Vault"""

import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import click

from ..core.config import load_config

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(
    context_settings=CONTEXT_SETTINGS,
    help="Управление бэкапами Vault",
)
def cli() -> None:
    """Корневая команда для бэкапов."""


@cli.command("create")
@click.option("--name", type=str, help="Имя бэкапа (по умолчанию: timestamp)")
@click.option("--destination", type=str, help="Директория для бэкапа (по умолчанию: .backups)")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def create_command(name: str | None, destination: str | None, verbose: bool) -> int:
    """Создать бэкап Vault."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        if not vault_path.exists():
            click.echo(f"❌ Vault не найден: {vault_path}")
            return 1

        # Определить директорию бэкапов
        if destination:
            backup_root = Path(destination)
        else:
            backup_root = vault_path.parent / ".backups"

        backup_root.mkdir(parents=True, exist_ok=True)

        # Создать имя бэкапа
        if not name:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            name = f"vault-backup-{timestamp}"

        backup_path = backup_root / name

        if backup_path.exists():
            click.echo(f"❌ Бэкап с таким именем уже существует: {backup_path}")
            return 1

        click.echo(f"💾 Создание бэкапа: {name}")

        if verbose:
            click.echo(f"   Источник: {vault_path}")
            click.echo(f"   Назначение: {backup_path}")

        # Создать бэкап
        shutil.copytree(vault_path, backup_path, symlinks=False)

        # Создать метаинформацию
        metadata = {
            "created": datetime.now(timezone.utc).isoformat(),
            "source": str(vault_path),
            "name": name,
        }

        metadata_file = backup_path / ".backup-info.txt"
        with open(metadata_file, "w", encoding="utf-8") as f:
            f.write(f"Backup created: {metadata['created']}\n")
            f.write(f"Source: {metadata['source']}\n")
            f.write(f"Name: {metadata['name']}\n")

        # Подсчитать размер
        total_size = sum(f.stat().st_size for f in backup_path.rglob("*") if f.is_file())
        size_mb = total_size / (1024 * 1024)

        click.echo(f"✅ Бэкап создан: {backup_path}")
        click.echo(f"📊 Размер: {size_mb:.2f} MB")

        if verbose:
            file_count = sum(1 for _ in backup_path.rglob("*") if _.is_file())
            click.echo(f"📁 Файлов: {file_count}")

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка создания бэкапа: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


@cli.command("list")
@click.option("--destination", type=str, help="Директория с бэкапами (по умолчанию: .backups)")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def list_command(destination: str | None, verbose: bool) -> int:
    """Показать список бэкапов."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        # Определить директорию бэкапов
        if destination:
            backup_root = Path(destination)
        else:
            backup_root = vault_path.parent / ".backups"

        if not backup_root.exists():
            click.echo("💾 Бэкапов пока нет")
            return 0

        # Найти все бэкапы
        backups = []
        for backup_dir in backup_root.iterdir():
            if backup_dir.is_dir():
                # Получить информацию о бэкапе
                info = get_backup_info(backup_dir)
                backups.append(info)

        if not backups:
            click.echo("💾 Бэкапов не найдено")
            return 0

        # Сортировать по дате создания
        backups.sort(key=lambda x: x["created"], reverse=True)

        click.echo(f"💾 Бэкапы ({len(backups)}):\n")

        for backup in backups:
            name = backup["name"]
            created = backup["created"]
            size_mb = backup["size_mb"]

            # Форматировать дату
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                date_str = created

            click.echo(f"  📦 {name}")
            click.echo(f"     Создан: {date_str}")
            click.echo(f"     Размер: {size_mb:.2f} MB")

            if verbose:
                click.echo(f"     Путь: {backup['path']}")

            click.echo()

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


@cli.command("restore")
@click.argument("backup_name")
@click.option("--destination", type=str, help="Директория с бэкапами (по умолчанию: .backups)")
@click.option("--force", is_flag=True, help="Перезаписать существующий Vault без подтверждения")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def restore_command(backup_name: str, destination: str | None, force: bool, verbose: bool) -> int:
    """Восстановить Vault из бэкапа."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        # Определить директорию бэкапов
        if destination:
            backup_root = Path(destination)
        else:
            backup_root = vault_path.parent / ".backups"

        backup_path = backup_root / backup_name

        if not backup_path.exists():
            click.echo(f"❌ Бэкап не найден: {backup_name}")
            return 1

        click.echo(f"🔄 Восстановление из бэкапа: {backup_name}")

        if verbose:
            click.echo(f"   Бэкап: {backup_path}")
            click.echo(f"   Назначение: {vault_path}")

        # Проверить, существует ли текущий Vault
        if vault_path.exists():
            if not force:
                click.echo("\n⚠️  ВНИМАНИЕ: Текущий Vault будет перезаписан!")
                if not click.confirm("Продолжить?"):
                    click.echo("Отменено")
                    return 0

            # Создать временный бэкап текущего Vault
            temp_backup_name = f"vault-before-restore-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
            temp_backup_path = backup_root / temp_backup_name

            click.echo(f"💾 Создание временного бэкапа текущего Vault: {temp_backup_name}")
            shutil.copytree(vault_path, temp_backup_path, symlinks=False)

            # Удалить текущий Vault
            shutil.rmtree(vault_path)

        # Восстановить из бэкапа
        shutil.copytree(backup_path, vault_path, symlinks=False)

        # Удалить метаинформацию бэкапа из восстановленного Vault
        backup_info = vault_path / ".backup-info.txt"
        if backup_info.exists():
            backup_info.unlink()

        click.echo(f"✅ Vault восстановлен из бэкапа: {backup_name}")

        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка восстановления: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


@cli.command("delete")
@click.argument("backup_name")
@click.option("--destination", type=str, help="Директория с бэкапами (по умолчанию: .backups)")
@click.option("--force", is_flag=True, help="Не запрашивать подтверждение")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def delete_command(backup_name: str, destination: str | None, force: bool, verbose: bool) -> int:
    """Удалить бэкап."""
    try:
        config = load_config()
        vault_path = Path(config.get("vault", {}).get("path", "vault"))

        # Определить директорию бэкапов
        if destination:
            backup_root = Path(destination)
        else:
            backup_root = vault_path.parent / ".backups"

        backup_path = backup_root / backup_name

        if not backup_path.exists():
            click.echo(f"❌ Бэкап не найден: {backup_name}")
            return 1

        # Подтверждение
        if not force:
            if not click.confirm(f"Удалить бэкап {backup_name}?"):
                click.echo("Отменено")
                return 0

        # Удалить
        shutil.rmtree(backup_path)

        click.echo(f"✅ Бэкап удален: {backup_name}")
        return 0

    except Exception as exc:
        click.echo(f"❌ Ошибка удаления: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


# Helper functions


def get_backup_info(backup_path: Path) -> dict:
    """Получить информацию о бэкапе."""
    info = {
        "name": backup_path.name,
        "path": str(backup_path),
        "created": "",
        "size_mb": 0.0,
    }

    # Попытаться прочитать метаинформацию
    metadata_file = backup_path / ".backup-info.txt"
    if metadata_file.exists():
        try:
            with open(metadata_file, encoding="utf-8") as f:
                for line in f:
                    if line.startswith("Backup created:"):
                        info["created"] = line.split(":", 1)[1].strip()
        except Exception:
            pass

    # Если метаинформации нет, использовать время модификации
    if not info["created"]:
        mtime = backup_path.stat().st_mtime
        info["created"] = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

    # Подсчитать размер
    total_size = sum(f.stat().st_size for f in backup_path.rglob("*") if f.is_file())
    info["size_mb"] = total_size / (1024 * 1024)

    return info


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]

    try:
        return cli.main(args=list(args), standalone_mode=False)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 0


if __name__ == "__main__":
    sys.exit(main())
