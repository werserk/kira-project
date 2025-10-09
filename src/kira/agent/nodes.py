"""LangGraph nodes for agent execution flow.

Implements the core nodes: plan, reflect, tool, verify, and route.
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .state import AgentState
    from .tools import ToolRegistry
    from ..adapters.llm import LLMAdapter, Message

logger = logging.getLogger(__name__)

__all__ = ["plan_node", "reflect_node", "tool_node", "verify_node", "route_node"]


def plan_node(state: AgentState, llm_adapter: LLMAdapter, tools_description: str) -> dict[str, Any]:
    """Planning node - generates execution plan from user request.

    Parameters
    ----------
    state
        Current agent state
    llm_adapter
        LLM adapter for generating plan
    tools_description
        Description of available tools

    Returns
    -------
    dict
        State updates with plan
    """
    logger.info(f"[{state.trace_id}] Planning phase started")
    state.status = "planning"

    # Build prompt for planning
    system_prompt = f"""You are Kira's AI planner. Generate a JSON execution plan for the user's request.

AVAILABLE TOOLS:
{tools_description}

OUTPUT FORMAT (JSON only):
{{
  "plan": ["step 1 description", "step 2 description", ...],
  "tool_calls": [
    {{"tool": "exact_tool_name", "args": {{}}, "dry_run": true/false}},
    ...
  ],
  "reasoning": "Brief explanation"
}}

RULES:
- Use EXACT tool names from the list above
- Start with dry_run=true for mutating operations
- Keep plans concise (max {state.budget.max_steps - state.budget.steps_used} steps)
- Return ONLY valid JSON, no markdown or extra text
"""

    # Get last user message
    user_message = ""
    for msg in reversed(state.messages):
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            break

    if not user_message:
        logger.warning(f"[{state.trace_id}] No user message found")
        return {"error": "No user message to plan for", "status": "error"}

    # Call LLM
    try:
        from ..adapters.llm import Message

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_message),
        ]

        response = llm_adapter.chat(messages, temperature=0.3, max_tokens=2000, timeout=30.0)

        # Update token budget
        tokens_used = response.usage.get("total_tokens", 0)
        state.budget.tokens_used += tokens_used

        # Parse plan
        plan_data = json.loads(response.content)
        logger.info(f"[{state.trace_id}] Generated plan with {len(plan_data.get('tool_calls', []))} steps")

        return {
            "plan": plan_data.get("tool_calls", []),
            "memory": {**state.memory, "reasoning": plan_data.get("reasoning", "")},
            "status": "planned",
        }

    except json.JSONDecodeError as e:
        logger.error(f"[{state.trace_id}] Failed to parse plan JSON: {e}")
        return {"error": f"Invalid plan JSON: {e}", "status": "error"}
    except Exception as e:
        logger.error(f"[{state.trace_id}] Planning failed: {e}", exc_info=True)
        return {"error": f"Planning failed: {e}", "status": "error"}


def reflect_node(state: AgentState, llm_adapter: LLMAdapter) -> dict[str, Any]:
    """Reflection node - reviews plan for safety and correctness.

    Parameters
    ----------
    state
        Current agent state
    llm_adapter
        LLM adapter for reflection

    Returns
    -------
    dict
        State updates with reflection results
    """
    logger.info(f"[{state.trace_id}] Reflection phase started")

    if not state.plan:
        logger.warning(f"[{state.trace_id}] No plan to reflect on")
        return {"status": "reflected"}

    # Build reflection prompt
    system_prompt = """You are a safety reviewer for AI agent plans. Review the plan and identify risks.

OUTPUT FORMAT (JSON only):
{
  "safe": true/false,
  "concerns": ["concern 1", "concern 2", ...],
  "revised_plan": [...],  // Only if unsafe and can be fixed
  "reasoning": "Brief explanation"
}

