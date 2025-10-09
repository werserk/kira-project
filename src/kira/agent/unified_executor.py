"""Unified executor interface for backward compatibility.

Provides unified interface for both AgentExecutor (legacy) and LangGraphExecutor (Phase 1-3).
Allows gradual migration and A/B testing.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from pathlib import Path

    from ..adapters.llm import LLMAdapter
    from ..core.host import HostAPI
    from .config import AgentConfig
    from .executor import ExecutionResult
    from .tools import ToolRegistry

logger = logging.getLogger(__name__)

__all__ = ["UnifiedExecutor", "create_unified_executor", "ExecutorType"]


class ExecutorProtocol(Protocol):
    """Protocol for executor interface."""

    def chat_and_execute(self, user_request: str, *, trace_id: str | None = None) -> Any:
        """Execute user request."""
        ...


class ExecutorType:
    """Executor type enum."""

    LEGACY = "legacy"  # AgentExecutor (Phase 0)
    LANGGRAPH = "langgraph"  # LangGraphExecutor (Phase 1-3)


class UnifiedExecutor:
    """Unified executor wrapper.

    Provides consistent interface for both legacy AgentExecutor and LangGraphExecutor.
    Enables gradual migration and feature flagging.
    """

    def __init__(
        self,
        executor: ExecutorProtocol,
        executor_type: str = ExecutorType.LEGACY,
    ) -> None:
        """Initialize unified executor.

        Parameters
        ----------
        executor
            Underlying executor (AgentExecutor or LangGraphExecutor)
        executor_type
            Type of executor: "legacy" or "langgraph"
        """
        self.executor = executor
        self.executor_type = executor_type
        logger.info(f"Initialized unified executor with type: {executor_type}")

    def chat_and_execute(self, user_request: str, *, trace_id: str | None = None) -> Any:
        """Execute user request through underlying executor.

        Parameters
        ----------
        user_request
            User's natural language request
        trace_id
            Optional trace ID for correlation

        Returns
        -------
        ExecutionResult
            Execution result (format depends on executor type)
        """
        logger.debug(f"Executing via {self.executor_type}: {user_request[:100]}...")

        if self.executor_type == ExecutorType.LANGGRAPH:
            # LangGraphExecutor.execute() returns ExecutionResult
            result = self.executor.execute(user_request, trace_id=trace_id)  # type: ignore[attr-defined]

            # Return the ExecutionResult directly (it has .response field)
            # For LangGraph, the natural language response is in result.response
            return result
        else:
            # Legacy AgentExecutor
            return self.executor.chat_and_execute(user_request, trace_id=trace_id)


def create_unified_executor(
    *,
    llm_adapter: LLMAdapter | None = None,
    tool_registry: ToolRegistry | None = None,
    config: AgentConfig | None = None,
    host_api: HostAPI | None = None,
    vault_path: Path | None = None,
    executor_type: str = ExecutorType.LEGACY,
    # LangGraph specific options
    enable_langgraph_reflection: bool = True,
    enable_langgraph_verification: bool = True,
    max_steps: int = 10,
    **kwargs: Any,
) -> UnifiedExecutor:
    """Factory to create unified executor with automatic type selection.

    Parameters
    ----------
    llm_adapter
        LLM adapter (LLMRouter or specific adapter)
    tool_registry
        Tool registry (will be created if not provided)
    config
        Agent configuration
    host_api
        Host API for vault operations
    vault_path
        Path to vault
    executor_type
        "legacy" or "langgraph"
    enable_langgraph_reflection
        Enable reflection node in LangGraph
    enable_langgraph_verification
        Enable verification node in LangGraph
    max_steps
        Maximum steps for LangGraph
    **kwargs
        Additional arguments for executors

    Returns
    -------
    UnifiedExecutor
        Configured unified executor

    Examples
    --------
    >>> # Legacy executor (current behavior)
    >>> executor = create_unified_executor(
    ...     llm_adapter=llm_router,
    ...     tool_registry=registry,
    ...     config=config,
    ...     executor_type="legacy",
    ... )

    >>> # LangGraph executor (Phase 1-3)
    >>> executor = create_unified_executor(
    ...     llm_adapter=llm_router,
    ...     tool_registry=registry,
    ...     executor_type="langgraph",
    ...     enable_langgraph_reflection=True,
    ... )
    """
    if executor_type == ExecutorType.LANGGRAPH:
        # Create LangGraph executor (Phase 1-3)
        try:
            from .langgraph_executor import LangGraphExecutor

            if tool_registry is None:
                # Create tool registry from host_api
                if host_api and vault_path:
                    from .tool_executor import create_tool_executor

                    tool_executor = create_tool_executor(host_api, vault_path)
                    tool_registry = tool_executor.get_tool_registry()
                else:
                    raise ValueError("tool_registry or (host_api + vault_path) required for LangGraph")

            logger.info(
                f"Creating LangGraph executor: "
                f"reflection={enable_langgraph_reflection}, "
                f"verification={enable_langgraph_verification}, "
                f"max_steps={max_steps}"
            )

            langgraph_executor = LangGraphExecutor(
                llm_adapter,  # type: ignore[arg-type]
                tool_registry,
                max_steps=max_steps,
                enable_reflection=enable_langgraph_reflection,
                enable_verification=enable_langgraph_verification,
            )

            return UnifiedExecutor(
                executor=langgraph_executor,  # type: ignore[arg-type]
                executor_type=ExecutorType.LANGGRAPH,
            )

        except ImportError as e:
            logger.warning(f"LangGraph not available, falling back to legacy: {e}")
            executor_type = ExecutorType.LEGACY

    # Create legacy executor (default)
    from .executor import AgentExecutor

    if config is None:
        from .config import AgentConfig

        config = AgentConfig.from_env()

    logger.info("Creating legacy AgentExecutor")

    legacy_executor = AgentExecutor(
        llm_adapter,  # type: ignore[arg-type]
        tool_registry,  # type: ignore[arg-type]
        config,
        **kwargs,
    )

    return UnifiedExecutor(
        executor=legacy_executor,  # type: ignore[arg-type]
        executor_type=ExecutorType.LEGACY,
    )

