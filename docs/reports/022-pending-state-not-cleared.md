# Report 022: Pending Confirmation State Not Cleared on New Request

**Date**: 2025-10-11
**Status**: Fixed
**Severity**: High
**Component**: Confirmation Flow - State Management
**Related**: Report 021

## Problem

### User Report
```
werserk (Максим Кирилюк), [10/11/25 12:50 PM]
Скинь полный список задач.

Кира, [10/11/25 12:50 PM]
Подтверди удаление: task-20251009-1123-cfb2cc5f, task-20251009-1108-960126e8.
Это действие необратимо. Уверен?
```

**Symptom**: User asks for task list, but bot responds with old confirmation question from previous interaction.

## Root Cause

After fixing Report 021 (persisting confirmation state), we introduced a new bug:

**Pending confirmation state was NOT cleared when user sent a different request!**

### The Flow

**Previous interaction:**
1. User: "Удали 2 задачи про Варю"
2. Bot: "Подтверди удаление...?"
3. State saved to DB: `pending_confirmation=True`

**New interaction (should be independent):**
1. User: "Скинь полный список задач" ← **Different request!**
2. State loaded from DB: `pending_confirmation=True` ← **Old state!**
3. `plan_node` checks for confirmation patterns
4. Doesn't find "да"/"нет", enters `else` block (line 89)
5. **❌ BUG**: Code mutates state object directly but doesn't return changes:
   ```python
   else:
       logger.warning("Ambiguous response, treating as new request")
       # These mutations are LOST!
       state.pending_confirmation = False
       state.pending_plan = []
       state.confirmation_question = ""
   # Function continues, these changes are not returned
   ```
6. LLM plans for "Скинь полный список задач"
7. BUT `respond_node` still sees `pending_confirmation=True` and old `confirmation_question`
8. Bot returns old question instead of task list ❌

### Why Direct Mutation Doesn't Work

In LangGraph, state updates must be **returned as dict**, not mutated directly:

```python
# ❌ WRONG (mutations are lost)
state.pending_confirmation = False
return {"plan": [...]}  # pending_confirmation NOT included, so not updated!

# ✅ CORRECT (explicit state update)
return {
    "plan": [...],
    "pending_confirmation": False,
    "pending_plan": [],
    "confirmation_question": "",
}
```

## Solution

### Code Changes

**File**: `src/kira/agent/nodes.py`

**1. Track clear flag** (line 54-55):
```python
# Track if we need to clear pending state
clear_pending_state = False
```

**2. Set flag instead of mutating** (line 88-91):
```python
# If ambiguous/different request, clear pending state and continue to normal planning
else:
    logger.warning(f"User sent different request, clearing pending confirmation")
    clear_pending_state = True  # Set flag instead of mutating
```

**3. Include cleared state in return** (lines 266-292):
```python
# Check if plan is empty (task completed)
if not tool_calls:
    result = {
        "plan": [],
        "memory": {**state.memory, "reasoning": reasoning},
        "status": "completed",
    }
    # Clear pending state if needed
    if clear_pending_state:
        result.update({
            "pending_confirmation": False,
            "pending_plan": [],
            "confirmation_question": "",
        })
    return result

result = {
    "plan": tool_calls,
    "memory": {**state.memory, "reasoning": reasoning},
    "status": "planned",
}
# Clear pending state if needed
if clear_pending_state:
    result.update({
        "pending_confirmation": False,
        "pending_plan": [],
        "confirmation_question": "",
    })
return result
```

### How It Works Now

**New interaction:**
1. User: "Скинь полный список задач"
2. State loaded: `pending_confirmation=True` (from DB)
3. `plan_node` checks for confirmation patterns
4. ✅ Doesn't find "да"/"нет" → sets `clear_pending_state=True`
5. ✅ LLM plans for "Скинь полный список задач" → `plan=[task_list]`
6. ✅ Return includes: `pending_confirmation=False, pending_plan=[], confirmation_question=""`
7. ✅ `LangGraphExecutor` sees `pending_confirmation=False` → clears session_state in DB
8. ✅ Bot responds with task list!

## Testing

### Manual Test Case

**Setup**: Have pending confirmation from previous request

1. User: "Удали 2 задачи"
2. Bot: "Подтверди удаление?"
3. **DON'T confirm** - send different request instead
4. User: "Скинь список задач"
5. **Expected**: Bot shows task list
6. **Previously**: Bot repeated "Подтверди удаление?"

### Database Check

```sql
-- After step 2 (pending confirmation)
SELECT * FROM session_state WHERE session_id = 'test';
-- pending_confirmation=1

-- After step 4 (different request)
SELECT * FROM session_state WHERE session_id = 'test';
-- pending_confirmation=0 OR row deleted
```

## Related Bugs

This is the **3rd bug** in confirmation flow:

1. **Report 020**: Recursion limit - route_after_reflect didn't check status
2. **Report 021**: Confirmation loop - state not persisted between requests
3. **Report 022**: State not cleared - direct mutation instead of return

All three bugs highlight the complexity of **stateful multi-turn interactions** in a stateless request/response architecture.

## Lessons Learned

### LangGraph State Management

1. **Never mutate state directly** - always return updates as dict
2. **All state changes must be explicitly returned**
3. **Partial updates are OK** - only changed fields need to be in return dict

### Stateful Flows

1. **Clearing state is as important as setting it**
2. **Consider "escape hatches"** - what if user changes their mind?
3. **User can always send unexpected input** - handle gracefully

### Testing

1. **Test "happy path" AND "interrupted path"**
2. **Test state transitions, not just final states**
3. **Multi-turn flows need integration tests, not just unit tests**

## Prevention

### Code Review Checklist

When reviewing stateful flow code:

- [ ] Are all state mutations returned in dict?
- [ ] Is state cleared when flow is interrupted?
- [ ] Are there "escape hatches" for users?
- [ ] Are edge cases (rejection, ignoring, new request) handled?

### Architecture Improvement Ideas

1. **State machine** for confirmation flow with explicit transitions
2. **Timeout** for pending confirmations (auto-clear after N minutes)
3. **Better logging** of state transitions for debugging

## Impact

### Before Fix
- User gets stuck with old confirmation question
- Only way out: restart conversation or explicitly reject
- **Very frustrating UX**

### After Fix
- User can freely change their mind
- Send any new request to cancel pending confirmation
- **Natural, flexible UX**

## Status

✅ Fixed in commit: [pending]
✅ Manually tested: Clearing works correctly
⏳ Awaiting integration tests
⏳ Awaiting deployment

---

**Key Insight**: In LangGraph, state is immutable from node perspective. All updates must flow through return values, never direct mutations. This enforces functional programming principles and prevents subtle bugs.

