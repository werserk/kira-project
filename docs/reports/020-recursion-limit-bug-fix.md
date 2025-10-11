# Report 020: Recursion Limit Bug Fix

**Date**: 2025-10-11
**Status**: Fixed
**Severity**: Critical
**Component**: Agent Graph Routing

## Problem

### User Report
```
werserk (Максим Кирилюк), [10/11/25 12:29 PM]
Удали 2 задачи про Варю

Кира, [10/11/25 12:29 PM]
❌ Ошибка: Recursion limit of 25 reached without hitting a stop condition.
```

### Root Cause
Infinite loop in LangGraph execution caused by missing `status == "completed"` check in `route_after_reflect()` function.

## Detailed Analysis

### Flow Breakdown (trace_id: `ec43020d-c44c-456c-93cb-bcd3dcad2234`)

**Step 1-4: Normal execution**
1. User: "Удали 2 задачи про Варю"
2. `plan_node` → calls `task_list()` to get tasks
3. `tool_node` → executes, returns 11 tasks
4. `verify_node` → passes
5. `plan_node` → creates plan to delete 2 tasks

**Step 5-31: INFINITE LOOP (6 iterations)**

Each iteration:
1. **plan_node**: Generates plan with 2x `task_delete` calls
2. **route_after_plan**: Detects destructive ops → routes to `reflect_step`
3. **reflect_node**: Analyzes plan, requests confirmation, sets:
   - `pending_confirmation = True`
   - `pending_plan = [task_delete, task_delete]`
   - `plan = []` (clears plan)
   - `status = "completed"` ← expects to route to respond_step
4. **❌ route_after_reflect**: BUG HERE!
   ```python
   def route_after_reflect(state):
       if state.error or state.status == "error":
           return "respond_step"
       return "tool_step"  # ← ALWAYS returns tool_step, ignores "completed"
   ```
5. **tool_node**: Executes with empty plan (step 1)
6. **verify_node**: Passes
7. **route_after_verify**: Returns to `plan_step`
8. **🔁 Back to step 1** - loop repeats!

**Result**: After 6 iterations (~25 graph nodes), recursion limit exceeded.

### Timeline
- **09:29:00** - Request received
- **09:29:00-04** - Normal execution (task_list)
- **09:29:04-34** - Infinite loop (6 iterations)
- **09:29:34** - Recursion limit exceeded

### Impact
- **Iterations**: 6 complete cycles
- **Time wasted**: ~34 seconds
- **LLM calls**: ~12+ (excessive)
- **Token cost**: Significantly higher than normal
- **User experience**: Complete failure

## Fix

### Code Change
**File**: `src/kira/agent/graph.py:206-212`

**Before**:
```python
def route_after_reflect(state):
    """Route after reflection."""
    if state.error or state.status == "error":
        return "respond_step"
    return "tool_step"
```

**After**:
```python
def route_after_reflect(state):
    """Route after reflection."""
    if state.error or state.status == "error":
        return "respond_step"
    if state.status == "completed":
        return "respond_step"  # Confirmation needed, ask user before proceeding
    return "tool_step"
```

### Why This Works

When `reflect_node` detects destructive operations requiring confirmation:
1. Sets `status = "completed"` (line 384 in nodes.py)
2. Expects to route to `respond_step` to ask user
3. Now `route_after_reflect` correctly detects this and routes to `respond_step`
4. `respond_node` generates confirmation question
5. User responds with "да" or "нет"
6. `plan_node` processes confirmation response

### Consistency Check

All routing functions now consistently handle `status == "completed"`:

✅ `route_after_plan`:
```python
if state.status == "completed":
    return "respond_step"
```

✅ `route_after_reflect` (FIXED):
```python
if state.status == "completed":
    return "respond_step"
```

✅ `route_after_tool` → returns to `plan_step` (which handles "completed")
✅ `route_after_verify` → returns to `plan_step` (which handles "completed")

## Testing

### Manual Test Case
1. Start agent with confirmation flow enabled
2. Send: "Удали 2 задачи про Варю"
3. **Expected behavior**:
   - Agent lists tasks
   - Identifies 2 tasks about Варя
   - **Requests confirmation**: "Подтверди удаление: [tasks]. Это действие необратимо. Уверен?"
   - Waits for user response
4. **Previous behavior**: Recursion limit error after 25 iterations

### Verification
After fix, the flow should be:
```
plan → tool(task_list) → verify → plan → reflect → respond (ask confirmation) → END
```

Not:
```
plan → reflect → tool → verify → plan → reflect → tool → verify → ... × 25 → ERROR
```

## Prevention

### Why This Wasn't Caught
1. Confirmation flow is relatively new feature
2. Not covered by existing tests
3. Routing logic is complex and spread across functions

### Recommendations
1. ✅ **Add unit tests** for all routing functions with various status values
2. ✅ **Add integration test** for confirmation flow end-to-end
3. ✅ **Document status transitions** in architecture docs
4. ⚠️ **Consider** adding recursion detection/logging in graph execution

## Related Issues
- #016 - Confirmation Flow for Destructive Operations (where this bug was introduced)
- #015 - Parallel Tool Execution
- #014 - Native Function Calling Migration

## Status
✅ Fixed in commit: [pending]
⏳ Awaiting test coverage
⏳ Awaiting deployment

---

**Lesson Learned**: When adding new control flow (like confirmation), ensure ALL routing functions handle new status values correctly. Missing a single check can cause infinite loops.

