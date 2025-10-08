"""CLI модуль для запуска Telegram бота"""

import os
import sys
from pathlib import Path
from typing import Any, cast

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import click

# Core imports (always available)
from ..core.config import load_config
from ..core.events import create_event_bus
from ..core.host import create_host_api
from ..core.scheduler import create_scheduler

# Agent and adapter imports moved to command function (lazy loaded)

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
        # Check if required dependencies are installed
        try:
            import telegram  # python-telegram-bot

            from ..agent.config import AgentConfig  # requires FastAPI
        except ImportError as e:
            click.echo(
                f"❌ Telegram commands require additional dependencies.\n"
                f"   Install with: poetry install --extras agent\n"
                f"   Error: {e}",
                err=True,
            )
            return 1

        config = load_config()

        if verbose:
            click.echo("🔧 Загружена конфигурация")
            click.echo(f"   Vault: {config.get('vault', {}).get('path', 'не указан')}")

        # Get token from parameter or settings
        from ..config.settings import load_settings
        settings = load_settings()

        bot_token = token or settings.telegram_bot_token
        if not bot_token:
            click.echo("❌ Bot token не указан. Используйте --token или установите TELEGRAM_BOT_TOKEN в .env")
            return 1

        return handle_telegram_start(config, bot_token, verbose, settings)
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
        # Check if required dependencies are installed
        try:
            from ..adapters.telegram.adapter import TelegramAdapter, TelegramAdapterConfig
        except ImportError as e:
            click.echo(
                f"❌ Telegram commands require additional dependencies.\n"
                f"   Install with: poetry install --extras agent\n"
                f"   Error: {e}",
                err=True,
            )
            return 1

        # Get token from parameter or settings
        from ..config.settings import load_settings
        settings = load_settings()

        bot_token = token or settings.telegram_bot_token
        if not bot_token:
            click.echo("❌ Bot token не указан. Используйте --token или установите TELEGRAM_BOT_TOKEN в .env")
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
    settings: Any,
) -> int:
    """Обработка запуска Telegram бота с интеграцией Agent."""

    # Import all required agent and adapter modules
    from ..adapters.llm import (
        AnthropicAdapter,
        LLMAdapter,
        LLMRouter,
        OllamaAdapter,
        OpenAIAdapter,
        OpenRouterAdapter,
        RouterConfig,
    )
    from ..adapters.telegram.adapter import TelegramAdapter, TelegramAdapterConfig, create_telegram_adapter
    from ..agent.config import AgentConfig
    from ..agent.executor import AgentExecutor
    from ..agent.kira_tools import RollupDailyTool, TaskCreateTool, TaskGetTool, TaskListTool, TaskUpdateTool
    from ..agent.memory import ConversationMemory
    from ..agent.message_handler import create_message_handler
    from ..agent.rag import RAGStore, build_rag_index
    from ..agent.tools import ToolRegistry

    click.echo("🤖 Запуск Telegram бота с AI агентом...")

    # Get telegram config
    telegram_config = config.get("adapters", {}).get("telegram", {})
    agent_config_dict = config.get("agent", {})
    vault_config = config.get("vault", {})

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

    # === Setup Agent Components ===
    vault_path = Path(vault_config.get("path", "vault"))

    # Create AgentConfig from settings
    agent_config = AgentConfig.from_settings(settings)

    # Initialize LLM adapters
    anthropic_adapter = AnthropicAdapter(api_key=agent_config.anthropic_api_key)
    openai_adapter = OpenAIAdapter(api_key=agent_config.openai_api_key)
    openrouter_adapter = OpenRouterAdapter(api_key=agent_config.openrouter_api_key)
    ollama_adapter = OllamaAdapter()

    router_config = RouterConfig(
        primary_provider="anthropic",
        planning_provider="anthropic",
        fallback_provider="openai",
        enable_ollama_fallback=agent_config.enable_ollama_fallback,
    )

    llm_adapter = LLMRouter(
        router_config,
        anthropic_adapter=anthropic_adapter,
        openai_adapter=openai_adapter,
        openrouter_adapter=openrouter_adapter,
        ollama_adapter=ollama_adapter,
    )

    # Initialize tool registry
    tool_registry = ToolRegistry()
    host_api = create_host_api(vault_path)

    # Register tools
    tool_registry.register(TaskCreateTool(host_api=host_api))
    tool_registry.register(TaskUpdateTool(host_api=host_api))
    tool_registry.register(TaskGetTool(host_api=host_api))
    tool_registry.register(TaskListTool(host_api=host_api))
    tool_registry.register(RollupDailyTool(vault_path=vault_path))

    if verbose:
        click.echo(f"   Зарегистрировано инструментов: {len(tool_registry.list_tools())}")

    # Initialize RAG store if enabled
    rag_store = None
    if agent_config.enable_rag:
        rag_index_path = Path(agent_config.rag_index_path)
        if rag_index_path.exists():
            rag_store = RAGStore(rag_index_path)
        else:
            # Build index from vault
            rag_store = build_rag_index(vault_path, rag_index_path)
        if verbose:
            click.echo(f"   RAG индекс загружен: {len(rag_store.documents)} документов")

    # Initialize conversation memory
    memory = ConversationMemory(max_exchanges=agent_config.memory_max_exchanges)

    # Create executor
    executor = AgentExecutor(
        cast(LLMAdapter, llm_adapter),
        tool_registry,
        agent_config,
        rag_store=rag_store,
        memory=memory,
    )

    if verbose:
        click.echo("   ✅ AI Agent инициализирован")

    # === Setup Telegram Components ===

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

    # === Connect Agent to Telegram via Event Bus ===

    def send_response(source: str, chat_id: str, text: str) -> None:
        """Callback to send response back to Telegram."""
        if source == "telegram":
            adapter.send_message(int(chat_id), text)

    # Create message handler and subscribe to events
    message_handler = create_message_handler(executor, response_callback=send_response)
    event_bus.subscribe("message.received", message_handler.handle_message_received)

    if verbose:
        click.echo("   ✅ Agent подключен к Telegram через Event Bus")

    try:
        click.echo("✅ Telegram бот с AI агентом запущен")
        click.echo("   Отправьте сообщение боту для начала работы")
        click.echo("   Нажмите Ctrl+C для остановки")

        if verbose:
            click.echo("   Режим: long polling + event-driven agent")
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
