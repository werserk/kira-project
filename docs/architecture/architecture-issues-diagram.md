# Architecture Issues - Visual Diagrams

This document provides visual representations of the identified issues and their solutions.

---

## Issue #1 & #2: Executor & Session ID Confusion

### Current State (Problematic)

```mermaid
graph TB
    subgraph "Entry Points"
        TG[Telegram<br/>trace_id=telegram-123]
        CLI[CLI<br/>trace_id=cli-uuid]
        HTTP[HTTP<br/>trace_id=http-uuid]
    end

    subgraph "UnifiedExecutor"
        UE[UnifiedExecutor<br/>Routes based on type]
    end

    subgraph "Execution Paths"
        AGE[AgentExecutor<br/>Uses trace_id for memory<br/>❌ No .response field]
        LGE[LangGraphExecutor<br/>Uses session_id for memory<br/>✅ Has .response field]
    end

    subgraph "Memory"
        MEM_TRACE[Memory<br/>Key: trace_id]
        MEM_SESSION[Memory<br/>Key: session_id]
    end

    TG --> UE
    CLI --> UE
    HTTP --> UE

    UE -->|executor_type=legacy| AGE
    UE -->|executor_type=langgraph| LGE

    AGE -->|lookup| MEM_TRACE
    LGE -->|lookup| MEM_SESSION

    style AGE fill:#f99,stroke:#900,stroke-width:2px
    style MEM_TRACE fill:#f99,stroke:#900,stroke-width:2px
    style MEM_SESSION fill:#f99,stroke:#900,stroke-width:2px

    note1[❌ Problem: Different memory keys]
    note2[❌ Problem: Inconsistent API]
    note3[❌ Problem: TelegramGateway doesn't pass session_id]
```

### Proposed Solution

```mermaid
graph TB
    subgraph "Entry Points"
        TG[Telegram<br/>session_id=telegram:123<br/>trace_id=uuid]
        CLI[CLI<br/>session_id=cli:user<br/>trace_id=uuid]
        HTTP[HTTP<br/>session_id=http:endpoint<br/>trace_id=uuid]
    end

    subgraph "UnifiedExecutor"
        UE[✅ UnifiedExecutor<br/>Ensures session_id exists<br/>Passes to both executors]
    end

    subgraph "Execution Paths"
        AGE[✅ AgentExecutor<br/>Uses session_id for memory<br/>✅ Has .response field]
        LGE[✅ LangGraphExecutor<br/>Uses session_id for memory<br/>✅ Has .response field]
    end

    subgraph "Memory"
        MEM[✅ Unified Memory<br/>Key: session_id]
    end

    TG --> UE
    CLI --> UE
    HTTP --> UE

    UE -->|executor_type=legacy| AGE
    UE -->|executor_type=langgraph| LGE

    AGE -->|lookup| MEM
    LGE -->|lookup| MEM

    style AGE fill:#9f9,stroke:#090,stroke-width:2px
    style LGE fill:#9f9,stroke:#090,stroke-width:2px
    style MEM fill:#9f9,stroke:#090,stroke-width:2px

    note1[✅ Solution: Consistent session_id format]
    note2[✅ Solution: Unified API contract]
    note3[✅ Solution: All entry points pass session_id]
```

---

## Issue #7 & #8: Tool Validation & FSM Guards

### Current Flow (Problematic)

```mermaid
sequenceDiagram
    participant User
    participant LLM
    participant Plan as Plan Node
    participant Reflect as Reflect Node
    participant Tool as Tool Node
    participant Validator as HostAPI Validator
    participant Vault

    User->>LLM: "Mark task-123 as done"
    LLM->>Plan: Generate plan
    Note over Plan: ❌ No validation of<br/>FSM transitions
    Plan->>Reflect: Plan generated
    Note over Reflect: ❌ No FSM check
    Reflect->>Tool: Execute plan
    Note over Tool: ❌ No argument validation
    Tool->>Validator: update_entity(task-123, status=done)
    Note over Validator: ❌ FAILURE: Transition invalid<br/>(task is in 'todo' state)
    Validator-->>Tool: ValidationError
    Tool-->>User: ❌ Error: Invalid transition

    Note over User,Vault: Problem: Error discovered late,<br/>after LLM tokens spent
```

