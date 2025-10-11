# Report 021: Confirmation Loop Bug Fix

**Date**: 2025-10-11
**Status**: Fixed
**Severity**: Critical
**Component**: Confirmation Flow & Session State

## Problem

### User Report
```
werserk (Максим Кирилюк), [10/11/25 12:40 PM]
Удали 2 задачи про Варю

Кира, [10/11/25 12:40 PM]
Подтверди удаление: task-20251009-1123-cfb2cc5f, task-20251009-1108-960126e8.
Это действие необратимо. Уверен?

werserk (Максим Кирилюк), [10/11/25 12:40 PM]
Да

Кира, [10/11/25 12:40 PM]
Подтверди удаление: task-20251009-1123-cfb2cc5f, task-20251009-1108-960126e8.
Это действие необратимо. Уверен?

werserk (Максим Кирилюк), [10/11/25 12:40 PM]
Да

Кира, [10/11/25 12:40 PM]
Подтверди удаление: task-20251009-1123-cfb2cc5f, task-20251009-1108-960126e8.
Это действие необратимо. Уверен?
```

**Symptom**: Bot enters infinite loop asking the same confirmation question, never recognizing user's "Да" response.

## Root Cause Analysis

### The Problem

**Confirmation state was NOT persisted between requests!**

Each new request created a fresh `AgentState` with default values:
```python
# Default values in dataclass
pending_confirmation: bool = False  # ❌ Always False!
pending_plan: list = []  # ❌ Always empty!
confirmation_question: str = ""  # ❌ Always empty!
```

### Flow Breakdown

**Request 1: "Удали 2 задачи про Варю"**
1. New `AgentState` created with `pending_confirmation=False`
2. plan_node → generates deletion plan
3. reflect_node → detects destructive ops, sets:
   - `pending_confirmation=True`
   - `pending_plan=[task_delete, task_delete]`
   - `confirmation_question="Подтверди удаление..."`
   - `status="completed"`
4. ✅ (After Report 020 fix) route_after_reflect → respond_step
5. respond_node → asks "Подтверди удаление?"
6. Graph ends, **state is lost** ❌

**Request 2: User responds "Да"**
1. New `AgentState` created with `pending_confirmation=False` ❌
2. plan_node checks:
   ```python
   if state.pending_confirmation and state.pending_plan:
       # This NEVER executes because pending_confirmation=False!
   ```
3. LLM sees history, plans to delete tasks again
4. reflect_node requests confirmation again
5. respond_node asks the same question again
6. **Infinite loop!** 🔁

### Why This Happened

Unlike conversation messages (which are persisted in SQLite), the **confirmation state was ephemeral** - it only existed during a single graph execution.

```python:src/kira/agent/langgraph_executor.py (before fix)
state = AgentState(
    trace_id=trace_id,
    session_id=session_id,
    user=user,
    messages=messages,  # ✅ Loaded from persistent memory
    # ❌ NOT loaded! Always uses dataclass defaults:
    # pending_confirmation=False
    # pending_plan=[]
    # confirmation_question=""
    ...
)
```

## Solution

### Implemented: Persistent Session State (Variant 1)

Added a new table `session_state` to store confirmation state per session:

```sql
CREATE TABLE session_state (
    session_id TEXT PRIMARY KEY,
    pending_confirmation INTEGER NOT NULL DEFAULT 0,
    pending_plan TEXT,  -- JSON-encoded plan
    confirmation_question TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### Code Changes

#### 1. Extended PersistentConversationMemory

**File**: `src/kira/agent/persistent_memory.py`

Added three new methods:

```python
def save_session_state(
    session_id: str,
    pending_confirmation: bool,
    pending_plan: list[dict] | None,
    confirmation_question: str
) -> None:
    """Save session confirmation state."""

def get_session_state(session_id: str) -> dict:
    """Get session confirmation state."""

def clear_session_state(session_id: str) -> None:
    """Clear session confirmation state."""
```

#### 2. Updated LangGraphExecutor

**File**: `src/kira/agent/langgraph_executor.py`

**Before execution** (lines 228-234):
```python
# Load session state (for confirmation flow)
session_state = self.conversation_memory.get_session_state(session_id)

state = AgentState(
    ...
    # Restore confirmation state from session
    pending_confirmation=session_state["pending_confirmation"],
    pending_plan=session_state["pending_plan"],
    confirmation_question=session_state["confirmation_question"],
)
```

**After execution** (lines 292-312):
```python
# Save or clear session state (for confirmation flow)
if final_state.pending_confirmation:
    # Save pending confirmation state
    self.conversation_memory.save_session_state(
        session_id,
        pending_confirmation=True,
        pending_plan=final_state.pending_plan,
        confirmation_question=final_state.confirmation_question,
    )
