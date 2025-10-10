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

    def chat_and_execute(self, user_request: str, *, trace_id: str | None = None, session_id: str | None = None) -> Any:
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

    def chat_and_execute(self, user_request: str, *, trace_id: str | None = None, session_id: str | None = None) -> Any:
        """Execute user request through underlying executor.

        Parameters
        ----------
        user_request
            User's natural language request
        trace_id
            Optional trace ID for request correlation
        session_id
            Optional session ID for conversation memory (preferred)

        Returns
        -------
        ExecutionResult
            Execution result with .response field (both executors)
        """
        logger.info(
            f"🔍 DEBUG: UnifiedExecutor.chat_and_execute() called - "
            f"executor_type={self.executor_type}, session_id={session_id}, trace_id={trace_id}"
        )
        logger.debug(f"Executing via {self.executor_type}: {user_request[:100]}...")

        # Ensure session_id exists for conversation continuity
        if session_id is None:
            import uuid

            # Generate default session_id if not provided
            session_id = f"default:{uuid.uuid4()}"
            logger.warning(f"⚠️ DEBUG: No session_id provided! Generated: {session_id}")
        else:
            logger.info(f"✅ DEBUG: Using provided session_id: {session_id}")

        if self.executor_type == ExecutorType.LANGGRAPH:
            logger.info(f"🔍 DEBUG: Delegating to LangGraphExecutor with session_id={session_id}")
            # LangGraphExecutor.execute() returns ExecutionResult with .response
            result = self.executor.execute(user_request, trace_id=trace_id, session_id=session_id)  # type: ignore[attr-defined]
            return result
        else:
            logger.info(f"🔍 DEBUG: Delegating to AgentExecutor (legacy) with session_id={session_id}")
            # AgentExecutor now also returns ExecutionResult with .response
            return self.executor.chat_and_execute(user_request, trace_id=trace_id, session_id=session_id)


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

            # Get memory config from kwargs or config
            memory_max_exchanges = kwargs.get('memory_max_exchanges', 10)
            enable_persistent_memory = kwargs.get('enable_persistent_memory', True)
            memory_db_path = kwargs.get('memory_db_path', None)

            logger.info(f"🔍 DEBUG: Initial memory config from kwargs - max={memory_max_exchanges}, persistent={enable_persistent_memory}")

            if config:
                if hasattr(config, 'memory_max_exchanges'):
                    memory_max_exchanges = config.memory_max_exchanges
                    logger.info(f"🔍 DEBUG: Override memory_max_exchanges from config: {memory_max_exchanges}")
                if hasattr(config, 'enable_persistent_memory'):
                    enable_persistent_memory = config.enable_persistent_memory
                    logger.info(f"🔍 DEBUG: Override enable_persistent_memory from config: {enable_persistent_memory}")
                if hasattr(config, 'memory_db_path'):
                    memory_db_path = config.memory_db_path
                    logger.info(f"🔍 DEBUG: Override memory_db_path from config: {memory_db_path}")

            logger.info(
                f"🔍 DEBUG: Creating LangGraph executor with: "
                f"reflection={enable_langgraph_reflection}, "
                f"verification={enable_langgraph_verification}, "
                f"max_steps={max_steps}, "
                f"memory_max_exchanges={memory_max_exchanges}, "
                f"persistent_memory={enable_persistent_memory}, "
                f"db_path={memory_db_path}"
            )

            langgraph_executor = LangGraphExecutor(
                llm_adapter,  # type: ignore[arg-type]
                tool_registry,
                max_steps=max_steps,
                enable_reflection=enable_langgraph_reflection,
                enable_verification=enable_langgraph_verification,
                memory_max_exchanges=memory_max_exchanges,
                enable_persistent_memory=enable_persistent_memory,
                memory_db_path=memory_db_path,
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
        executor=legacy_executor,
        executor_type=ExecutorType.LEGACY,
    )

