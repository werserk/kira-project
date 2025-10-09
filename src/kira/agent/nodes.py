"""LangGraph nodes for agent execution flow.

Implements the core nodes: plan, reflect, tool, verify, and route.
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..adapters.llm import LLMAdapter, Message
    from .state import AgentState
    from .tools import ToolRegistry

logger = logging.getLogger(__name__)

__all__ = ["plan_node", "reflect_node", "tool_node", "verify_node", "respond_node", "route_node"]


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
    {{"tool": "exact_tool_name", "args": {{}}, "dry_run": false}},
    ...
  ],
  "reasoning": "Brief explanation"
}}

RULES:
- Use EXACT tool names from the list above
- Set dry_run=false for actual execution (reflection_node will ensure safety)
- Only use dry_run=true if user explicitly asks to simulate/preview
- Keep plans concise (max {state.budget.max_steps - state.budget.steps_used} steps)
- Return ONLY valid JSON, no markdown or extra text

IMPORTANT FOR DELETIONS:
- To delete a task, you MUST first get its 'uid' from task_list
- Use task_list to find the task, then task_delete with the uid
- Example: [
    {{"tool": "task_list", "args": {{}}, "dry_run": false}},
    {{"tool": "task_delete", "args": {{"uid": "<uid_from_previous_step>"}}, "dry_run": false}}
  ]
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
- FSM state transitions are valid
- Arguments are present and have correct types
- ALLOW deletions if user explicitly requested (e.g., "удали задачу X", "delete task Y")
- BLOCK only if user intent is ambiguous (e.g., "delete all" without explicit confirmation)
- BLOCK if task_delete has no valid uid argument
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

    logger.info(f"[{state.trace_id}] Executing tool: {tool_name} (dry_run={dry_run}, args={args})")

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


def respond_node(state: AgentState, llm_adapter: LLMAdapter) -> dict[str, Any]:
    """Response generation node - creates natural language response.

    Generates a conversational, natural language response based on:
    - Original user request
    - Execution plan
    - Tool results
    - Any errors

    Parameters
    ----------
    state
        Current agent state
    llm_adapter
        LLM adapter for generating response

    Returns
    -------
    dict
        State updates with natural language response
    """
    logger.info(f"[{state.trace_id}] Response generation phase started")
    state.status = "responding"

    # Extract user request (get the LAST user message, not first!)
    user_request = ""
    if state.messages:
        # Find the last user message in the conversation
        for msg in reversed(state.messages):
            if msg.get("role") == "user":
                user_request = msg.get("content", "")
                break
        # Fallback to first message if no user role found
        if not user_request:
            user_request = state.messages[0].get("content", "")

    # Build context for response generation
    context_parts = []

    # Add execution summary
    if state.tool_results:
        context_parts.append("EXECUTION RESULTS:")
        for i, result in enumerate(state.tool_results, 1):
            tool_name = result.get("tool", "unknown")
            status = result.get("status", "unknown")
            data = result.get("data", {})
            context_parts.append(f"{i}. Tool: {tool_name}")
            context_parts.append(f"   Status: {status}")
            if data:
                context_parts.append(f"   Data: {json.dumps(data, ensure_ascii=False)}")

    # Add error if present
    if state.error:
        context_parts.append(f"\nERROR: {state.error}")

    context = "\n".join(context_parts)

    # Build prompt for natural response
    system_prompt = """Ты - Кира, дружелюбный и заботливый AI-ассистент. Общайся на "ты", тепло и по-человечески.

ВАЖНО:
- Обращайся на "ты" (не "вы")
- Будь дружелюбной, теплой, ласковой и услужливой
- НЕ используй эмодзи или смайлики - только текст
- Отвечай кратко, но информативно
- Если задача выполнена - радуйся вместе с пользователем
- Если ошибка - объясни понятно и предложи решение
- Говори на языке пользователя (русский/английский)
- Не упоминай технические детали (названия инструментов, ID)
- Будь как настоящий заботливый друг-помощник

СТИЛЬ:
✅ "Отлично, я нашла 3 задачи! Хочешь, расскажу подробнее?"
✅ "С радостью помогу! У тебя есть несколько активных задач."
❌ "Найдено 3 записи. Вы можете запросить детали."
❌ "Вот твои задачи 😊" (без эмодзи!)

Твоя цель - чтобы пользователь чувствовал теплоту и заботу через слова, а не смайлики."""

    user_prompt = f"""Пользователь спросил: "{user_request}"

{context}

Сгенерируй дружелюбный и естественный ответ на основе результатов выше. Помни - общайся на "ты" и будь теплой!"""

    try:
        from ..adapters.llm import Message

        messages: list[Message] = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]

        response = llm_adapter.chat(
            messages,
            temperature=0.8,  # Slightly higher for more natural responses
            max_tokens=500,
            timeout=15.0,
        )

        nl_response = response.content.strip()
        logger.info(f"[{state.trace_id}] Generated natural response: {nl_response[:100]}...")

        return {
            "response": nl_response,
            "status": "responded",
        }

    except Exception as e:
        logger.error(f"[{state.trace_id}] Response generation failed: {e}", exc_info=True)

        # Fallback to simple response
        fallback = "Хорошо, выполнено!" if state.error is None else f"Произошла ошибка: {state.error}"

        return {
            "response": fallback,
            "status": "responded",
        }


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
            return "respond"  # Generate NL response before done
    elif state.status == "responded":
        return "done"
    elif state.status == "completed":
        return "respond"  # Always generate NL response
    else:
        logger.warning(f"[{state.trace_id}] Unknown status: {state.status}")
        return "halt"