else:
    # Clear any pending confirmation state
    self.conversation_memory.clear_session_state(session_id)
```

### New Flow (After Fix)

**Request 1: "Удали 2 задачи про Варю"**
1. Load session state (none exists, defaults used)
2. plan_node → generates deletion plan
3. reflect_node → requests confirmation, sets `pending_confirmation=True`
4. respond_node → asks "Подтверди удаление?"
5. **💾 Save session state to SQLite**
6. Graph ends

**Request 2: User responds "Да"**
1. **✅ Load session state from SQLite**:
   - `pending_confirmation=True`
   - `pending_plan=[task_delete, task_delete]`
2. plan_node detects pending confirmation:
   ```python
   if state.pending_confirmation and state.pending_plan:
       # ✅ NOW EXECUTES!
       if "да" in user_message.lower():
           # Restore plan and execute
           return {
               "plan": state.pending_plan,
               "pending_confirmation": False,
               ...
           }
   ```
3. Tool execution proceeds
4. Tasks deleted
5. **🧹 Clear session state** (confirmation completed)
6. Success! ✅

## Database Schema

### New Table: session_state

```sql
CREATE TABLE session_state (
    session_id TEXT PRIMARY KEY,           -- e.g., "telegram:916542313"
    pending_confirmation INTEGER NOT NULL DEFAULT 0,  -- 0=False, 1=True
    pending_plan TEXT,                     -- JSON: [{"tool": "task_delete", ...}]
    confirmation_question TEXT,            -- Question asked to user
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### Example Data

After requesting deletion:
```
session_id: telegram:916542313
pending_confirmation: 1
pending_plan: [{"tool":"task_delete","args":{"uid":"task-1"}}, ...]
confirmation_question: Подтверди удаление: task-1, task-2. Это действие необратимо. Уверен?
updated_at: 2025-10-11 12:40:00
```

After user confirms:
```
(row deleted - no pending state)
```

## Testing

### Manual Test Scenario

1. Start bot
2. User: "Удали 2 задачи про Варю"
3. **Expected**: Bot asks "Подтверди удаление: ..."
4. User: "Да"
5. **Expected**: Bot executes deletion and confirms
6. **NOT Expected**: Bot asks the same question again

### Verification

Check database:
```sql
-- After step 3 (confirmation requested)
SELECT * FROM session_state WHERE session_id = 'telegram:916542313';
-- Should return 1 row with pending_confirmation=1

-- After step 5 (user confirmed)
SELECT * FROM session_state WHERE session_id = 'telegram:916542313';
-- Should return 0 rows (state cleared)
```

## Related Issues

- **Report 020**: Recursion limit bug (fixed route_after_reflect)
  - That fix made confirmation flow work at all
  - This fix makes it work correctly across requests

- **Feature #016**: Confirmation flow for destructive operations
  - Original implementation didn't consider session persistence

## Alternatives Considered

### Variant 2: Separate session_state table (✅ CHOSEN)
- **Pros**: Clean separation, easy to query, automatic migration
- **Cons**: Extra table
- **Verdict**: Implemented

### Variant 3: Add columns to conversations table
- **Pros**: No extra table
- **Cons**: Mixing message data with state data, harder migrations
- **Verdict**: Rejected

### Variant 4: In-memory state dict
- **Pros**: Simple, fast
- **Cons**: Lost on restart, not persistent
- **Verdict**: Rejected (would break on bot restart)

## Migration

Schema update is **automatic** via `CREATE TABLE IF NOT EXISTS`.

Existing installations will:
1. Keep existing `conversations` table unchanged
2. Create new `session_state` table automatically on first run
3. No data loss, no manual migration needed

## Lessons Learned

1. **State persistence is hard**: What seems obvious (keep state between requests) must be explicitly implemented
2. **Test cross-request flows**: Single-request tests wouldn't catch this
3. **Log liberally**: DEBUG logs helped identify the exact problem quickly
4. **Dataclass defaults are tricky**: They look safe but can hide state loss

## Prevention

### Added to Best Practices

1. ✅ **Any stateful flow spanning multiple requests MUST use persistent storage**
2. ✅ **Confirmation flows are inherently multi-request and need persistence**
3. ✅ **Test multi-turn conversations in integration tests**
4. ⚠️ **Consider**: Add health check that verifies session state persistence

## Status

✅ Fixed in commit: [pending]
✅ Tested manually: Confirmation loop no longer occurs
⏳ Awaiting integration tests
⏳ Awaiting deployment

---

**Key Insight**: Stateless request handlers (like web APIs) require explicit state management for multi-turn interactions. Conversation memory solved this for messages; session state solves it for confirmation flow.

