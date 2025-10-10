# 018: Chat Mode & Progress Updates

**Date**: 2025-10-10
**Status**: ✅ **IMPLEMENTED**

---

## 📋 Problem Statement

Two UX issues were identified:

### 1. Generic "Думаю..." Indicator
- User sees only animated "Думаю..." while Kira works
- No visibility into **what exactly** is happening:
  - "Получаю список задач..."
  - "Удаляю задачу..."
  - "Создаю задачу..."
- Feels like a black box

### 2. No Casual Conversation Support
- Every message triggers tool calls
- Can't just chat with Kira:
  - "Привет!"
  - "Как дела?"
  - "Спасибо!"
  - "Что ты умеешь?"
- Forces unnecessary tool executions

---

## 🎯 Solution

### 1. Progress Updates 📊

**Architecture**:
```
MessageHandler
  ↓ creates ThinkingIndicator
  ↓ passes indicator.update_status as callback
  ↓
UnifiedExecutor.chat_and_execute(progress_callback=...)
  ↓
LangGraphExecutor.execute(progress_callback=...)
  ↓ stores in AgentState
  ↓
tool_node() → calls progress_callback("Удаляю задачу...")
  ↓
ThinkingIndicator.update_status() → edits Telegram message
```

**User sees**:
```
"Получаю список задач..." (while task_list executes)
"Удаляю задачу..." (while task_delete executes)
"Создаю задачу..." (while task_create executes)
```

**Implementation**:

1. **Enhanced `ThinkingIndicator`** (`src/kira/adapters/telegram/adapter.py`):
   - Added `update_status(text: str)` method
   - Stops animation when custom status is set
   - Edits message in real-time

2. **Added `progress_callback` to `AgentState`** (`src/kira/agent/state.py`):
   ```python
   progress_callback: Any = None  # Optional callback(status: str) -> None
   ```

3. **Created `_get_tool_status_text()` helper** (`src/kira/agent/nodes.py`):
   - Maps tool names to human-readable Russian text
   - Example: `task_delete` → `"Удаляю задачу..."`

4. **Updated `tool_node()`** (`src/kira/agent/nodes.py`):
   - Calls `progress_callback` before executing each tool
   - Gracefully handles callback failures

5. **Added `progress_callback` parameter to execution chain**:
   - `LangGraphExecutor.execute()` - accepts callback
   - `UnifiedExecutor.chat_and_execute()` - passes it through
   - `MessageHandler.handle_message_received()` - connects indicator

### 2. Chat Mode 💬

**LLM Decision Making**:
```
User: "Привет!"
  ↓
plan_node() → LLM decides: "No tools needed, just chat"
  ↓
Returns empty tool_calls
  ↓
route_node() → routes to respond_node (no tools to execute)
  ↓
respond_node() → generates friendly response
```

**Implementation**:

Updated `plan_node` system prompt (`src/kira/agent/nodes.py`):
```python
💬 CHAT vs TOOLS - You decide:
- If user just wants to TALK (greetings, questions, thanks) →
  Don't call ANY tools, go straight to response
- If user wants to DO something (create, delete, list, update) →
  Call appropriate tools

Examples:
- "Привет!" → No tools, just friendly response
- "Как дела?" → No tools, casual chat
- "Что ты умеешь?" → No tools, explain capabilities
- "Спасибо!" → No tools, acknowledge
- "Покажи задачи" → Call task_list()
- "Удали задачу X" → Call task_list() then task_delete()
```

**Key Insight**: LLM already has capability to return zero tool calls (for "task completed" scenarios). We just needed to **explicitly instruct** it to use this for conversations.

---

## 📊 Status Mappings

```python
{
    "task_list": "Получаю список задач...",
    "task_get": "Получаю информацию о задаче...",
    "task_create": "Создаю задачу...",
    "task_update": "Обновляю задачу...",
    "task_delete": "Удаляю задачу...",
    "rollup_daily": "Генерирую дневной отчёт...",
    "inbox_normalize": "Обрабатываю входящие...",
}
```

Default fallback: `f"Выполняю {tool_name}..."`

---

## 🔄 Data Flow

### Progress Updates Flow

```
User sends: "Delete task X"
  ↓
MessageHandler: Creates thinking_indicator
  ↓
MessageHandler: Passes indicator.update_status as progress_callback
  ↓
LangGraphExecutor: Stores callback in AgentState
  ↓
plan_node: Decides to call task_list, then task_delete
  ↓
tool_node (step 1):
  - Calls progress_callback("Получаю список задач...")
  - Telegram shows: "Получаю список задач..."
  - Executes task_list()
  ↓
tool_node (step 2):
  - Calls progress_callback("Удаляю задачу...")
  - Telegram shows: "Удаляю задачу..."
  - Executes task_delete()
  ↓
respond_node: Generates final response
  ↓
MessageHandler: Deletes indicator, sends final message
```

### Chat Mode Flow

```
User sends: "Привет!"
  ↓
plan_node:
  - LLM recognizes this as casual chat
  - Returns empty tool_calls list
  ↓
route_node:
  - Sees empty plan
  - Routes to respond_node (skips tool execution)
  ↓
respond_node:
  - Generates friendly greeting
  - Returns to user
```

---

## ✅ Testing Scenarios

### Progress Updates

**Scenario 1: Single Tool**
```
User: "Покажи задачи"
Expected:
  1. "Получаю список задач..." (animated)
  2. [list of tasks] (final response)
```

