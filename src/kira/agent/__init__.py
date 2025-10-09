"""Kira Agent module.

Provides NL → Plan → Dry-Run → Execute → Verify workflow with LLM integration.

Phase 1: LangGraph integration available with LangGraphExecutor.
"""

from .config import AgentConfig
from .executor import AgentExecutor, ExecutionPlan, ExecutionResult
from .service import create_agent_app
from .tools import AgentTool, ToolRegistry

# Phase 1: LangGraph components (optional, requires langgraph extras)
try:
    from .graph import AgentGraph, build_agent_graph
    from .langgraph_executor import LangGraphExecutor
    from .state import AgentState, Budget, ContextFlags

    _LANGGRAPH_AVAILABLE = True
except ImportError:
    _LANGGRAPH_AVAILABLE = False
    LangGraphExecutor = None  # type: ignore
    AgentState = None  # type: ignore
    Budget = None  # type: ignore
    ContextFlags = None  # type: ignore
    build_agent_graph = None  # type: ignore
    AgentGraph = None  # type: ignore

__all__ = [
    "AgentConfig",
    "AgentExecutor",
    "ExecutionPlan",
    "ExecutionResult",
    "AgentTool",
    "ToolRegistry",
    "create_agent_app",
    # Phase 1 LangGraph
    "LangGraphExecutor",
    "AgentState",
    "Budget",
    "ContextFlags",
    "build_agent_graph",
    "AgentGraph",
]
