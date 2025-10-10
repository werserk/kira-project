"""Telegram bot gateway for Kira agent.

⚠️ WEBHOOK MODE ONLY - For FastAPI/HTTP webhook integration.

This module provides direct HTTP webhook integration for Telegram.
For long-polling mode, use TelegramAdapter + MessageHandler (event-driven).

Architecture:
    - Webhook mode (this file): Telegram → HTTP POST → TelegramGateway → AgentExecutor
    - Polling mode (kira_telegram CLI): Telegram → TelegramAdapter → EventBus → MessageHandler → AgentExecutor

Use Cases:
    - Webhook: Production deployments with public HTTPS endpoint
    - Polling: Development and environments without public URL
"""

from __future__ import annotations

import json
import uuid
from typing import Any

try:
    from fastapi import APIRouter, HTTPException, Request
    from pydantic import BaseModel
except ImportError:
    raise ImportError(
        "FastAPI dependencies not installed. Install with: poetry install --extras agent"
    ) from None

from ..observability.loguru_config import get_logger, get_timing_logger
from .executor import AgentExecutor

# Loguru logger for agent operations
agent_logger = get_logger("agent")

__all__ = ["create_telegram_router", "TelegramUpdate"]


class TelegramUpdate(BaseModel):
    """Telegram update model."""

    update_id: int
    message: dict[str, Any] | None = None


class TelegramGateway:
    """Gateway between Telegram and Kira agent."""

    def __init__(self, executor: AgentExecutor, bot_token: str) -> None:
        """Initialize gateway.

        Parameters
        ----------
        executor
            Agent executor
        bot_token
            Telegram bot token
        """
        self.executor = executor
        self.bot_token = bot_token

    def process_message(self, message: dict[str, Any]) -> str:
        """Process Telegram message.

        Parameters
        ----------
        message
            Telegram message object

        Returns
        -------
        str
            Response text
        """
        # Extract text from message
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")

        if not text:
            return "Please send a text message."

        # Create consistent session_id format for conversation memory
        session_id = f"telegram:{chat_id}"
        trace_id = f"telegram-{chat_id}-{uuid.uuid4()}"

        # Initialize timing logger for end-to-end tracking
        timing = get_timing_logger(trace_id=trace_id, component="agent")
        timing.start("e2e_telegram_to_vault", chat_id=chat_id, message_length=len(text))

        try:
            agent_logger.info(
                "Processing Telegram message",
                trace_id=trace_id,
                chat_id=chat_id,
                session_id=session_id,
                message_length=len(text),
            )

            timing.start("agent_execution", chat_id=chat_id)

            # Execute request with session_id for memory continuity
            result = self.executor.chat_and_execute(text, trace_id=trace_id, session_id=session_id)

            timing.end("agent_execution", status=result.status)

            # Check if result has natural language response (LangGraph)
            if hasattr(result, "response") and result.response:
                # LangGraph ExecutionResult with NL response - use it directly!
                response = result.response

                timing.end("e2e_telegram_to_vault", success=True, response_length=len(response))
                timing.log_summary()

                agent_logger.info(
                    "Message processing completed successfully",
                    trace_id=trace_id,
                    chat_id=chat_id,
                    response_length=len(response),
                )

                return response

            # Legacy ExecutionResult - format manually
            if result.status == "ok":
                # Format response
                if result.results:
                    response_parts = []
                    for i, step_result in enumerate(result.results, 1):
                        if step_result.get("status") == "ok":
                            data = step_result.get("data", {})
                            response_parts.append(f"✅ Step {i}: Success")
                            if data:
                                # Show limited data to avoid overwhelming user
                                summary = str(data)[:200]
                                response_parts.append(f"   {summary}")
                        else:
                            error = step_result.get("error", "Unknown error")
                            response_parts.append(f"❌ Step {i}: {error}")

                    response = "\n".join(response_parts)
                else:
                    response = "✅ Request completed successfully"

                timing.end("e2e_telegram_to_vault", success=True, response_length=len(response))
                timing.log_summary()

                return response
            else:
                timing.end("e2e_telegram_to_vault", success=False, error=result.error)
                timing.log_summary()

                agent_logger.error(
                    "Message processing failed",
                    trace_id=trace_id,
                    chat_id=chat_id,
                    error=result.error,
                )

                return f"❌ Error: {result.error}"

        except Exception as e:
            timing.end("e2e_telegram_to_vault", success=False, error=str(e))
            timing.log_summary()

            agent_logger.error(
                "Exception during message processing",
                trace_id=trace_id,
                chat_id=chat_id,
                error=str(e),
            )

            return f"❌ Error processing request: {str(e)}"


def create_telegram_router(executor: AgentExecutor, bot_token: str) -> APIRouter:
    """Create FastAPI router for Telegram webhook.

    Parameters
    ----------
    executor
        Agent executor
    bot_token
        Telegram bot token

    Returns
    -------
    APIRouter
        Configured FastAPI router
    """
    router = APIRouter(prefix="/telegram", tags=["telegram"])
    gateway = TelegramGateway(executor, bot_token)

    @router.post("/webhook")
    async def webhook(request: Request) -> dict[str, str]:
        """Handle Telegram webhook."""
        try:
            data = await request.json()
            update = TelegramUpdate(**data)

            if update.message:
                response_text = gateway.process_message(update.message)

                # In production, send response back to Telegram API
                # For now, just return it
                return {
                    "status": "ok",
                    "response": response_text,
                    "chat_id": update.message.get("chat", {}).get("id"),
                }

            return {"status": "ok", "message": "No message to process"}

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    @router.get("/health")
    def health() -> dict[str, str]:
        """Health check for Telegram gateway."""
        return {"status": "ok", "gateway": "telegram"}

    return router