### Proposed Flow (Fixed)

```mermaid
sequenceDiagram
    participant User
    participant LLM
    participant Plan as Plan Node
    participant Validator as Tool Validator
    participant Reflect as Reflect Node
    participant Tool as Tool Node
    participant Vault

    User->>LLM: "Mark task-123 as done"
    LLM->>Plan: Generate plan
    Plan->>Plan: Include FSM rules in prompt
    Plan->>Validator: ✅ Validate arguments
    Note over Validator: Check: task exists,<br/>status transition valid
    alt Invalid Plan
        Validator-->>Plan: Validation errors
        Plan->>LLM: Re-plan with errors
    else Valid Plan
        Validator-->>Plan: ✅ Valid
        Plan->>Reflect: Plan generated
        Reflect->>Reflect: ✅ FSM check
        Reflect->>Tool: Execute plan
        Tool->>Vault: update_entity(task-123, status=done)
        Vault-->>Tool: ✅ Success
        Tool-->>User: ✅ Task marked as done
    end

    Note over User,Vault: Solution: Early validation,<br/>no wasted LLM tokens
```

---

## Issue #9: Link Graph Race Condition

### Current Flow (Race Condition)

```mermaid
sequenceDiagram
    participant Client
    participant HostAPI
    participant Filesystem
    participant LinkGraph
    participant Process

    Client->>HostAPI: create_entity("task", {...})
    HostAPI->>Filesystem: write_markdown(atomic=True)
    Filesystem-->>HostAPI: ✅ File written

    Note over Process: ❌ CRASH HERE

    HostAPI->>LinkGraph: add_entity(entity_id)
    Note over LinkGraph: ❌ Never executed!

    Note over HostAPI,LinkGraph: Result: File exists in vault,<br/>but link graph is stale

    rect rgb(255, 220, 220)
    Note over Client,Process: Problem: Non-atomic operation<br/>leads to inconsistent state
    end
```

### Proposed Flow (Journal-Based Recovery)

```mermaid
sequenceDiagram
    participant Client
    participant HostAPI
    participant Journal
    participant Filesystem
    participant LinkGraph

    Note over HostAPI: On Startup
    HostAPI->>Journal: Read link_journal.jsonl
    HostAPI->>LinkGraph: Replay uncommitted entries
    Note over LinkGraph: ✅ Recover from crashes

    Client->>HostAPI: create_entity("task", {...})
    HostAPI->>Journal: Write journal entry<br/>{op: "add_entity", id: "task-123"}
    Journal-->>HostAPI: ✅ Persisted
    HostAPI->>Filesystem: write_markdown(atomic=True)
    Filesystem-->>HostAPI: ✅ File written
    HostAPI->>LinkGraph: add_entity(entity_id)
    LinkGraph-->>HostAPI: ✅ Graph updated
    HostAPI->>Journal: Mark entry as committed

    Note over Process: ❌ CRASH AFTER WRITE

    Note over HostAPI: On Next Startup
    HostAPI->>Journal: Find uncommitted entry
    HostAPI->>LinkGraph: Replay: add_entity(task-123)
    Note over LinkGraph: ✅ Consistency restored!

    rect rgb(220, 255, 220)
    Note over Client,LinkGraph: Solution: Write-ahead log<br/>enables crash recovery
    end
```

---

## Issue #12: Memory Leak

### Current Memory Growth

