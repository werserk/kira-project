# Report 023: Confirmation State Lost in respond_node

**Date**: 2025-10-11
**Status**: Fixed
**Severity**: CRITICAL
**Component**: Confirmation Flow - State Management in respond_node
**Related**: Reports 020, 021, 022

## Problem

### User Report
```
werserk (Максим Кирилюк), [10/11/25 12:57 PM]
Скинь полный список задач.

Кира, [10/11/25 12:57 PM]
Конечно! У тебя сейчас 11 активных задач:
[... task list ...]

werserk (Максим Кирилюк), [10/11/25 12:58 PM]
Удали 2 задачи про Варю

Кира, [10/11/25 12:58 PM]
Подтверди удаление: task-20251009-1123-cfb2cc5f, task-20251009-1108-960126e8.
Это действие необратимо. Уверен?

werserk (Максим Кирилюк), [10/11/25 12:58 PM]
Подтверждаю удаление

Кира, [10/11/25 12:58 PM]
Подтверди удаление: task-20251009-1123-cfb2cc5f, task-20251009-1108-960126e8.
Это действие необратимо. Уверен?  ← LOOP!
```

**Symptom**: Despite implementing Reports 021 and 022 fixes (session state persistence and state clearing), the confirmation loop bug STILL occurred. Bot asks for confirmation repeatedly, never processing user's "Подтверждаю удаление" response.

## Root Cause Analysis

### Investigation Process

After implementing Reports 021 and 022:
- ✅ Session state table created
- ✅ `get_session_state()`, `save_session_state()`, `clear_session_state()` implemented
- ✅ State loaded before execution and saved after execution
- ✅ `plan_node` properly handles confirmation with `clear_pending_state` flag

**But the bug persisted!** 🐛

### Log Analysis

Looking at logs for trace `e9551d88-053f-42b0-8eb8-deb153175c61` (user confirms deletion):

```
09:58:30.118 - Loaded session state - pending_confirmation=False, pending_plan_len=0
              ❌ WRONG! Should have been True with pending plan!

09:58:34.262 - LLM requested 2 tool calls: task_delete, task_delete
              ℹ️ LLM planned from scratch (didn't use pending_plan)

09:58:38.521 - Reflection complete: needs_confirmation=True
              ⚠️ Asking for confirmation AGAIN

09:58:38.544 - 🧹 Clearing session state (no pending confirmation)
              ❌ State shows pending_confirmation=False!
```

Looking at previous trace `d5403a84-480f-4f33-ab8d-69da59672a79` (user asks to delete):

```
09:58:09.056 - Loaded session state - pending_confirmation=False ✅ (correct, new request)
09:58:22.704 - 🧹 Clearing session state (no pending confirmation)
              ❌ WRONG! Should be 💾 SAVING with pending_confirmation=True!
```

**Key Finding**: When `reflect_node` detects destructive operations and sets `pending_confirmation=True`, the executor sees `pending_confirmation=False` at the end!

### The Smoking Gun

Checked `reflect_node` return value (lines 394-401 in nodes.py):

```python
if needs_confirmation:
    return {
        "pending_confirmation": True,  ✅ Sets correctly
        "pending_plan": state.plan,
        "confirmation_question": confirmation_question,
        "plan": [],
        "memory": {**state.memory, "reflection": reflection},
        "status": "completed",
    }
```

Checked `respond_node` return value (lines 644-649 in nodes.py):

```python
if state.pending_confirmation and state.confirmation_question:
    return {
        "response": state.confirmation_question,  ✅ Returns question
        "status": "responded",
        # ❌ MISSING: pending_confirmation
        # ❌ MISSING: pending_plan
        # ❌ MISSING: confirmation_question
    }
```

**ROOT CAUSE IDENTIFIED!**

`respond_node` does NOT include the confirmation state fields in its return dict!

### Why This Causes the Bug

In LangGraph's state management model:

1. **State updates are PARTIAL** - only fields in return dict are updated
2. **Fields NOT in return dict are UNCHANGED** - they keep their previous value

