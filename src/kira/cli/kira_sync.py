"""CLI модуль для синхронизации адаптеров"""

import sys
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import click

from ..core.config import load_config
from ..core.events import create_event_bus
from ..core.scheduler import create_scheduler
from ..pipelines.sync_pipeline import SyncPipeline, SyncPipelineConfig

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(
    context_settings=CONTEXT_SETTINGS,
    help="Синхронизация внешних адаптеров (GCal, Telegram)",
)
def cli() -> None:
    """Корневая команда sync."""


@cli.command("run")
@click.option(
    "--adapters",
    type=str,
    help="Список адаптеров через запятую (gcal,telegram). По умолчанию: все",
)
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def run_command(adapters: str | None, verbose: bool) -> int:
    """Запустить синхронизацию адаптеров."""

    try:
        config = load_config()

        if verbose:
            click.echo("🔧 Загружена конфигурация")
            click.echo(f"   Vault: {config.get('vault', {}).get('path', 'не указан')}")

        adapter_list = None
        if adapters:
            adapter_list = [a.strip() for a in adapters.split(",")]

        return handle_sync_run(config, adapter_list, verbose)
    except FileNotFoundError as exc:
        click.echo(f"❌ Файл не найден: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - вывод трейсбека ниже
        click.echo(f"❌ Ошибка выполнения sync команды: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


@cli.command("schedule")
@click.option(
    "--interval",
    type=int,
    default=300,
    show_default=True,
    help="Интервал синхронизации в секундах",
)
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def schedule_command(interval: int, verbose: bool) -> int:
    """Запустить периодическую синхронизацию (daemon mode)."""

    try:
        config = load_config()

        if verbose:
            click.echo("🔧 Загружена конфигурация")
            click.echo(f"   Vault: {config.get('vault', {}).get('path', 'не указан')}")

        return handle_sync_schedule(config, interval, verbose)
    except FileNotFoundError as exc:
        click.echo(f"❌ Файл не найден: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - вывод трейсбека ниже
        click.echo(f"❌ Ошибка выполнения sync schedule: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


def handle_sync_run(
    config: dict,
    adapter_list: list[str] | None,
    verbose: bool,
) -> int:
    """Обработка одноразовой синхронизации."""

    adapters_str = ", ".join(adapter_list) if adapter_list else "все"
    click.echo(f"🔄 Запуск синхронизации адаптеров: {adapters_str}...")

    if verbose:
        click.echo(f"   Адаптеры: {adapter_list or 'все доступные'}")

    # Create event bus for pipeline
    event_bus = create_event_bus()

    # Create pipeline config
    pipeline_config = SyncPipelineConfig(
        adapters=adapter_list or ["gcal", "telegram"],
        log_path=Path("logs/pipelines/sync.jsonl"),
    )

    # Create pipeline
    pipeline = SyncPipeline(
        config=pipeline_config,
        event_bus=event_bus,
    )

    try:
        result = pipeline.run(adapters=adapter_list)

        if verbose:
            click.echo(f"   Синхронизировано: {result.adapters_synced}")
            click.echo(f"   Ошибок: {result.adapters_failed}")
            click.echo(f"   Длительность: {result.duration_ms:.2f}ms")
            click.echo(f"   Trace ID: {result.trace_id}")

        if result.success:
            click.echo("✅ Синхронизация завершена успешно")
            return 0
        else:
            click.echo("⚠️  Синхронизация завершена с ошибками:")
            for error in result.errors:
                click.echo(f"   - {error}")
            return 1

    except Exception as exc:  # pragma: no cover - зависит от реализации pipeline
        click.echo(f"❌ Ошибка синхронизации: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


def handle_sync_schedule(
    config: dict,
    interval: int,
    verbose: bool,
) -> int:
    """Обработка периодической синхронизации."""

    click.echo(f"⏰ Запуск периодической синхронизации (интервал: {interval}s)...")

    if verbose:
        click.echo("   Режим: daemon")
        click.echo(f"   Интервал: {interval} секунд")

    # Create event bus and scheduler
    event_bus = create_event_bus()
    scheduler = create_scheduler()

    # Create pipeline config
    pipeline_config = SyncPipelineConfig(
        sync_interval_seconds=interval,
        adapters=["gcal", "telegram"],
        log_path=Path("logs/pipelines/sync.jsonl"),
    )

    # Create pipeline
    pipeline = SyncPipeline(
        config=pipeline_config,
        event_bus=event_bus,
        scheduler=scheduler,
    )

    try:
        # Schedule periodic sync
        job_id = pipeline.schedule_periodic_sync()

        if job_id:
            click.echo(f"✅ Периодическая синхронизация запущена (Job ID: {job_id})")
            click.echo("   Нажмите Ctrl+C для остановки")

            if verbose:
                click.echo(f"   Первая синхронизация через {interval} секунд")

            # Keep running until interrupted
            try:
                scheduler.start()
            except KeyboardInterrupt:
                click.echo("\n⏹️  Остановка синхронизации...")
                pipeline.cancel_periodic_sync()
                scheduler.stop()
                click.echo("✅ Синхронизация остановлена")

            return 0
        else:
            click.echo("❌ Не удалось запланировать синхронизацию")
            return 1

    except Exception as exc:  # pragma: no cover - зависит от scheduler
        click.echo(f"❌ Ошибка планирования синхронизации: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]

    try:
        return cli.main(args=list(args), standalone_mode=False)
    except SystemExit as exc:  # pragma: no cover - click нормализует код выхода
        return int(exc.code) if exc.code is not None else 0


if __name__ == "__main__":  # pragma: no cover - исполняемый модуль
    sys.exit(main())