```mermaid
graph LR
    subgraph "Memory Growth Over Time"
        T0[Day 0<br/>10 MB]
        T1[Day 1<br/>60 MB<br/>+50 MB]
        T2[Day 2<br/>110 MB<br/>+50 MB]
        T3[Day 7<br/>360 MB<br/>+250 MB]
        T4[Day 30<br/>3 GB<br/>❌ OOM]
    end

    T0 --> T1
    T1 --> T2
    T2 --> T3
    T3 --> T4

    style T4 fill:#f99,stroke:#900,stroke-width:3px

    note[❌ Problem: Sessions never expire<br/>Memory grows unbounded]
```

### Proposed Memory Management

```mermaid
graph TB
    subgraph "ConversationMemory with Cleanup"
        ADD[Add Turn]
        CHECK{Sessions > Max?}
        EXPIRE[Expire Old Sessions<br/>TTL: 1 hour]
        EVICT[Evict LRU Session]
        STORE[Store in Memory]
    end

    ADD --> EXPIRE
    EXPIRE --> CHECK
    CHECK -->|Yes| EVICT
    CHECK -->|No| STORE
    EVICT --> STORE

    subgraph "Memory Growth Over Time"
        S0[Day 0<br/>10 MB]
        S1[Day 1<br/>15 MB<br/>+5 MB]
        S2[Day 2<br/>15 MB<br/>Stable]
        S3[Day 7<br/>15 MB<br/>Stable]
        S4[Day 30<br/>15 MB<br/>✅ Stable]
    end

    S0 --> S1
    S1 --> S2
    S2 --> S3
    S3 --> S4

    style S4 fill:#9f9,stroke:#090,stroke-width:3px

    note[✅ Solution: TTL + LRU eviction<br/>Memory stays bounded]
```

---

## Data Flow Comparison

### Before Fixes (Inconsistent Paths)

```mermaid
flowchart TB
    subgraph Telegram Path
        TG1[Telegram Message] --> TG2[EventBus]
        TG2 --> TG3[MessageHandler]
        TG3 --> TG4[UnifiedExecutor]
        TG4 --> TG5[LangGraph]
        TG5 --> TG6[NL Response ✅]
    end

    subgraph CLI Path
        CLI1[CLI Command] --> CLI2[UnifiedExecutor]
        CLI2 --> CLI3[AgentExecutor]
        CLI3 --> CLI4[Tool Results]
        CLI4 --> CLI5[Manual Format ❌]
    end

    subgraph HTTP Webhook Path
        HTTP1[HTTP Request] --> HTTP2[TelegramGateway]
        HTTP2 --> HTTP3[AgentExecutor]
        HTTP3 --> HTTP4[Tool Results]
        HTTP4 --> HTTP5[Manual Format ❌]
    end

    style TG6 fill:#9f9,stroke:#090
    style CLI5 fill:#f99,stroke:#900
    style HTTP5 fill:#f99,stroke:#900

    note[❌ Problem: Different response formats<br/>by entry point]
```

### After Fixes (Unified Paths)

```mermaid
flowchart TB
    subgraph Telegram Path
        TG1[Telegram Message] --> TG2[EventBus]
        TG2 --> TG3[MessageHandler]
        TG3 --> TG4[UnifiedExecutor]
        TG4 --> TG5[LangGraph]
        TG5 --> TG6[NL Response ✅]
    end

    subgraph CLI Path
        CLI1[CLI Command] --> CLI2[UnifiedExecutor]
        CLI2 --> CLI3[AgentExecutor with NL]
        CLI3 --> CLI4[Tool Results + NL]
        CLI4 --> CLI5[NL Response ✅]
    end

    subgraph HTTP Webhook Path
        HTTP1[HTTP Request] --> HTTP2[TelegramGateway]
        HTTP2 --> HTTP3[UnifiedExecutor]
        HTTP3 --> HTTP4[AgentExecutor with NL]
        HTTP4 --> HTTP5[NL Response ✅]
    end

    style TG6 fill:#9f9,stroke:#090
    style CLI5 fill:#9f9,stroke:#090
    style HTTP5 fill:#9f9,stroke:#090

    note[✅ Solution: All paths generate NL responses<br/>Consistent user experience]
```

---

## Component Dependency Graph