**The Flow (Buggy):**

1. `reflect_node` returns: `{"pending_confirmation": True, ...}` → State updated ✅
2. Graph routes to `respond_step`
3. `respond_node` returns: `{"response": "...", "status": "responded"}`
   - Does NOT include `pending_confirmation` ❌
   - LangGraph sees no update for these fields
   - **Fields revert to defaults!** (False, [], "")
4. `final_state.pending_confirmation = False` ❌
5. Executor calls `clear_session_state()` instead of `save_session_state()` ❌
6. Session state is NEVER saved to database!
7. Next request loads empty state → confirmation loop!

## Solution

### Code Fix

**File**: `src/kira/agent/nodes.py`

**Before** (lines 643-649):
```python
# If there's a confirmation question pending, return it directly
if state.pending_confirmation and state.confirmation_question:
    logger.info(f"[{state.trace_id}] Returning confirmation question to user")
    return {
        "response": state.confirmation_question,
        "status": "responded",
    }
```

**After** (lines 643-653):
```python
# If there's a confirmation question pending, return it directly
if state.pending_confirmation and state.confirmation_question:
    logger.info(f"[{state.trace_id}] Returning confirmation question to user")
    # CRITICAL: Must return pending_* fields to preserve confirmation state!
    return {
        "response": state.confirmation_question,
        "status": "responded",
        "pending_confirmation": True,  # Preserve confirmation state
        "pending_plan": state.pending_plan,  # Preserve pending plan
        "confirmation_question": state.confirmation_question,  # Preserve question
    }
```

### How It Works Now

**Request 1: User asks to delete tasks**

1. `plan_node` → generates deletion plan
2. `reflect_node` → detects destructive ops, returns:
   ```python
   {
       "pending_confirmation": True,
       "pending_plan": [task_delete, task_delete],
       "confirmation_question": "Подтверди удаление: ...",
       "status": "completed"
   }
   ```
3. Graph routes to `respond_step`
4. `respond_node` → ✅ NOW returns:
   ```python
   {
       "response": "Подтверди удаление: ...",
       "status": "responded",
       "pending_confirmation": True,  # ✅ Preserved!
       "pending_plan": [...],  # ✅ Preserved!
       "confirmation_question": "..."  # ✅ Preserved!
   }
   ```
5. Executor checks: `final_state.pending_confirmation == True` ✅
6. **💾 Saves session state to database!** ✅

**Request 2: User confirms**

1. ✅ Loads session state: `pending_confirmation=True`, `pending_plan=[...]`
2. `plan_node` detects confirmation: "подтверждаю" in message
3. Returns pending plan with `pending_confirmation=False`
4. Tool execution proceeds
5. Tasks deleted successfully! ✅

## Timeline of Bugs

This is the **4th bug** in the confirmation flow saga:

1. **Report 020**: Recursion limit - `route_after_reflect` didn't check status
2. **Report 021**: State not persisted - no session_state table
3. **Report 022**: State not cleared - direct mutation instead of return
4. **Report 023**: State lost in respond_node - fields not returned ← **THIS ONE**

## Testing

### Manual Test

1. Start bot
2. User: "Удали 2 задачи про Варю"
3. **Expected**: Bot asks "Подтверди удаление: ..."
4. **Verify DB**: `SELECT * FROM session_state` should show:
   - `pending_confirmation = 1`
   - `pending_plan = [...json...]`
5. User: "Подтверждаю удаление"
6. **Expected**: Bot executes deletion and confirms success
7. **Verify DB**: `SELECT * FROM session_state` should return 0 rows (cleared)

### Database Verification

```bash
# After step 3 (confirmation requested)
sqlite3 artifacts/conversations.db \
  "SELECT session_id, pending_confirmation, LENGTH(pending_plan)
   FROM session_state
   WHERE session_id = 'telegram:916542313';"
# Expected: telegram:916542313|1|123 (some length)

# After step 6 (confirmed and executed)
sqlite3 artifacts/conversations.db \
  "SELECT * FROM session_state
   WHERE session_id = 'telegram:916542313';"
# Expected: (empty result - row deleted)
```