**Scenario 2: Multi-Step**
```
User: "Удали задачу X"
Expected:
  1. "Получаю список задач..." (animated)
  2. "Удаляю задачу..." (animated)
  3. "Задача удалена" (final response)
```

**Scenario 3: Parallel Execution**
```
User: "Удали все задачи"
Expected:
  1. "Получаю список задач..." (animated)
  2. "Удаляю задачу..." (animated, multiple times in quick succession)
  3. "Удалено N задач" (final response)
```

### Chat Mode

**Scenario 1: Greeting**
```
User: "Привет!"
Expected:
  - No tool calls
  - Direct friendly response
  - No "Получаю..." messages
```

**Scenario 2: Question**
```
User: "Что ты умеешь?"
Expected:
  - No tool calls
  - Explanation of capabilities
```

**Scenario 3: Thanks**
```
User: "Спасибо!"
Expected:
  - No tool calls
  - Acknowledgment
```

**Scenario 4: Mixed (Action)**
```
User: "Создай задачу: купить молоко"
Expected:
  - Calls task_create
  - Shows "Создаю задачу..." progress
  - Confirms creation
```

---

## 🎨 User Experience

### Before

```
User: "Delete all tasks"
Telegram: "Думаю.." (20 seconds of waiting)
Telegram: "Удалено 12 задач"
```

**Problems**:
- No feedback on progress
- User doesn't know if it's working
- Feels unresponsive

### After

```
User: "Delete all tasks"
Telegram: "Получаю список задач..." (2 seconds)
Telegram: "Удаляю задачу..." (15 seconds, updates per task)
Telegram: "Удалено 12 задач"
```

**Benefits**:
- ✅ Clear progress indication
- ✅ User knows system is working
- ✅ Feels responsive and transparent

---

## 🔧 Implementation Details

### Thread Safety

`ThinkingIndicator` uses thread-safe design:
- `update_status()` can be called from any thread
- `_animate()` checks `_custom_text` before updating
- Telegram API calls are atomic (httpx is thread-safe)

### Error Handling

```python
if state.progress_callback:
    status_text = _get_tool_status_text(tool_name, args)
    try:
        state.progress_callback(status_text)
    except Exception as e:
        logger.warning(f"Progress callback failed: {e}")
        # Continue execution - don't block on UI updates
```

**Design principle**: Progress updates are **best-effort**, execution continues even if callback fails.

### Backwards Compatibility

- `progress_callback` is **optional** in all methods
- Works with non-Telegram adapters (callback is None)
- No breaking changes to existing code

---

## 📈 Benefits

### Progress Updates
1. **Transparency**: User sees what's happening
2. **Perceived Performance**: Feels faster with feedback
3. **Debuggability**: Easier to identify slow operations
4. **Trust**: User knows system is working

### Chat Mode
1. **Natural Interaction**: Can talk casually
2. **Efficiency**: No wasted tool calls
3. **User-Friendly**: More human-like
4. **Flexibility**: Mix actions and chat

---

## 🚀 Future Enhancements

### Short-term
1. **More detailed statuses**:
   - "Удаляю задачу 'Buy milk'..." (include task title)
   - "Создаю задачу 3 из 5..." (show progress)

2. **Emoji indicators**:
   - 📋 "Получаю список задач..."
   - 🗑️ "Удаляю задачу..."
   - ✨ "Создаю задачу..."

### Medium-term
3. **Progress bars** for batch operations:
   - "Удаляю задачи: [████████--] 8/10"

4. **Time estimates**:
   - "Генерирую отчёт... (~30 сек)"

### Long-term
5. **Streaming responses**:
   - Real-time text generation
   - Character-by-character updates

6. **Rich media**:
   - Inline buttons during execution
   - Ability to cancel long operations

---

## 📊 Modified Files

### Core Changes
1. `src/kira/adapters/telegram/adapter.py`:
   - Added `update_status()` to `ThinkingIndicator`
   - Modified `_animate()` to respect custom text

2. `src/kira/agent/state.py`:
   - Added `progress_callback: Any` field

3. `src/kira/agent/nodes.py`:
   - Added `_get_tool_status_text()` helper
   - Updated `tool_node()` to call progress_callback
   - Updated `plan_node` system prompt for chat mode

### Integration
4. `src/kira/agent/langgraph_executor.py`:
   - Added `progress_callback` parameter to `execute()`
   - Passes callback to `AgentState`

5. `src/kira/agent/unified_executor.py`:
   - Added `progress_callback` parameter to `chat_and_execute()`
   - Forwards to `LangGraphExecutor.execute()`

6. `src/kira/agent/message_handler.py`:
   - Extracts `indicator.update_status` as callback
   - Passes to `executor.chat_and_execute()`

---

## ✅ Summary

Two **high-impact UX improvements** with minimal architectural changes:

1. **Progress Updates** 📊:
   - Users see real-time status of what Kira is doing
   - Transparent, trustworthy, responsive

2. **Chat Mode** 💬:
   - Users can have casual conversations
   - No forced tool executions
   - More natural interaction

**Implementation**: ~150 lines of code
**Impact**: Significantly improved user experience
**Backwards Compatible**: Yes

---

**Author**: AI Assistant
**Date**: 2025-10-10
**Version**: 1.0
**Status**: ✅ **ACTIVE**

