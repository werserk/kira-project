"""Example: LangGraph integration with multi-provider LLM support.

Demonstrates how LangGraph works with any LLM provider through LLMRouter.

Features:
- Multi-provider support (OpenAI, Anthropic, OpenRouter, Ollama)
- Automatic fallback to Ollama on failures
- Provider routing based on task type
- Complete Phase 1-3 integration
"""

import os
from pathlib import Path

# Phase 1-3 imports
from kira.agent import (
    # LangGraph
    LangGraphExecutor,
    # LLM Integration - ключевой компонент!
    create_langgraph_llm_adapter,
    # Tools
    create_tool_executor,
    # Memory & RAG
    create_context_memory,
    create_rag_integration,
    # Persistence
    create_persistence,
    # Safety & Observability
    create_policy_enforcer,
    create_audit_logger,
    create_metrics_collector,
)
from kira.core.host import create_host_api


def example_1_basic_any_provider():
    """Example 1: Basic usage with any LLM provider."""
    print("=" * 60)
    print("Example 1: LangGraph with ANY LLM Provider")
    print("=" * 60)

    # Create LLM adapter - работает с ЛЮБЫМ провайдером!
    llm = create_langgraph_llm_adapter(
        api_keys={
            "anthropic": os.getenv("ANTHROPIC_API_KEY", ""),
            "openai": os.getenv("OPENAI_API_KEY", ""),
            "openrouter": os.getenv("OPENROUTER_API_KEY", ""),
        },
        # Routing strategy:
        planning_provider="anthropic",  # Claude для планирования
        structuring_provider="openai",  # GPT-4 для JSON
        default_provider="openrouter",  # OpenRouter как default
        enable_ollama_fallback=True,  # Fallback на локальный Ollama
        task_type="planning",  # LangGraph делает планирование
    )

    # Create tools
    vault_path = Path.cwd() / "vault"
    host_api = create_host_api(vault_path)
    tool_executor = create_tool_executor(host_api, vault_path)
    tool_registry = tool_executor.get_tool_registry()

    # Create executor
    executor = LangGraphExecutor(
        llm,  # Наш multi-provider адаптер!
        tool_registry,
        max_steps=10,
        enable_reflection=True,
        enable_verification=True,
    )

    # Execute
    print("\n✨ Executing with automatic provider selection...")
    result = executor.execute("Create a task called 'Test Multi-Provider'")

    print(f"\n✅ Success: {result.success}")
    print(f"📊 Status: {result.status}")
    print(f"🔧 Tools executed: {len(result.tool_results)}")
    print(f"💰 Budget used: {result.budget_used.steps_used} steps")


def example_2_provider_fallback():
    """Example 2: Automatic fallback to Ollama when remote fails."""
    print("\n" + "=" * 60)
    print("Example 2: Automatic Fallback to Ollama")
    print("=" * 60)

    # Без API ключей - автоматически fallback на Ollama!
    llm = create_langgraph_llm_adapter(
        api_keys={},  # Пустые ключи
        enable_ollama_fallback=True,  # Ollama спасает!
        task_type="planning",
    )

    print("\n🔄 No API keys provided - will fallback to Ollama")
    print("💡 Make sure Ollama is running: ollama serve")

    # Rest of setup...
    vault_path = Path.cwd() / "vault"
    host_api = create_host_api(vault_path)
    tool_executor = create_tool_executor(host_api, vault_path)
    tool_registry = tool_executor.get_tool_registry()

    executor = LangGraphExecutor(llm, tool_registry)

    # Execute - будет работать с Ollama!
    result = executor.execute("List all tasks")

    print(f"\n✅ Fallback worked: {result.success}")


