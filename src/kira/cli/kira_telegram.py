"""CLI модуль для запуска Telegram бота"""

import os
import sys
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import click

from ..adapters.telegram.adapter import TelegramAdapter, TelegramAdapterConfig, create_telegram_adapter
from ..core.config import load_config
from ..core.events import create_event_bus
from ..core.scheduler import create_scheduler

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(
    context_settings=CONTEXT_SETTINGS,
    help="Управление Telegram ботом",
)
def cli() -> None:
    """Корневая команда telegram."""


@cli.command("start")
@click.option("--token", type=str, help="Bot token (или используйте TELEGRAM_BOT_TOKEN env)")
@click.option("--verbose", "-v", is_flag=True, help="Подробный вывод")
def start_command(token: str | None, verbose: bool) -> int:
    """Запустить Telegram бота в режиме polling."""

    try:
        config = load_config()

        if verbose:
            click.echo("🔧 Загружена конфигурация")
            click.echo(f"   Vault: {config.get('vault', {}).get('path', 'не указан')}")

        # Get token from parameter or environment
        bot_token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            click.echo("❌ Bot token не указан. Используйте --token или установите TELEGRAM_BOT_TOKEN")
            return 1

        return handle_telegram_start(config, bot_token, verbose)
    except FileNotFoundError as exc:
        click.echo(f"❌ Файл не найден: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - вывод трейсбека ниже
        click.echo(f"❌ Ошибка запуска Telegram бота: {exc}")
        if verbose:
            import traceback

            traceback.print_exc()
        return 1


@cli.command("test")
@click.option("--token", type=str, help="Bot token (или используйте TELEGRAM_BOT_TOKEN env)")
@click.option("--chat-id", type=int, required=True, help="Chat ID для тестового сообщения")
def test_command(token: str | None, chat_id: int) -> int:
    """Отправить тестовое сообщение в Telegram."""

    try:
        # Get token from parameter or environment
        bot_token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            click.echo("❌ Bot token не указан. Используйте --token или установите TELEGRAM_BOT_TOKEN")
            return 1

        click.echo(f"📤 Отправка тестового сообщения в chat {chat_id}...")

        # Create minimal adapter config
        adapter_config = TelegramAdapterConfig(
            bot_token=bot_token,
            allowed_chat_ids=[chat_id],
        )

        adapter = TelegramAdapter(adapter_config)

        # Send test message
        result = adapter.send_message(
            chat_id=chat_id,
            text="✅ Kira Telegram Bot активирован!\n\nОтправьте сообщение для теста.",
        )

        if result:
            click.echo("✅ Тестовое сообщение отправлено")
            return 0
        else:
            click.echo("❌ Не удалось отправить сообщение")
            return 1

    except Exception as exc:  # pragma: no cover - внешний API
        click.echo(f"❌ Ошибка отправки сообщения: {exc}")
        import traceback

        traceback.print_exc()
        return 1


def handle_telegram_start(
    config: dict,
    bot_token: str,
    verbose: bool,
) -> int:
    """Обработка запуска Telegram бота."""

    click.echo("🤖 Запуск Telegram бота...")

    # Get telegram config
    telegram_config = config.get("adapters", {}).get("telegram", {})

    # Parse allowed chats and users
    allowed_chat_ids = []
    whitelist_chats = telegram_config.get("whitelist_chats", [])
    if whitelist_chats:
        allowed_chat_ids = [int(chat_id) for chat_id in whitelist_chats]

    if verbose:
        click.echo(f"   Режим: {telegram_config.get('mode', 'bot')}")
        if allowed_chat_ids:
            click.echo(f"   Разрешенные чаты: {allowed_chat_ids}")
        else:
            click.echo("   Разрешенные чаты: все")

    # Create event bus and scheduler
    event_bus = create_event_bus()
    scheduler = create_scheduler()

    # Create adapter config
    adapter_config = TelegramAdapterConfig(
        bot_token=bot_token,
        allowed_chat_ids=allowed_chat_ids,
        polling_timeout=telegram_config.get("polling_timeout", 30),
        log_path=Path("logs/adapters/telegram.jsonl"),
        temp_dir=Path("tmp/telegram"),
        daily_briefing_time=telegram_config.get("daily_briefing_time", "09:00"),
    )

    # Create adapter
    adapter = create_telegram_adapter(
        config=adapter_config,
        event_bus=event_bus,
        scheduler=scheduler,
    )

    try:
        click.echo("✅ Telegram бот запущен")
        click.echo("   Нажмите Ctrl+C для остановки")

        if verbose:
            click.echo("   Режим: long polling")
            click.echo(f"   Timeout: {adapter_config.polling_timeout}s")

        # Start polling (blocks until interrupted)
        adapter.start_polling()

        return 0

    except KeyboardInterrupt:
        click.echo("\n⏹️  Остановка Telegram бота...")
        adapter.stop_polling()
        click.echo("✅ Telegram бот остановлен")
        return 0

    except Exception as exc:  # pragma: no cover - внешний API
        click.echo(f"❌ Ошибка работы бота: {exc}")
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
