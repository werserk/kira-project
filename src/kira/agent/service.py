"""Kira Agent HTTP service.

FastAPI service providing:
- POST /agent/chat: NL → plan → execute
- POST /agent/execute: Execute predefined plan
- GET /health: Health check
- GET /agent/version: Version info
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
except ImportError:
    raise ImportError(
        "FastAPI dependencies not installed. Install with: poetry install --extras agent"
    ) from None

from ..adapters.llm import (
    AnthropicAdapter,
    LLMAdapter,
    LLMRouter,
    OllamaAdapter,
    OpenAIAdapter,
    OpenRouterAdapter,
    RouterConfig,
    TaskType,
)
from ..core.host import create_host_api
from .config import AgentConfig
from .executor import AgentExecutor, ExecutionPlan, ExecutionStep
from .kira_tools import RollupDailyTool, TaskCreateTool, TaskGetTool, TaskListTool, TaskUpdateTool
from .memory import ConversationMemory
from .rag import RAGStore
from .telegram_gateway import create_telegram_router
from .tools import ToolRegistry

__all__ = ["create_agent_app", "AuditLogger"]


class AuditLogger:
    """JSONL audit logger."""

    def __init__(self, audit_dir: Path) -> None:
        """Initialize audit logger.

        Parameters
        ----------
        audit_dir
            Directory for audit logs
        """
        self.audit_dir = audit_dir
        self.audit_dir.mkdir(parents=True, exist_ok=True)

    def log(self, event: dict[str, Any]) -> None:
        """Log event to JSONL.

        Parameters
        ----------
        event
            Event to log
        """
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        log_file = self.audit_dir / f"audit-{today}.jsonl"

        event["timestamp"] = datetime.now(UTC).isoformat()

        with log_file.open("a") as f:
            f.write(json.dumps(event) + "\n")


# Request/Response models
class ChatRequest(BaseModel):
    """Chat request."""

    message: str
    execute: bool = True


class ChatResponse(BaseModel):
    """Chat response."""

    status: str
    results: list[dict[str, Any]] = []
    error: str | None = None
    trace_id: str = ""


class ExecutePlanRequest(BaseModel):
    """Execute plan request."""

    steps: list[dict[str, Any]]


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: str
    version: str = "0.1.0"


def create_agent_app(config: AgentConfig | None = None) -> FastAPI:
    """Create FastAPI app for agent service.

    Parameters
    ----------
    config
        Agent configuration

    Returns
    -------
    FastAPI
        Configured FastAPI app
    """
    if config is None:
        config = AgentConfig.from_env()

    app = FastAPI(
        title="Kira Agent",
        description="NL → Plan → Dry-Run → Execute → Verify",
        version="0.1.0",
    )

    # Initialize LLM adapters for router
    anthropic_adapter = None
    if config.anthropic_api_key:
        anthropic_adapter = AnthropicAdapter(
            api_key=config.anthropic_api_key,
            default_model=config.anthropic_default_model,
        )

    openai_adapter = None
    if config.openai_api_key:
        openai_adapter = OpenAIAdapter(
            api_key=config.openai_api_key,
            default_model=config.openai_default_model,
        )

    openrouter_adapter = None
    if config.openrouter_api_key:
        openrouter_adapter = OpenRouterAdapter(
            api_key=config.openrouter_api_key,
            default_model=config.openrouter_default_model,
        )

    ollama_adapter = None
    if config.enable_ollama_fallback:
        try:
            ollama_adapter = OllamaAdapter(
                base_url=config.ollama_base_url,
                default_model=config.ollama_default_model,
            )
        except Exception:
            # Ollama not available, continue without it
            pass

    # Initialize LLM Router with multi-provider support
    router_config = RouterConfig(
        planning_provider=config.planning_provider,
        structuring_provider=config.structuring_provider,
        default_provider=config.default_provider,
        enable_ollama_fallback=config.enable_ollama_fallback,
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

    # Initialize HostAPI
    if not config.vault_path:
        raise ValueError("Vault path not configured")

    host_api = create_host_api(config.vault_path)

    # Register tools
    tool_registry.register(TaskCreateTool(host_api=host_api))
    tool_registry.register(TaskUpdateTool(host_api=host_api))
    tool_registry.register(TaskGetTool(host_api=host_api))
    tool_registry.register(TaskListTool(host_api=host_api))
    tool_registry.register(RollupDailyTool(vault_path=config.vault_path))

    # Initialize RAG store for context enhancement
    rag_store = None
    if config.enable_rag:
        rag_index_path = Path(config.rag_index_path or ".rag/index.json")
        rag_store = RAGStore(rag_index_path)

    # Initialize conversation memory
    memory = ConversationMemory(max_exchanges=config.memory_max_exchanges)

    # Initialize executor with RAG and Memory
    # Note: LLMRouter implements LLMAdapter protocol with additional features
    executor = AgentExecutor(
        cast(LLMAdapter, llm_adapter),
        tool_registry,
        config,
        rag_store=rag_store,
        memory=memory,
    )

    # Initialize audit logger
    audit_dir = Path("artifacts/audit")
    audit_logger = AuditLogger(audit_dir)

    # Integrate Telegram Gateway if enabled
    if config.enable_telegram_webhook and config.telegram_bot_token:
        telegram_router = create_telegram_router(executor, config.telegram_bot_token)
        app.include_router(telegram_router)

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        """Health check endpoint with provider availability."""
        # Check adapter availability (simplified)
        status_details = {"llm_provider": config.llm_provider}

        return HealthResponse(
            status="ok",
            timestamp=datetime.now(UTC).isoformat(),
        )

    @app.get("/agent/version")
    def version() -> dict[str, str]:
        """Get version info."""
        return {
            "version": "0.2.0",
            "sprint": "2",
            "llm_provider": config.llm_provider,
            "status": "alpha",
        }

    @app.get("/metrics")
    def metrics() -> dict[str, Any]:
        """Get Prometheus-compatible metrics."""
        # In production, use prometheus_client library
        # For Sprint 2, return simple metrics
        return {
            "agent_requests_total": 0,
            "agent_requests_success": 0,
            "agent_requests_failed": 0,
            "agent_request_duration_seconds": {
                "count": 0,
                "sum": 0.0,
                "avg": 0.0,
            },
        }

    @app.post("/agent/chat", response_model=ChatResponse)
    def chat(request: ChatRequest) -> ChatResponse:
        """Handle chat request with optional execution.

        Parameters
        ----------
        request
            Chat request

        Returns
        -------
        ChatResponse
            Chat response with results
        """
        try:
            # Log request
            audit_logger.log(
                {
                    "event": "agent_chat",
                    "message": request.message,
                    "execute": request.execute,
                }
            )

            if request.execute:
                # Full execution
                result = executor.chat_and_execute(request.message)

                # Log result
                audit_logger.log(
                    {
                        "event": "agent_execute",
                        "trace_id": result.trace_id,
                        "status": result.status,
                        "results": result.results,
                    }
                )

                return ChatResponse(
                    status=result.status,
                    results=result.results,
                    error=result.error,
                    trace_id=result.trace_id,
                )
            else:
                # Plan only
                plan = executor.plan(request.message)

                return ChatResponse(
                    status="ok",
                    results=[
                        {
                            "plan": plan.plan_description,
                            "reasoning": plan.reasoning,
                            "steps": [
                                {"tool": s.tool, "args": s.args, "dry_run": s.dry_run}
                                for s in plan.steps
                            ],
                        }
                    ],
                    trace_id="plan-only",
                )

        except Exception as e:
            audit_logger.log(
                {
                    "event": "agent_error",
                    "error": str(e),
                    "message": request.message,
                }
            )
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.post("/agent/execute", response_model=ChatResponse)
    def execute_plan(request: ExecutePlanRequest) -> ChatResponse:
        """Execute predefined plan.

        Parameters
        ----------
        request
            Execute plan request

        Returns
        -------
        ChatResponse
            Execution results
        """
        try:
            # Parse steps
            steps = [
                ExecutionStep(
                    tool=step["tool"],
                    args=step.get("args", {}),
                    dry_run=step.get("dry_run", False),
                )
                for step in request.steps
            ]

            plan = ExecutionPlan(steps=steps)

            # Execute
            result = executor.execute_plan(plan)

            # Log
            audit_logger.log(
                {
                    "event": "agent_execute_plan",
                    "trace_id": result.trace_id,
                    "status": result.status,
                    "results": result.results,
                }
            )

            return ChatResponse(
                status=result.status,
                results=result.results,
                error=result.error,
                trace_id=result.trace_id,
            )

        except Exception as e:
            audit_logger.log(
                {
                    "event": "agent_execute_error",
                    "error": str(e),
                }
            )
            raise HTTPException(status_code=500, detail=str(e)) from e

    return app