## Lessons Learned

### LangGraph State Management Pitfalls

1. **Always return ALL fields you want to preserve**
   - If a field is NOT in return dict, it MAY be lost or reverted
   - Even if previous node set it!

2. **State flow is NOT intuitive**
   - State updates don't automatically "carry forward"
   - Each node's return is a PATCH, not a full state

3. **Debugging requires log analysis**
   - Check what's actually IN the final_state
   - Don't assume state is preserved just because it was set

### Prevention Checklist

When writing a LangGraph node that needs to preserve state from previous nodes:

- [ ] Identify which state fields from previous nodes must be preserved
- [ ] Include those fields explicitly in return dict
- [ ] Add logs to verify state is actually preserved
- [ ] Test multi-node flows end-to-end

### Why This Bug Was Subtle

- ✅ Reports 021/022 fixed the *infrastructure* (DB persistence, state management)
- ❌ But missed the *data flow* bug in `respond_node`
- The fixes were CORRECT but INCOMPLETE
- Only revealed through actual user testing with real conversation flow

## Impact

### Before Fix
- Confirmation flow completely broken
- Bot enters infinite loop asking same question
- User cannot delete tasks
- Very frustrating UX

### After Fix
- Confirmation flow works correctly
- Session state persists between requests
- User can confirm operations smoothly
- Professional, reliable UX

## Related Architecture Issues

### Consider Refactoring

The current architecture has several pain points:

1. **Implicit state dependencies** between nodes
   - Hard to track what each node expects from previous nodes
   - Easy to forget to return required fields

2. **No type checking** on return dicts
   - TypeScript would catch this at compile time
   - Python dict typing is weak for this use case

3. **Manual state management** is error-prone
   - Would benefit from explicit state machine
   - Or builder pattern for state updates

### Potential Improvements

1. **State Update Builder Pattern**:
   ```python
   return StateUpdate(state) \
       .set_response(question) \
       .set_status("responded") \
       .preserve_confirmation_state() \
       .build()
   ```

2. **Explicit State Preservation**:
   ```python
   @preserve_fields("pending_confirmation", "pending_plan", "confirmation_question")
   def respond_node(state):
       # Fields automatically included in return
       return {"response": "...", "status": "responded"}
   ```

3. **Typed State Updates**:
   ```python
   class ConfirmationState(TypedDict):
       pending_confirmation: Required[bool]
       pending_plan: Required[list]
       confirmation_question: Required[str]

   def respond_node(state) -> ConfirmationState:
       # Type checker ensures all fields returned
   ```

## Prevention Measures

### Added to Best Practices

1. ✅ **Always explicitly return state fields that must persist**
2. ✅ **Document state dependencies between nodes**
3. ✅ **Log final_state fields at graph execution end**
4. ✅ **Test multi-turn flows with state persistence**
5. ⚠️ **Consider**: Use state update helpers/builders to reduce errors

### Code Review Checklist

When reviewing LangGraph node code:

- [ ] Does this node depend on state set by previous nodes?
- [ ] Are all required state fields explicitly returned?
- [ ] Are there logs to verify state preservation?
- [ ] Is there a test covering this state flow?

## Status

✅ Fixed in commit: [pending]
✅ Tested manually: Confirmation flow works correctly
✅ Session state properly saved and loaded
⏳ Awaiting integration tests
⏳ Awaiting deployment

---

**Key Insight**: In LangGraph, state updates are **explicit and partial**. Fields not in return dict may be lost. Always return ALL fields that must persist, even if they seem redundant. This is especially critical for multi-turn flows with session state.

**The Bug in One Sentence**: `respond_node` returned only `response` and `status`, causing LangGraph to lose `pending_confirmation`, `pending_plan`, and `confirmation_question` that were set by `reflect_node`, breaking the entire confirmation flow.

