"""Kira Agent module.

Provides NL → Plan → Dry-Run → Execute → Verify workflow with LLM integration.

Phase 1: LangGraph integration available with LangGraphExecutor.
Phase 2: Tool schemas, memory, RAG, and persistence.
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

# Phase 2: Tool schemas and execution
from .context_memory import ContextMemory, EntityFact, create_context_memory
from .persistence import (
    FileStatePersistence,
    SQLiteStatePersistence,
    StatePersistence,
    create_persistence,
)
from .rag_integration import RAGIntegration, create_rag_integration
from .tool_executor import ToolExecutor, create_tool_executor
from .tool_schemas import TOOL_SCHEMAS, validate_tool_args

__all__ = [
    # Core
    "AgentConfig",
    "AgentExecutor",
    "ExecutionPlan",
    "ExecutionResult",
    "AgentTool",
    "ToolRegistry",
    "create_agent_app",
    # Phase 1: LangGraph
    "LangGraphExecutor",
    "AgentState",
    "Budget",
    "ContextFlags",
    "build_agent_graph",
    "AgentGraph",
    # Phase 2: Tools
    "ToolExecutor",
    "create_tool_executor",
    "TOOL_SCHEMAS",
    "validate_tool_args",
    # Phase 2: Memory
    "ContextMemory",
    "EntityFact",
    "create_context_memory",
    # Phase 2: RAG
    "RAGIntegration",
    "create_rag_integration",
    # Phase 2: Persistence
    "StatePersistence",
    "FileStatePersistence",
    "SQLiteStatePersistence",
    "create_persistence",
]
