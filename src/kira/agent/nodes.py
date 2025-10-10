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


def plan_node(state: AgentState, llm_adapter: LLMAdapter, tool_registry: Any) -> dict[str, Any]:
    """Planning node - generates execution plan from user request using native function calling.

    Parameters
    ----------
    state
        Current agent state
    llm_adapter
        LLM adapter for generating plan
    tool_registry
        Tool registry for converting tools to API format

    Returns
    -------
    dict
        State updates with plan
    """
    logger.info(f"[{state.trace_id}] Planning phase started (using native function calling)")
    state.status = "planning"

    # Get last user message for validation
    user_message = ""
    for msg in reversed(state.messages):
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            break

    if not user_message:
        logger.warning(f"[{state.trace_id}] No user message found")
        return {"error": "No user message to plan for", "status": "error"}

    # Build concise system prompt (no JSON instructions needed!)
    system_prompt = f"""You are Kira's AI planner. Your job is to call the right tools to accomplish the user's request.

🔄 DYNAMIC REPLANNING MODE:
- You will be called AFTER each tool execution to decide next steps
- You can see the results of previous tool executions
- Use REAL data from previous results (uids, values, etc.)
- Call one or more tools as needed
- If the task is COMPLETE, don't call any tools

⚡ PARALLEL EXECUTION:
- When you need to perform MULTIPLE INDEPENDENT operations, call ALL tools at once
- For example: deleting 3 tasks → call task_delete 3 times in ONE response
- For example: creating 2 tasks → call task_create 2 times in ONE response
- Only use sequential calls when operations DEPEND on each other

IMPORTANT RULES:
- Use EXACT tool names available to you
- Use REAL data from previous results (actual UIDs, not placeholders!)
- Keep plans concise (max {state.budget.max_steps - state.budget.steps_used} steps remaining)
- If user's request is fully satisfied, don't call any tools (task complete)
- ALWAYS prefer parallel execution when operations are independent!

EXAMPLES:

Example 1 - Delete multiple tasks (PARALLEL):
User: "Delete all tasks about project X"
After task_list returns UIDs: [task-123, task-456, task-789]
→ Call task_delete(uid="task-123"), task_delete(uid="task-456"), task_delete(uid="task-789") ALL AT ONCE

Example 2 - Create multiple tasks (PARALLEL):
User: "Create tasks: buy milk, walk dog, send email"
→ Call task_create(title="buy milk"), task_create(title="walk dog"), task_create(title="send email") ALL AT ONCE

Example 3 - Sequential (when dependent):
User: "Create a task and mark it as done"
Step 1: Call task_create(title="...")
Step 2 (after creation): Call task_update(uid=<from_step1>, status="done")
"""

    # Call LLM with native function calling API
    try:
        from ..adapters.llm import Message

        # Build messages: system prompt + FULL conversation history + previous results
        messages = [Message(role="system", content=system_prompt)]

        # Add ALL conversation history from state.messages
        for msg in state.messages:
            messages.append(Message(role=msg.get("role", "user"), content=msg.get("content", "")))

        # Add tool results as user message so LLM can see what was executed
        if state.tool_results:
            results_summary = "PREVIOUS TOOL EXECUTIONS:\n"
            for i, result in enumerate(state.tool_results, 1):
                tool_name = result.get("tool", "unknown")
                status = result.get("status", "unknown")
                data = result.get("data", {})
                error = result.get("error", "")

                results_summary += f"\n{i}. {tool_name}: {status}"
                if status == "ok" and data:
                    # Format data nicely for LLM
                    results_summary += f"\n   Result: {json.dumps(data, ensure_ascii=False, indent=2)}"
                elif status == "error" and error:
                    results_summary += f"\n   Error: {error}"

            messages.append(Message(role="user", content=results_summary))
            logger.info(f"[{state.trace_id}] 🔍 DEBUG: Added {len(state.tool_results)} previous tool results to context")

        # Get tools in API format from registry
        api_tools = tool_registry.to_api_format()

        logger.info(
            f"[{state.trace_id}] 🔍 DEBUG: Calling LLM with {len(api_tools)} tools available, "
            f"{len(messages)} messages (1 system + {len(state.messages)} conversation + "
            f"{1 if state.tool_results else 0} results)"
        )

        # Call LLM with native function calling API
        response = llm_adapter.tool_call(
            messages=messages,
            tools=api_tools,
            temperature=0.3,
            max_tokens=2000,
            timeout=30.0
        )

        # Update token budget
        tokens_used = response.usage.get("total_tokens", 0)
        state.budget.tokens_used += tokens_used

        # Process tool calls from response
        tool_calls = []
        if response.tool_calls:
            logger.info(f"[{state.trace_id}] LLM requested {len(response.tool_calls)} tool call(s)")
            for call in response.tool_calls:
                tool_calls.append({
                    "tool": call.name,
                    "args": call.arguments,
                    "dry_run": state.flags.dry_run  # Use global dry_run flag
                })
                logger.debug(f"[{state.trace_id}]  - {call.name}({call.arguments})")
        else:
            logger.info(f"[{state.trace_id}] LLM didn't request any tools - task may be complete")

        # Extract reasoning from response content (if provided)
        reasoning = response.content if response.content else "Tool execution planned"

        logger.info(f"[{state.trace_id}] Generated plan with {len(tool_calls)} steps")

        # Check if plan is empty (task completed)
        if not tool_calls:
            logger.info(f"[{state.trace_id}] Empty plan returned - task completed. Reasoning: {reasoning}")
            return {
                "plan": [],
                "memory": {**state.memory, "reasoning": reasoning},
                "status": "completed",  # This will route to respond_step
            }

        return {
            "plan": tool_calls,
            "memory": {**state.memory, "reasoning": reasoning},
            "status": "planned",
        }

    except Exception as e:
        logger.error(f"[{state.trace_id}] Planning failed: {e}", exc_info=True)
        return {
            "error": f"Planning failed: {e}",
            "status": "error",
            "plan": [],
        }


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