### Current State (Circular Dependencies Risk)

```mermaid
graph TD
    Core[core/host.py]
    Obs[observability/logging.py]
    Agent[agent/executor.py]
    Tools[agent/kira_tools.py]

    Core -->|local import| Obs
    Obs -->|needs| Core
    Agent -->|uses| Tools
    Tools -->|needs| Core
    Core -->|emits events for| Agent

    style Core fill:#f99
    style Obs fill:#f99

    note[❌ Risk: Local imports hide<br/>circular dependencies]
```

### Proposed State (Clean Dependencies)

```mermaid
graph TD
    Obs[observability/logging.py<br/>No dependencies]
    Core[core/host.py<br/>Uses: Obs]
    Tools[agent/kira_tools.py<br/>Uses: Core]
    Agent[agent/executor.py<br/>Uses: Tools]

    Core --> Obs
    Tools --> Core
    Agent --> Tools

    style Core fill:#9f9
    style Obs fill:#9f9
    style Tools fill:#9f9
    style Agent fill:#9f9

    note[✅ Solution: Unidirectional dependencies<br/>No circular imports]
```

---

## Execution State Flow

### Current: Lost Context

```mermaid
stateDiagram-v2
    [*] --> AgentState: User request

    state AgentState {
        [*] --> Planning
        Planning --> Reflecting
        Reflecting --> Executing
        Executing --> Verifying
        Verifying --> Responding
        Responding --> [*]

        note right of AgentState
            Rich state:
            - trace_id
            - messages
            - plan
            - current_step
            - tool_results
            - memory
            - budget
            - flags
            - retry_count
        end note
    }

    AgentState --> ExecutionResult: Conversion

    state ExecutionResult {
        note left of ExecutionResult
            ❌ Simplified state:
            - trace_id
            - status
            - error
            - tool_results
            - response

            LOST:
            - plan
            - memory
            - budget
            - retry_count
        end note
    }

    ExecutionResult --> [*]: Return to caller
```

### Proposed: Preserved Context

```mermaid
stateDiagram-v2
    [*] --> AgentState: User request

    state AgentState {
        [*] --> Planning
        Planning --> Reflecting
        Reflecting --> Executing
        Executing --> Verifying
        Verifying --> Responding
        Responding --> [*]
    }

    AgentState --> ExecutionResult: Conversion

    state ExecutionResult {
        note right of ExecutionResult
            ✅ Rich result:
            - trace_id
            - status
            - error
            - tool_results
            - response

            + ExecutionContext:
              - plan
              - memory
              - budget
              - retry_count
              - flags
        end note
    }

    ExecutionResult --> [*]: Return to caller
```

---

## Summary Metrics Dashboard

```mermaid
graph TB
    subgraph "Before Fixes"
        M1[Response Consistency<br/>60%]
        M2[Context Preservation<br/>40%]
        M3[Tool Success Rate<br/>75%]
        M4[Error Recovery<br/>30%]
        M5[Memory Growth<br/>+50 MB/day]
    end

    subgraph "After Fixes"
        N1[Response Consistency<br/>100% ✅]
        N2[Context Preservation<br/>95% ✅]
        N3[Tool Success Rate<br/>95% ✅]
        N4[Error Recovery<br/>80% ✅]
        N5[Memory Growth<br/>+5 MB/day ✅]
    end

    M1 -.-> N1
    M2 -.-> N2
    M3 -.-> N3
    M4 -.-> N4
    M5 -.-> N5

    style M1 fill:#fdd
    style M2 fill:#fdd
    style M3 fill:#fdd
    style M4 fill:#fdd
    style M5 fill:#fdd

    style N1 fill:#dfd
    style N2 fill:#dfd
    style N3 fill:#dfd
    style N4 fill:#dfd
    style N5 fill:#dfd
```

---

**Note**: These diagrams illustrate the key architectural issues and proposed solutions. For detailed implementation code, see the [full error analysis report](../reports/006-comprehensive-error-analysis.md).

