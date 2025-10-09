"""Agent state model for LangGraph integration.

Defines the state structure that flows through the agent graph.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["AgentState", "Budget", "ContextFlags"]


@dataclass
class Budget:
    """Resource budget for agent execution."""

    max_steps: int = 10
    max_tokens: int = 10000
    max_wall_time_seconds: float = 300.0
    steps_used: int = 0
    tokens_used: int = 0
    wall_time_used: float = 0.0

    def is_exceeded(self) -> bool:
        """Check if any budget limit is exceeded."""
        return (
            self.steps_used >= self.max_steps
            or self.tokens_used >= self.max_tokens
            or self.wall_time_used >= self.max_wall_time_seconds
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "max_steps": self.max_steps,
            "max_tokens": self.max_tokens,
            "max_wall_time_seconds": self.max_wall_time_seconds,
            "steps_used": self.steps_used,
            "tokens_used": self.tokens_used,
            "wall_time_used": self.wall_time_used,
        }


@dataclass
class ContextFlags:
    """Execution context flags."""

    dry_run: bool = False
    require_confirmation: bool = False
    enable_reflection: bool = True
    enable_verification: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "dry_run": self.dry_run,
            "require_confirmation": self.require_confirmation,
            "enable_reflection": self.enable_reflection,
            "enable_verification": self.enable_verification,
        }


@dataclass
class AgentState:
    """State that flows through the agent graph.

    This is the core data structure that LangGraph uses to maintain state
    across all nodes in the execution graph.
    """

    # Identity
    trace_id: str
    user: str = "default"
    session_id: str = ""

    # Conversation
    messages: list[dict[str, Any]] = field(default_factory=list)

    # Planning and execution
    plan: list[dict[str, Any]] = field(default_factory=list)
    current_step: int = 0
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    response: str = ""  # Natural language response from respond_node

    # Memory and context
    memory: dict[str, Any] = field(default_factory=dict)
    rag_snippets: list[str] = field(default_factory=list)

    # Error handling
    error: str | None = None
    retry_count: int = 0

    # Resource management
    budget: Budget = field(default_factory=Budget)
    flags: ContextFlags = field(default_factory=ContextFlags)

    # Status
    status: str = "pending"  # pending, planning, executing, verifying, responded, completed, error

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "trace_id": self.trace_id,
            "user": self.user,
            "session_id": self.session_id,
            "messages": self.messages,
            "plan": self.plan,
            "current_step": self.current_step,
            "tool_results": self.tool_results,
            "response": self.response,
            "memory": self.memory,
            "rag_snippets": self.rag_snippets,
            "error": self.error,
            "retry_count": self.retry_count,
            "budget": self.budget.to_dict(),
            "flags": self.flags.to_dict(),
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentState:
        """Create from dictionary."""
        budget_data = data.get("budget", {})
        flags_data = data.get("flags", {})

        return cls(
            trace_id=data["trace_id"],
            user=data.get("user", "default"),
            session_id=data.get("session_id", ""),
            messages=data.get("messages", []),
            plan=data.get("plan", []),
            current_step=data.get("current_step", 0),
            tool_results=data.get("tool_results", []),
            memory=data.get("memory", {}),
            rag_snippets=data.get("rag_snippets", []),
            error=data.get("error"),
            retry_count=data.get("retry_count", 0),
            budget=Budget(**budget_data) if budget_data else Budget(),
            flags=ContextFlags(**flags_data) if flags_data else ContextFlags(),
            status=data.get("status", "pending"),
        )