SAFETY CHECKS:
- No destructive operations without dry_run=true first
- No operations that could cause data loss
- FSM state transitions are valid
- Arguments are reasonable
"""

    try:
        from ..adapters.llm import Message

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=f"Review this plan:\n{json.dumps(state.plan, indent=2)}"),
        ]

        response = llm_adapter.chat(messages, temperature=0.1, max_tokens=1000, timeout=20.0)

        # Update token budget
        tokens_used = response.usage.get("total_tokens", 0)
        state.budget.tokens_used += tokens_used

        reflection = json.loads(response.content)
        is_safe = reflection.get("safe", True)

        logger.info(f"[{state.trace_id}] Reflection complete: safe={is_safe}")

        if not is_safe and reflection.get("revised_plan"):
            logger.warning(f"[{state.trace_id}] Plan revised due to safety concerns")
            return {
                "plan": reflection["revised_plan"],
                "memory": {**state.memory, "reflection": reflection},
                "status": "reflected",
            }

        return {
            "memory": {**state.memory, "reflection": reflection},
            "status": "reflected",
        }

    except Exception as e:
        logger.error(f"[{state.trace_id}] Reflection failed: {e}", exc_info=True)
        # Continue without reflection on error
        return {"status": "reflected"}


def tool_node(state: AgentState, tool_registry: ToolRegistry) -> dict[str, Any]:
    """Tool execution node - executes the current step.

    Parameters
    ----------
    state
        Current agent state
    tool_registry
        Registry of available tools

    Returns
    -------
    dict
        State updates with tool results
    """
    logger.info(f"[{state.trace_id}] Tool execution phase started (step {state.current_step})")
    state.status = "executing"

    if state.current_step >= len(state.plan):
        logger.warning(f"[{state.trace_id}] No more steps to execute")
        return {"status": "completed"}

    step = state.plan[state.current_step]
    tool_name = step.get("tool", "")
    args = step.get("args", {})
    dry_run = step.get("dry_run", False) or state.flags.dry_run

    logger.info(f"[{state.trace_id}] Executing tool: {tool_name} (dry_run={dry_run})")

    start_time = time.time()

    try:
        tool = tool_registry.get(tool_name)
        if not tool:
            available = [t.name for t in tool_registry.list_tools()]
            error_msg = f"Tool not found: {tool_name}. Available: {', '.join(available)}"
            logger.error(f"[{state.trace_id}] {error_msg}")
            return {
                "error": error_msg,
                "status": "error",
            }

        # Execute tool
        result = tool.execute(args, dry_run=dry_run)

        elapsed = time.time() - start_time
        state.budget.wall_time_used += elapsed
        state.budget.steps_used += 1

        # Add result to tool_results
        tool_result = {
            **result.to_dict(),
            "tool": tool_name,
            "step": state.current_step,
            "elapsed_ms": int(elapsed * 1000),
        }

        logger.info(
            f"[{state.trace_id}] Tool {tool_name} completed: status={result.status}, elapsed={elapsed:.2f}s"
        )

        return {
            "tool_results": state.tool_results + [tool_result],
            "current_step": state.current_step + 1,
            "status": "executed" if result.status == "ok" else "error",
            "error": result.error if result.status == "error" else None,
        }

    except Exception as e:
        logger.error(f"[{state.trace_id}] Tool execution failed: {e}", exc_info=True)
        elapsed = time.time() - start_time
        state.budget.wall_time_used += elapsed

        return {
            "error": f"Tool execution failed: {e}",
            "status": "error",
        }


def verify_node(state: AgentState, tool_registry: ToolRegistry) -> dict[str, Any]:
    """Verification node - validates execution results.

    Parameters
    ----------
    state
        Current agent state
    tool_registry
        Registry of available tools

    Returns
    -------
    dict
        State updates with verification results
    """
    logger.info(f"[{state.trace_id}] Verification phase started")
    state.status = "verifying"

    if not state.tool_results:
        logger.warning(f"[{state.trace_id}] No results to verify")
        return {"status": "verified"}

    # Simple verification: check if last operation succeeded
    last_result = state.tool_results[-1]
    if last_result.get("status") == "error":
        logger.warning(f"[{state.trace_id}] Last operation failed, verification skipped")
        return {"status": "verified"}

    # TODO: Add more sophisticated verification logic
    # - Check FSM state transitions
    # - Verify no duplicate operations
    # - Validate data integrity

    logger.info(f"[{state.trace_id}] Verification passed")
    return {"status": "verified"}


def route_node(state: AgentState) -> str:
    """Routing node - decides next step based on state.

    Parameters
    ----------
    state
        Current agent state

    Returns
    -------
    str
        Name of next node to execute
    """
    logger.debug(f"[{state.trace_id}] Routing: status={state.status}, step={state.current_step}/{len(state.plan)}")

    # Check budget
    if state.budget.is_exceeded():
        logger.warning(f"[{state.trace_id}] Budget exceeded")
        return "halt"

    # Check for errors
    if state.error or state.status == "error":
        if state.retry_count < 2:
            logger.info(f"[{state.trace_id}] Error detected, retrying (attempt {state.retry_count + 1})")
            return "plan"  # Try to replan
        else:
            logger.error(f"[{state.trace_id}] Max retries reached")
            return "halt"

    # Route based on status
    if state.status == "pending":
        return "plan"
    elif state.status == "planned":
        if state.flags.enable_reflection:
            return "reflect"
        else:
            return "tool"
    elif state.status == "reflected":
        return "tool"
    elif state.status == "executed":
        if state.flags.enable_verification:
            return "verify"
        else:
            # Check if more steps remain
            if state.current_step < len(state.plan):
                return "tool"
            else:
                return "done"
    elif state.status == "verified":
        # Check if more steps remain
        if state.current_step < len(state.plan):
            return "tool"
        else:
            return "done"
    elif state.status == "completed":
        return "done"
    else:
        logger.warning(f"[{state.trace_id}] Unknown status: {state.status}")
        return "halt"