def _get_respond_node_system_prompt() -> str:
    """Returns the system prompt for the respond_node."""
    return """Ты - Кира, дружелюбный и заботливый AI-асситент. Общайся на "ты", тепло и по-человечески.

ВАЖНО:
- Твоя главная цель - дать максимально естественный и человечный ответ
- Обращайся на "ты" (не "вы")
- Будь дружелюбной, теплой, ласковой и услужливой
- НЕ используй эмодзи или смайлики - только текст
- Отвечай кратко, но информативно
- Если задача выполнена - радуйся вместе с пользователем
- Если ошибка - объясни понятно и предложи решение
- Говори на языке пользователя (русский/английский)
- Будь как настоящий заботливый друг-помощник

🚨 КРИТИЧЕСКИ ВАЖНО - ЧЕСТНОСТЬ И ТОЧНОСТЬ:
- НИКОГДА не выдумывай результаты выполнения!
- Если инструмент вернул ошибку - скажи об этом честно
- Если операция НЕ выполнена - не говори, что выполнена
- НЕ придумывай данные, которых нет в EXECUTION RESULTS
- Если что-то пошло не так - признай это и предложи помощь
- Лучше сказать "не получилось", чем солгать об успехе

🔍 ПРИ ОШИБКАХ - ДОБАВЛЯЙ ПОДРОБНОСТИ:
- Если ты видишь DEBUG INFO - ОБЯЗАТЕЛЬНО включи его в ответ
- Пользователь разработчик и ему нужна техническая информация
- Формат: "Извини, возникла ошибка. Вот подробности для дебага: [DEBUG INFO]"
- Не скрывай Trace ID, тип ошибки и другую техническую информацию
- Это поможет пользователю быстро найти проблему в логах

СТИЛЬ:
✅ "Отлично, я нашла 3 задачи! Хочешь, расскажу подробнее?"
✅ "С радостью помогу! У тебя есть несколько активных задач."
✅ "Хм, что-то не получилось. Вот подробности: Trace ID: xxx, Error: yyy"
✅ "Извини, возникла техническая ошибка при планировании. Trace ID: abc-123, планирование вернуло plain text вместо JSON."
❌ "Задача удалена!" (если на самом деле была ошибка)
❌ "Найдено 3 записи. Вы можете запросить детали."
❌ "Вот твои задачи 😊" (без эмодзи!)

Твоя цель - чтобы пользователь чувствовал теплоту и заботу через слова, а не смайлики.
НО главное - быть ЧЕСТНОЙ и ТОЧНОЙ в описании результатов и ПРЕДОСТАВЛЯТЬ ТЕХНИЧЕСКУЮ ИНФОРМАЦИЮ ПРИ ОШИБКАХ!"""


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

    # Build context for response generation (execution results)
    context_parts = []

    # CRITICAL: Check if we have ANY tool results
    # If not, and there's no error - this means LLM is hallucinating!
    if not state.tool_results and not state.error:
        # Вероятно, планирование провалилось
        logger.warning(f"[{state.trace_id}] ⚠️ NO TOOL RESULTS and NO ERROR - possible hallucination!")
        state.error = "Не удалось выполнить операцию (ошибка планирования)"

    # Add execution summary with clear success/failure indicators
    if state.tool_results:
        context_parts.append("Что было выполнено:")
        for i, result in enumerate(state.tool_results, 1):
            tool_name = result.get("tool", "unknown")
            status = result.get("status", "unknown")
            data = result.get("data", {})
            error = result.get("error", "")

            # Clear status indicator
            status_emoji = "✅" if status == "ok" else "❌"
            context_parts.append(f"{i}. {status_emoji} Tool: {tool_name}")
            context_parts.append(f"   Status: {status.upper()}")

            # Show data OR error (never both)
            if status == "ok" and data:
                context_parts.append(f"   Result: {json.dumps(data, ensure_ascii=False)}")
            elif status == "error" and error:
                context_parts.append(f"   ⚠️ ERROR: {error}")
                context_parts.append(f"   ⚠️ IMPORTANT: This operation FAILED - do NOT tell user it succeeded!")

    # Add global error if present
    if state.error:
        context_parts.append(f"\n🚨 GLOBAL ERROR: {state.error}")
        context_parts.append("🚨 The request was NOT completed successfully!")

        # Add detailed error information for debugging
        context_parts.append(f"\n📋 DEBUG INFO (include in response for user):")
        context_parts.append(f"   Trace ID: {state.trace_id}")
        context_parts.append(f"   Error Type: {state.error}")
        context_parts.append(f"   Steps Completed: {state.budget.steps_used}/{state.budget.max_steps}")

        if state.tool_results:
            context_parts.append(f"   Tools Executed: {len(state.tool_results)}")
            failed_tools = [r for r in state.tool_results if r.get("status") == "error"]
            if failed_tools:
                context_parts.append(f"   Failed Tools: {len(failed_tools)}")
        else:
            context_parts.append(f"   Tools Executed: 0 (planning failed)")

        # If no tools were executed, make it VERY clear
        if not state.tool_results:
            context_parts.append("\n❌ NO TOOLS WERE EXECUTED!")
            context_parts.append("❌ DO NOT use conversation history - you have NO REAL DATA!")
            context_parts.append("❌ Tell user honestly that you couldn't get the information!")
            context_parts.append("❌ PROVIDE THE DEBUG INFO ABOVE TO THE USER!")

    context = "\n".join(context_parts)

    # Build prompt for natural response
    system_prompt = _get_respond_node_system_prompt()

    try:
        from ..adapters.llm import Message

        # Build messages with FULL conversation history
        messages: list[Message] = [Message(role="system", content=system_prompt)]

        # Add ALL conversation history from state.messages
        for msg in state.messages:
            messages.append(Message(role=msg.get("role", "user"), content=msg.get("content", "")))

        # Add execution context as system message if we have results
        if context:
            messages.append(
                Message(
                    role="system",
                    content=f"""ВОТ РЕАЛЬНЫЕ РЕЗУЛЬТАТЫ ВЫПОЛНЕНИЯ ИНСТРУМЕНТОВ:

{context}

🚨 КРИТИЧЕСКИ ВАЖНО:
- Используй ТОЛЬКО информацию из результатов выше
- НЕ придумывай инструменты, которых нет в списке выше
- НЕ копируй формат результатов в свой ответ
- Если инструмент НЕ ВЫПОЛНЯЛСЯ - не говори, что он выполнился
- Сгенерируй дружелюбный и естественный ответ БЕЗ технических деталей
- Общайся на "ты" и будь теплой"""
                )
            )

        logger.info(
            f"[{state.trace_id}] 🔍 DEBUG: Calling LLM for response with {len(messages)} messages "
            f"(system + {len(state.messages)} conversation + context)"
        )

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
        if state.error:
            # Честно сообщаем об ошибке
            fallback = f"Извини, что-то пошло не так при выполнении задачи. Техническая ошибка: {state.error}"
        elif state.tool_results:
            # Есть результаты, но LLM не смог их обработать
            successful = sum(1 for r in state.tool_results if r.get("status") == "ok")
            total = len(state.tool_results)
            fallback = f"Я выполнила {successful} из {total} операций, но не могу сформулировать ответ. Попробуй спросить еще раз?"
        else:
            fallback = "Хм, не получилось выполнить задачу. Можешь попробовать переформулировать запрос?"

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
        logger.error(f"[{state.trace_id}] Error detected: {state.error}")
        # При ошибке - генерируем честный ответ пользователю
        return "respond"

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

