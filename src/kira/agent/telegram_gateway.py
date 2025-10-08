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
from typing import Any

try:
    from fastapi import APIRouter, HTTPException, Request
    from pydantic import BaseModel
except ImportError:
    raise ImportError(
        "FastAPI dependencies not installed. Install with: poetry install --extras agent"
    ) from None

from .executor import AgentExecutor

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

        # Use chat_id as trace_id for conversation continuity
        trace_id = f"telegram-{chat_id}"

        try:
            # Execute request
            result = self.executor.chat_and_execute(text, trace_id=trace_id)

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

                    return "\n".join(response_parts)
                else:
                    return "✅ Request completed successfully"
            else:
                return f"❌ Error: {result.error}"

        except Exception as e:
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
