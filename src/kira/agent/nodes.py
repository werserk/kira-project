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

    # Build prompt for planning with dynamic replanning support
    system_prompt = f"""You are Kira's AI planner. Generate a JSON execution plan for the next step(s) of the user's request.

🔄 DYNAMIC REPLANNING MODE:
- You will be called AFTER each tool execution to plan the next step(s)
- You can see the results of previous tool executions
- Use REAL data from previous results, NOT placeholders
- Plan one or more steps, based on what's needed
- If the task is COMPLETE, return an empty tool_calls array []

AVAILABLE TOOLS:
{tools_description}

OUTPUT FORMAT (JSON only):
{{
  "tool_calls": [
    {{"tool": "exact_tool_name", "args": {{}}, "dry_run": false}},
    ...
  ],
  "reasoning": "Brief explanation"
}}

RULES:
- Use EXACT tool names from the list above
- Use REAL data from previous results (uids, values, etc.)
- DO NOT use placeholders like '<uid_from_previous_step>' - use actual UIDs!
- Set dry_run=false for actual execution
- Keep plans concise (max {state.budget.max_steps - state.budget.steps_used} steps remaining)
- Return ONLY valid JSON, no markdown or extra text

COMPLETION:
- If the user's request is fully satisfied, return: {{"tool_calls": [], "reasoning": "Task completed"}}
- This will trigger the natural language response generation

EXAMPLE WORKFLOW (Delete task):
1st call (no previous results):
  {{"tool_calls": [{{"tool": "task_list", "args": {{}}, "dry_run": false}}], "reasoning": "Get task list to find UIDs"}}

2nd call (after task_list returned tasks with UIDs):
  {{"tool_calls": [{{"tool": "task_delete", "args": {{"uid": "task-20251010-123456"}}, "dry_run": false}}], "reasoning": "Delete specific task using real UID from results"}}

3rd call (after successful deletion):
  {{"tool_calls": [], "reasoning": "Task deleted successfully, work complete"}}
"""

    # Get last user message for validation
    user_message = ""
    for msg in reversed(state.messages):
        if msg.get("role") == "user":
            user_message = msg.get("content", "")
            break

    if not user_message:
        logger.warning(f"[{state.trace_id}] No user message found")
        return {"error": "No user message to plan for", "status": "error"}

    # Call LLM with FULL conversation history for context
    try:
        from ..adapters.llm import Message

        # Build messages: system prompt + FULL conversation history + previous results
        messages = [Message(role="system", content=system_prompt)]

        # Add ALL conversation history from state.messages
        for msg in state.messages:
            messages.append(Message(role=msg.get("role", "user"), content=msg.get("content", "")))

        # Add tool results as assistant messages so LLM can see what was executed
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

            messages.append(Message(role="assistant", content=results_summary))
            logger.info(f"[{state.trace_id}] 🔍 DEBUG: Added {len(state.tool_results)} previous tool results to context")

        logger.info(
            f"[{state.trace_id}] 🔍 DEBUG: Calling LLM for planning with {len(messages)} messages "
            f"(1 system + {len(state.messages)} conversation + {1 if state.tool_results else 0} results)"
        )

        response = llm_adapter.chat(messages, temperature=0.3, max_tokens=2000, timeout=30.0)
        raw_content = response.content  # Store for error logging

        # Update token budget
        tokens_used = response.usage.get("total_tokens", 0)
        state.budget.tokens_used += tokens_used

        # Log raw response for debugging
        logger.debug(f"[{state.trace_id}] Raw LLM response: {raw_content[:500]}...")

        # Clean response: remove markdown code blocks if present
        content = raw_content.strip()
        if content.startswith("```json"):
            content = content[7:]  # Remove ```json
        elif content.startswith("```"):
            content = content[3:]  # Remove ```
        if content.endswith("```"):
            content = content[:-3]  # Remove closing ```
        content = content.strip()

        # Parse plan
        plan_data = json.loads(content)
        tool_calls = plan_data.get("tool_calls", [])
        reasoning = plan_data.get("reasoning", "")

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

    except json.JSONDecodeError as e:
        logger.error(f"[{state.trace_id}] Failed to parse plan JSON: {e}")
        try:
            logger.error(f"[{state.trace_id}] Raw response that failed to parse: {raw_content[:500]}")
            # Check if LLM returned plain text instead of JSON
            if not raw_content.strip().startswith("{"):
                logger.error(f"[{state.trace_id}] 🚨 LLM returned plain text instead of JSON! This is a critical prompt violation.")
        except NameError:
            logger.error(f"[{state.trace_id}] Response not available for logging")
        # При ошибке парсинга - переходим к ответу с объяснением проблемы
        return {
            "error": f"Failed to generate valid plan (LLM returned invalid JSON - possibly plain text response)",
            "status": "error",
            "plan": [],  # Пустой план
        }
    except Exception as e:
        logger.error(f"[{state.trace_id}] Planning failed: {e}", exc_info=True)
        return {
            "error": f"Planning failed: {e}",
            "status": "error",
            "plan": [],  # Пустой план
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
- Не упоминай технические детали пользователю, НО:
- Будь как настоящий заботливый друг-помощник

🚨 КРИТИЧЕСКИ ВАЖНО - ЧЕСТНОСТЬ И ТОЧНОСТЬ:
- НИКОГДА не выдумывай результаты выполнения!
- Если инструмент вернул ошибку - скажи об этом честно
- Если операция НЕ выполнена - не говори, что выполнена
- НЕ придумывай данные, которых нет в EXECUTION RESULTS
- Если что-то пошло не так - признай это и предложи помощь
- Лучше сказать "не получилось", чем солгать об успехе

СТИЛЬ:
✅ "Отлично, я нашла 3 задачи! Хочешь, расскажу подробнее?"
✅ "С радостью помогу! У тебя есть несколько активных задач."
✅ "Хм, что-то не получилось удалить задачу. Давай попробуем по-другому?"
❌ "Задача удалена!" (если на самом деле была ошибка)
❌ "Найдено 3 записи. Вы можете запросить детали."
❌ "Вот твои задачи 😊" (без эмодзи!)

Твоя цель - чтобы пользователь чувствовал теплоту и заботу через слова, а не смайлики.
НО главное - быть ЧЕСТНОЙ и ТОЧНОЙ в описании результатов!"""


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

        # If no tools were executed, make it VERY clear
        if not state.tool_results:
            context_parts.append("\n❌ NO TOOLS WERE EXECUTED!")
            context_parts.append("❌ DO NOT use conversation history - you have NO REAL DATA!")
            context_parts.append("❌ Tell user honestly that you couldn't get the information!")

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