def example_3_full_integration():
    """Example 3: Full integration with all Phase 1-3 components."""
    print("\n" + "=" * 60)
    print("Example 3: Full Integration (Phase 1-3)")
    print("=" * 60)

    vault_path = Path.cwd() / "vault"

    # 1. LLM with multi-provider support
    llm = create_langgraph_llm_adapter(
        api_keys={
            "anthropic": os.getenv("ANTHROPIC_API_KEY", ""),
        },
        enable_ollama_fallback=True,
    )

    # 2. Tools with validation
    host_api = create_host_api(vault_path)
    tool_executor = create_tool_executor(host_api, vault_path)
    tool_registry = tool_executor.get_tool_registry()

    # 3. Memory for multi-turn conversations
    memory = create_context_memory(max_facts=20)

    # 4. RAG for better planning
    rag = create_rag_integration(
        vault_path=vault_path,
        index_path=vault_path / ".kira" / "rag_index.json",
    )

    # 5. Persistence for recovery
    persistence = create_persistence(
        storage_type="sqlite",
        storage_path=vault_path / ".kira" / "agent_states",
    )

    # 6. Policy enforcement
    policy_enforcer = create_policy_enforcer(
        enable_delete=False,  # Запрещаем удаление
        require_confirmation=True,
    )

    # 7. Audit logging
    audit_logger = create_audit_logger(
        audit_path=vault_path / "artifacts" / "audit" / "agent",
    )

    # 8. Metrics collection
    metrics = create_metrics_collector()

    # Create executor
    executor = LangGraphExecutor(
        llm,  # Multi-provider LLM
        tool_registry,
        max_steps=15,
        max_tokens=15000,
        enable_reflection=True,
        enable_verification=True,
    )

    print("\n🚀 Full stack initialized:")
    print(f"   • LLM: Multi-provider with fallback")
    print(f"   • Tools: {len(tool_registry.list_tools())} validated tools")
    print(f"   • Memory: Multi-turn context")
    print(f"   • RAG: Documentation-enhanced planning")
    print(f"   • Persistence: SQLite state recovery")
    print(f"   • Policies: Capability enforcement")
    print(f"   • Audit: JSONL event logging")
    print(f"   • Metrics: Prometheus-compatible")

    # Execute complex workflow
    trace_id = "full-integration-demo"

    print(f"\n📝 Executing workflow...")
    result = executor.execute(
        "Create a task named 'Integration Test' with tag 'demo'",
        trace_id=trace_id,
    )

    # Save state for recovery
    if result.state:
        persistence.save_state(trace_id, result.state)
        print(f"💾 State saved for trace: {trace_id}")

    # Log audit event
    audit_logger.log_node_execution(
        trace_id=trace_id,
        node="full_workflow",
        output_data={"success": result.success},
        elapsed_ms=int(result.budget_used.wall_time_used * 1000),
    )

    # Record metrics
    metrics.record_step(success=result.success)
    for tool_result in result.tool_results:
        metrics.record_tool_execution(
            tool_name=tool_result.get("tool", "unknown"),
            latency_seconds=tool_result.get("elapsed_ms", 0) / 1000,
            success=tool_result.get("status") == "ok",
        )

    # Get health
    health = metrics.get_health()

    print(f"\n✅ Execution complete:")
    print(f"   • Success: {result.success}")
    print(f"   • Status: {result.status}")
    print(f"   • Steps: {result.budget_used.steps_used}")
    print(f"   • Health: {health.status}")


def main():
    """Run all examples."""
    print("\n" + "🎯 " * 20)
    print("LangGraph + Multi-Provider LLM Integration Examples")
    print("🎯 " * 20)

    print("\n💡 Key Feature: LangGraph works with ANY LLM provider:")
    print("   • OpenAI (GPT-4)")
    print("   • Anthropic (Claude)")
    print("   • OpenRouter (100+ models)")
    print("   • Ollama (local, free)")
    print("   • Automatic fallback on failures")

    try:
        example_1_basic_any_provider()
    except Exception as e:
        print(f"\n❌ Example 1 failed: {e}")

    try:
        example_2_provider_fallback()
    except Exception as e:
        print(f"\n❌ Example 2 failed: {e}")

    try:
        example_3_full_integration()
    except Exception as e:
        print(f"\n❌ Example 3 failed: {e}")

    print("\n" + "=" * 60)
    print("✅ Examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()

