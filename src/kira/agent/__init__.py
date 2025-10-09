"""Kira Agent module.

Provides NL → Plan → Dry-Run → Execute → Verify workflow with LLM integration.

Phase 1: LangGraph integration available with LangGraphExecutor.
Phase 2: Tool schemas, memory, RAG, and persistence.
Phase 3: Safety, observability, and E2E testing.
"""

from .config import AgentConfig
from .executor import AgentExecutor, ExecutionPlan, ExecutionResult
from .service import create_agent_app
from .tools import AgentTool, ToolRegistry
from .unified_executor import ExecutorType, UnifiedExecutor, create_unified_executor

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

# Phase 3: Safety, observability, and metrics
from .audit import AuditEvent, AuditLogger, create_audit_logger

# Phase 2: Tool schemas and execution
from .context_memory import ContextMemory, EntityFact, create_context_memory
from .llm_integration import LangGraphLLMBridge, create_langgraph_llm_adapter
from .metrics import HealthCheck, MetricsCollector, create_metrics_collector
from .persistence import FileStatePersistence, SQLiteStatePersistence, StatePersistence, create_persistence
from .policies import Capability, PolicyEnforcer, PolicyViolation, ToolPolicy, create_policy_enforcer
from .rag_integration import RAGIntegration, create_rag_integration
from .retry_policies import CircuitBreaker, RetryableError, RetryPolicy, create_retry_policy, with_retry
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
    # Unified Executor (Phase 1-3 integration)
    "UnifiedExecutor",
    "ExecutorType",
    "create_unified_executor",
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
    # Phase 3: Policies
    "Capability",
    "ToolPolicy",
    "PolicyEnforcer",
    "PolicyViolation",
    "create_policy_enforcer",
    # Phase 3: Retry
    "RetryPolicy",
    "RetryableError",
    "CircuitBreaker",
    "with_retry",
    "create_retry_policy",
    # Phase 3: Audit
    "AuditEvent",
    "AuditLogger",
    "create_audit_logger",
    # Phase 3: Metrics
    "HealthCheck",
    "MetricsCollector",
    "create_metrics_collector",
    # Phase 3: LLM Integration
    "LangGraphLLMBridge",
    "create_langgraph_llm_adapter",
]
