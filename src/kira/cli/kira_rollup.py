"""CLI модуль для создания rollup отчетов"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import click

from ..core.config import load_config
from ..pipelines.rollup_pipeline import RollupPipeline

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(
    context_settings=CONTEXT_SETTINGS,
    help="Создать rollup отчеты (дневные/недельные)",
)
def cli() -> None:
    """Корневая команда rollup."""


@cli.command("daily")
@click.option("--date", type=str, help="Дата для rollup (YYYY-MM-DD, по умолчанию: вчера)")
@click.option("--output", type=str, help="Путь для сохранения отчета")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def daily_command(date: str | None, output: str | None, verbose: bool) -> int:
    """Создать дневной rollup."""

    try:
        config = load_config()

        if verbose:
            click.echo("🔧 Загружена конфигурация")
            click.echo(f"   Vault: {config.get('vault', {}).get('path', 'не указан')}")

        pipeline = RollupPipeline(config)
        return handle_daily_rollup(pipeline, date, output, verbose)
    except FileNotFoundError as exc:
        click.echo(f"❌ Файл не найден: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - вывод трейсбека ниже
        click.echo(f"❌ Ошибка выполнения rollup команды: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


@cli.command("weekly")
@click.option("--week", type=str, help="Неделя для rollup (YYYY-WW, по умолчанию: прошлая неделя)")
@click.option("--output", type=str, help="Путь для сохранения отчета")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def weekly_command(week: str | None, output: str | None, verbose: bool) -> int:
    """Создать недельный rollup."""

    try:
        config = load_config()

        if verbose:
            click.echo("🔧 Загружена конфигурация")
            click.echo(f"   Vault: {config.get('vault', {}).get('path', 'не указан')}")

        pipeline = RollupPipeline(config)
        return handle_weekly_rollup(pipeline, week, output, verbose)
    except FileNotFoundError as exc:
        click.echo(f"❌ Файл не найден: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - вывод трейсбека ниже
        click.echo(f"❌ Ошибка выполнения rollup команды: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


def handle_daily_rollup(
    pipeline: RollupPipeline,
    date: str | None,
    output: str | None,
    verbose: bool,
) -> int:
    """Обработка дневного rollup."""

    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            click.echo(f"❌ Неверный формат даты: {date}. Используйте YYYY-MM-DD")
            return 1
    else:
        target_date = (datetime.now() - timedelta(days=1)).date()

    click.echo(f"📊 Создание дневного rollup за {target_date}...")

    if verbose:
        click.echo(f"   Дата: {target_date}")
        if output:
            click.echo(f"   Выходной файл: {output}")

    try:
        result = pipeline.create_daily_rollup(date=target_date, output_path=output)

        if verbose:
            click.echo(f"   Обработано задач: {result.get('tasks_count', 0)}")
            click.echo(f"   Обработано событий: {result.get('events_count', 0)}")
            click.echo(f"   Создано записей: {result.get('entries_count', 0)}")

        click.echo("✅ Дневной rollup создан")
        return 0
    except Exception as exc:  # pragma: no cover - зависит от реализации pipeline
        click.echo(f"❌ Ошибка создания дневного rollup: {exc}")
        return 1


def handle_weekly_rollup(
    pipeline: RollupPipeline,
    week: str | None,
    output: str | None,
    verbose: bool,
) -> int:
    """Обработка недельного rollup."""

    if week:
        try:
            year, week_number = week.split("-W")
            year = int(year)
            week_number = int(week_number)
            jan_4 = datetime(year, 1, 4)
            monday = jan_4 - timedelta(days=jan_4.weekday()) + timedelta(weeks=week_number - 1)
            start_date = monday.date()
        except (ValueError, IndexError):
            click.echo(f"❌ Неверный формат недели: {week}. Используйте YYYY-WW")
            return 1
    else:
        today = datetime.now().date()
        days_since_monday = today.weekday()
        last_monday = today - timedelta(days=days_since_monday + 7)
        start_date = last_monday

    end_date = start_date + timedelta(days=6)

    click.echo(f"📊 Создание недельного rollup за {start_date} - {end_date}...")

    if verbose:
        click.echo(f"   Неделя: {start_date} - {end_date}")
        if output:
            click.echo(f"   Выходной файл: {output}")

    try:
        result = pipeline.create_weekly_rollup(
            start_date=start_date,
            end_date=end_date,
            output_path=output,
        )

        if verbose:
            click.echo(f"   Обработано задач: {result.get('tasks_count', 0)}")
            click.echo(f"   Обработано событий: {result.get('events_count', 0)}")
            click.echo(f"   Создано записей: {result.get('entries_count', 0)}")

        click.echo("✅ Недельный rollup создан")
        return 0
    except Exception as exc:  # pragma: no cover - зависит от реализации pipeline
        click.echo(f"❌ Ошибка создания недельного rollup: {exc}")
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
