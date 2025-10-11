"""LangGraph-based executor for Kira agent.

Provides a high-level interface to the LangGraph execution engine.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..adapters.llm import LLMAdapter
    from .state import AgentState
    from .tools import ToolRegistry

logger = logging.getLogger(__name__)

__all__ = ["LangGraphExecutor", "ExecutionResult"]


class ExecutionResult:
    """Result of LangGraph execution."""

    def __init__(self, state: AgentState | dict[str, Any]) -> None:
        """Initialize from final state.

        Parameters
        ----------
        state
            Final agent state after graph execution (AgentState or dict)
        """
        # LangGraph returns dict, not dataclass
        if isinstance(state, dict):
            from .state import AgentState as StateClass
            state = StateClass.from_dict(state)

        self.state = state
        self.trace_id = state.trace_id
        self.status = state.status
        self.error = state.error
        self.tool_results = state.tool_results
        self.budget_used = state.budget
        self.response = state.response  # Natural language response

    @property
    def success(self) -> bool:
        """Check if execution was successful."""
        return self.status not in ("error", "halt") and self.error is None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "trace_id": self.trace_id,
            "status": self.status,
            "error": self.error,
            "tool_results": self.tool_results,
            "budget": self.budget_used.to_dict(),
            "success": self.success,
            "response": self.response,  # NL response for user
        }


class LangGraphExecutor:
    """LangGraph-based agent executor.

    This is the Phase 1 implementation of the LangGraph integration.
    It provides plan → reflect → tool → verify workflow with resource budgets.
    """

    def __init__(
        self,
        llm_adapter: LLMAdapter,
        tool_registry: ToolRegistry,
        *,
        max_steps: int = 10,
        max_tokens: int = 10000,
        max_wall_time: float = 300.0,
        enable_reflection: bool = True,
        enable_verification: bool = True,
        memory_max_exchanges: int = 10,
        enable_persistent_memory: bool = True,
        memory_db_path: Path | None = None,
    ) -> None:
        """Initialize LangGraph executor.

        Parameters
        ----------
        llm_adapter
            LLM adapter for planning and reflection
        tool_registry
            Registry of available tools
        max_steps
            Maximum number of tool execution steps
        max_tokens
            Maximum tokens to use
        max_wall_time
            Maximum wall time in seconds
        enable_reflection
            Enable reflection node
        enable_verification
            Enable verification node
        memory_max_exchanges
            Maximum number of conversation exchanges to keep in memory
        enable_persistent_memory
            Use persistent SQLite memory (survives restarts)
        memory_db_path
            Path to SQLite database for persistent memory
        """
        self.llm_adapter = llm_adapter
        self.tool_registry = tool_registry
        self.max_steps = max_steps
        self.max_tokens = max_tokens
        self.max_wall_time = max_wall_time
        self.enable_reflection = enable_reflection
        self.enable_verification = enable_verification

        # Conversation memory for multi-turn context
        # Can be either PersistentConversationMemory or ConversationMemory
        if enable_persistent_memory:
            from .persistent_memory import PersistentConversationMemory

            if memory_db_path is None:
                memory_db_path = Path("artifacts/conversations.db")

            self.conversation_memory: Any = PersistentConversationMemory(
                db_path=memory_db_path,
                max_exchanges=memory_max_exchanges,
            )
            logger.info(
                f"LangGraph executor initialized with PERSISTENT memory "
                f"(max_exchanges={memory_max_exchanges}, db={memory_db_path})"
            )
        else:
            from .memory import ConversationMemory

            self.conversation_memory = ConversationMemory(max_exchanges=memory_max_exchanges)
            logger.info(
                f"LangGraph executor initialized with EPHEMERAL memory "
                f"(max_exchanges={memory_max_exchanges})"
            )

        # Build graph on initialization
        from .graph import build_agent_graph

        self.graph = build_agent_graph(llm_adapter, tool_registry)

    def execute(
        self,
        user_request: str,
        *,
        trace_id: str | None = None,
        session_id: str | None = None,
        user: str = "default",
        dry_run: bool = False,
        progress_callback: Any = None,
    ) -> ExecutionResult:
        """Execute user request through LangGraph.

        This is the main entry point for LangGraph execution.
        For compatibility with UnifiedExecutor, this is called by
        UnifiedExecutor.chat_and_execute() when executor_type is LANGGRAPH.

        Parameters
        ----------
        user_request
            Natural language request
        trace_id
            Optional trace ID for correlation
        session_id
            Optional session ID for conversation memory (same for all messages in a chat)
        user
            User identifier
        dry_run
            If True, run all tools in dry-run mode

        Returns
        -------
        ExecutionResult
            Execution result with final state
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        if session_id is None:
            session_id = user  # Fallback to user ID if no session

        logger.info(f"[{trace_id}] Executing request: {user_request[:100]}... (session={session_id})")

        # DEBUG: Log memory type
        memory_type = type(self.conversation_memory).__name__
        logger.info(f"[{trace_id}] 🔍 DEBUG: Using memory type: {memory_type}")

        # Get conversation history from memory
        # IMPORTANT: Limit to 3 exchanges (6 messages) to avoid overwhelming LLM
        MAX_HISTORY_EXCHANGES = 3  # 3 user-assistant pairs = 6 messages
        try:
            conversation_history = self.conversation_memory.get_context_messages(
                session_id,
                limit=MAX_HISTORY_EXCHANGES
            )
            logger.info(
                f"[{trace_id}] 🔍 DEBUG: Loaded {len(conversation_history)} messages from memory "
                f"for session={session_id} (limited to {MAX_HISTORY_EXCHANGES} exchanges)"
            )

            # DEBUG: Log first few messages if any
            if conversation_history:
                for i, msg in enumerate(conversation_history[:4]):
                    logger.debug(f"[{trace_id}]   History[{i}]: {msg.role} - {msg.content[:50]}...")
            else:
                logger.info(f"[{trace_id}] 🔍 DEBUG: NO HISTORY FOUND for session={session_id}")

        except Exception as e:
            logger.error(f"[{trace_id}] ❌ ERROR loading conversation history: {e}", exc_info=True)
            conversation_history = []

        # Build messages list: [old context] + [new user message]
        messages = [{"role": msg.role, "content": msg.content} for msg in conversation_history]
        messages.append({"role": "user", "content": user_request})

        logger.info(
            f"[{trace_id}] 🔍 DEBUG: Building state with {len(messages)} total messages "
            f"({len(conversation_history)} from history + 1 new)"
        )

        # Load session state (for confirmation flow)
        session_state = self.conversation_memory.get_session_state(session_id)
        logger.info(
            f"[{trace_id}] 🔍 DEBUG: Loaded session state - "
            f"pending_confirmation={session_state['pending_confirmation']}, "
            f"pending_plan_len={len(session_state['pending_plan'])}"
        )

        # Create initial state
        from .state import AgentState, Budget, ContextFlags

        state = AgentState(
            trace_id=trace_id,
            session_id=session_id,
            user=user,
            messages=messages,  # Include conversation history!
            progress_callback=progress_callback,  # For UI updates
            # Restore confirmation state from session
            pending_confirmation=session_state["pending_confirmation"],
            pending_plan=session_state["pending_plan"],
            confirmation_question=session_state["confirmation_question"],
            budget=Budget(
                max_steps=self.max_steps,
                max_tokens=self.max_tokens,
                max_wall_time_seconds=self.max_wall_time,
            ),
            flags=ContextFlags(
                dry_run=dry_run,
                enable_reflection=self.enable_reflection,
                enable_verification=self.enable_verification,
            ),
        )

        # Execute graph
        # Note: AgentGraph.invoke() handles conversion from dict to AgentState
        final_state = self.graph.invoke(state)

        result = ExecutionResult(final_state)
        logger.info(f"[{trace_id}] Execution completed: success={result.success}, status={result.status}")

        # Save this exchange to conversation memory
        assistant_response = final_state.response or "Ошибка выполнения"

        logger.info(
            f"[{trace_id}] 🔍 DEBUG: Saving turn to memory - "
            f"session={session_id}, user_msg_len={len(user_request)}, "
            f"assistant_msg_len={len(assistant_response)}"
        )

        try:
            self.conversation_memory.add_turn(
                session_id,
                user_message=user_request,
                assistant_message=assistant_response
            )
            logger.info(f"[{trace_id}] ✅ Successfully saved conversation turn to memory (session={session_id})")

            # DEBUG: Verify it was saved
            verification = self.conversation_memory.get_context_messages(session_id)
            logger.info(f"[{trace_id}] 🔍 DEBUG: Verification - memory now has {len(verification)} messages")

        except Exception as e:
            logger.error(f"[{trace_id}] ❌ ERROR saving conversation turn: {e}", exc_info=True)

        # Save or clear session state (for confirmation flow)
        try:
            if final_state.pending_confirmation:
                # Save pending confirmation state
                logger.info(
                    f"[{trace_id}] 💾 Saving pending confirmation state - "
                    f"plan_len={len(final_state.pending_plan)}"
                )
                self.conversation_memory.save_session_state(
                    session_id,
                    pending_confirmation=True,
                    pending_plan=final_state.pending_plan,
                    confirmation_question=final_state.confirmation_question,
                )
            else:
                # Clear any pending confirmation state (user confirmed or rejected)
                logger.info(f"[{trace_id}] 🧹 Clearing session state (no pending confirmation)")
                self.conversation_memory.clear_session_state(session_id)

        except Exception as e:
            logger.error(f"[{trace_id}] ❌ ERROR managing session state: {e}", exc_info=True)

        return result

    def stream(
        self,
        user_request: str,
        *,
        trace_id: str | None = None,
        user: str = "default",
        dry_run: bool = False,
    ) -> Any:
        """Stream execution progress step by step.

        Parameters
        ----------
        user_request
            Natural language request
        trace_id
            Optional trace ID for correlation
        user
            User identifier
        dry_run
            If True, run all tools in dry-run mode

        Yields
        ------
        tuple[str, ExecutionResult]
            Node name and current execution result for each step
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        logger.info(f"[{trace_id}] Starting streaming execution: {user_request[:100]}...")

        # Create initial state
        from .state import AgentState, Budget, ContextFlags

        state = AgentState(
            trace_id=trace_id,
            user=user,
            messages=[{"role": "user", "content": user_request}],
            budget=Budget(
                max_steps=self.max_steps,
                max_tokens=self.max_tokens,
                max_wall_time_seconds=self.max_wall_time,
            ),
            flags=ContextFlags(
                dry_run=dry_run,
                enable_reflection=self.enable_reflection,
                enable_verification=self.enable_verification,
            ),
        )

        # Stream graph execution
        for node_name_val, updated_state in self.graph.stream(state):
            result = ExecutionResult(updated_state)
            yield node_name_val, result

    def get_graph_diagram(self) -> str:
        """Get Mermaid diagram of the execution graph.

        Returns
        -------
        str
            Mermaid diagram text
        """
        return self.graph.get_graph_visualization()

