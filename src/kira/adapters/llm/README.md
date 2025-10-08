# LLM Adapters

**Multi-provider LLM integration with intelligent routing and fallback.**

The LLM adapters provide a unified interface to multiple language model providers, with automatic routing, retry logic, and local fallback capabilities.

---

## Features

- ✅ **Multiple Providers** - Anthropic, OpenAI, OpenRouter, Ollama
- ✅ **Intelligent Routing** - Task-based provider selection
- ✅ **Automatic Fallback** - Local Ollama when remote fails
- ✅ **Retry Logic** - Exponential backoff for transient errors
- ✅ **Rate Limit Handling** - Automatic retry on rate limits
- ✅ **Tool Calling** - Function calling support across providers
- ✅ **Unified Interface** - Provider-agnostic `LLMAdapter` protocol

---

## Quick Start

### Installation

```bash
# Install dependencies
poetry add anthropic openai httpx

# For local fallback
# Install Ollama: https://ollama.ai
ollama pull llama2
```

### Basic Usage with Router

```python
from kira.adapters.llm import LLMRouter, RouterConfig, TaskType
from kira.adapters.llm import AnthropicAdapter, OpenAIAdapter, OllamaAdapter

# Create adapters
anthropic = AnthropicAdapter(api_key=os.getenv("ANTHROPIC_API_KEY"))
openai = OpenAIAdapter(api_key=os.getenv("OPENAI_API_KEY"))
ollama = OllamaAdapter()  # Local fallback

# Create router
router = LLMRouter(
    config=RouterConfig(
        planning_provider="anthropic",
        structuring_provider="openai",
        default_provider="anthropic",
        enable_ollama_fallback=True
    ),
    anthropic_adapter=anthropic,
    openai_adapter=openai,
    ollama_adapter=ollama
)

# Use router
response = router.chat(
    messages=[
        {"role": "user", "content": "Create a task breakdown for Q4 planning"}
    ],
    task_type=TaskType.PLANNING  # Routes to Anthropic
)

print(response.content)
```

---

## Supported Providers

### 1. Anthropic (Claude)

**Best for:** Complex reasoning, planning, long context

```python
from kira.adapters.llm import AnthropicAdapter

adapter = AnthropicAdapter(
    api_key="sk-ant-...",
    default_model="claude-3-5-sonnet-20241022",
    base_url="https://api.anthropic.com/v1"
)

response = adapter.generate(
    prompt="Explain quantum computing",
    temperature=0.7,
    max_tokens=1000,
    timeout=30.0
)
```

**Models:**
- `claude-3-5-sonnet-20241022` (recommended)
- `claude-3-opus-20240229`
- `claude-3-haiku-20240307`

---

### 2. OpenAI (GPT)

**Best for:** Structured outputs, JSON generation

```python
from kira.adapters.llm import OpenAIAdapter

adapter = OpenAIAdapter(
    api_key="sk-...",
    default_model="gpt-4-turbo-preview",
    base_url="https://api.openai.com/v1"
)

response = adapter.chat(
    messages=[
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Hello!"}
    ],
    temperature=0.7,
    max_tokens=500
)
```

**Models:**
- `gpt-4-turbo-preview`
- `gpt-4`
- `gpt-3.5-turbo`

---

### 3. OpenRouter

**Best for:** Multi-model access, cost optimization

```python
from kira.adapters.llm import OpenRouterAdapter

adapter = OpenRouterAdapter(
    api_key="sk-or-...",
    default_model="anthropic/claude-3.5-sonnet",
    site_url="https://kira.example.com",  # For rankings
    site_name="Kira"
)

response = adapter.generate(
    prompt="Summarize this text...",
    model="openai/gpt-4-turbo-preview",  # Override model
    temperature=0.5
)
```

**Benefits:**
- Access to 100+ models
- Automatic routing to cheapest/fastest
- No vendor lock-in

---

### 4. Ollama (Local)

**Best for:** Offline operation, privacy, cost savings

```python
from kira.adapters.llm import OllamaAdapter

adapter = OllamaAdapter(
    base_url="http://localhost:11434",
    default_model="llama2"
)

response = adapter.generate(
    prompt="What is AI?",
    temperature=0.7,
    max_tokens=500
)
```

**Models:**
- `llama2` (7B, 13B, 70B)
- `mistral`
- `codellama`
- `neural-chat`

**Setup:**
```bash
# Install Ollama
curl https://ollama.ai/install.sh | sh

# Pull models
ollama pull llama2
ollama pull mistral

# Start server
ollama serve
```

---

## LLM Router

The router intelligently selects providers based on task type and handles failures gracefully.

### Configuration

```python
from kira.adapters.llm import RouterConfig

config = RouterConfig(
    planning_provider="anthropic",      # For complex planning
    structuring_provider="openai",      # For JSON outputs
    default_provider="openrouter",      # General tasks
    enable_ollama_fallback=True,        # Fall back to local
    max_retries=3,                      # Retry attempts
    initial_backoff=1.0,                # Initial delay (seconds)
    max_backoff=30.0,                   # Max delay (seconds)
    backoff_multiplier=2.0              # Exponential factor
)
```

### Task Types

```python
from kira.adapters.llm import TaskType

# Planning: Complex multi-step reasoning
response = router.chat(
    messages=[...],
    task_type=TaskType.PLANNING  # → Anthropic
)

# Structuring: JSON generation, data extraction
response = router.chat(
    messages=[...],
    task_type=TaskType.STRUCTURING  # → OpenAI
)

# Default: General queries
response = router.chat(
    messages=[...],
    task_type=TaskType.DEFAULT  # → OpenRouter
)
```

### Automatic Fallback

If remote provider fails (rate limit, timeout, network error), router automatically falls back to Ollama:

```python
try:
    # Try Anthropic
    response = anthropic.chat(messages)
except LLMRateLimitError:
    # Automatic fallback to Ollama
    response = ollama.chat(messages)
```

**Fallback Triggers:**
- Rate limit errors (429)
- Timeout errors
- Network errors (connection refused, DNS)
- API errors (500, 503)

**Not Triggered:**
- Authentication errors (401, 403)
- Invalid request errors (400)
- Model not found (404)

---

## LLM Adapter Protocol

All adapters implement the `LLMAdapter` protocol:

```python
from typing import Protocol
from kira.adapters.llm import LLMResponse, Message, Tool

class LLMAdapter(Protocol):
    def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        timeout: float = 30.0
    ) -> LLMResponse:
        """Single-turn text completion."""
        ...

    def chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        timeout: float = 30.0
    ) -> LLMResponse:
        """Multi-turn conversation."""
        ...

    def tool_call(
        self,
        messages: list[Message],
        tools: list[Tool],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        timeout: float = 60.0
    ) -> LLMResponse:
        """Chat with tool/function calling."""
        ...
```

---

## Tool/Function Calling

Use tools to give LLMs the ability to execute functions:

```python
from kira.adapters.llm import Message, Tool

# Define available tools
tools = [
    Tool(
        name="create_task",
        description="Create a new task in the vault",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "due": {"type": "string", "format": "date-time"},
                "priority": {"type": "string", "enum": ["low", "medium", "high"]}
            },
            "required": ["title"]
        }
    )
]

# Call with tools
response = adapter.tool_call(
    messages=[
        Message(role="user", content="Create a task to review Q4 report by Friday")
    ],
    tools=tools
)

# Check for tool calls
if response.tool_calls:
    for call in response.tool_calls:
        print(f"Tool: {call.name}")
        print(f"Arguments: {call.arguments}")

        # Execute tool
        if call.name == "create_task":
            create_task(**call.arguments)
```

### Provider Support

| Provider | Tool Calling | Notes |
|----------|--------------|-------|
| Anthropic | ✅ Native | Full support with structured output |
| OpenAI | ✅ Native | Function calling API |
| OpenRouter | ✅ Native | Depends on underlying model |
| Ollama | ⚠️ Emulated | Tools described in prompt, JSON response |

---

## Response Format

All methods return `LLMResponse`:

```python
@dataclass
class LLMResponse:
    content: str                        # Generated text
    finish_reason: str                  # "stop", "length", "tool_calls", "error"
    tool_calls: list[ToolCall]         # Function calls (if any)
    usage: dict[str, int]              # Token usage
    model: str                          # Model used
    raw_response: dict                  # Original API response
```

**Example:**
```python
response = adapter.generate("Hello!")

print(response.content)        # "Hello! How can I help you?"
print(response.finish_reason)  # "stop"
print(response.usage)          # {"prompt_tokens": 3, "completion_tokens": 8, ...}
print(response.model)          # "claude-3-5-sonnet-20241022"
```

---

## Error Handling

### Exception Hierarchy

```python
LLMError
├── LLMTimeoutError      # Request timed out
├── LLMRateLimitError    # Rate limit exceeded
└── LLMErrorEnhanced     # Router errors (with retry info)
```

### Retry Logic

```python
from kira.adapters.llm import LLMRateLimitError

for attempt in range(max_retries):
    try:
        response = adapter.chat(messages)
        break
    except LLMRateLimitError as e:
        if attempt < max_retries - 1:
            delay = initial_backoff * (2 ** attempt)
            time.sleep(min(delay, max_backoff))
        else:
            raise
```

### Error Example

```python
from kira.adapters.llm import LLMErrorEnhanced

try:
    response = router.chat(messages)
except LLMErrorEnhanced as e:
    print(f"Provider: {e.provider}")
    print(f"Error type: {e.error_type}")
    print(f"Retryable: {e.retryable}")

    if e.retryable:
        # Try again later
        pass
```

---

## Best Practices

### ✅ DO

1. **Use router** instead of calling adapters directly
2. **Enable Ollama fallback** for reliability
3. **Set reasonable timeouts** (30s for chat, 60s for tool calls)
4. **Handle rate limits** gracefully
5. **Log provider choices** for debugging
6. **Use tool calling** for structured outputs
7. **Cache responses** when appropriate

### ❌ DON'T

1. **Don't expose API keys** in logs or commits
2. **Don't ignore timeouts** (set limits)
3. **Don't retry forever** (max_retries)
4. **Don't use high temperature** for structured tasks (use 0.0-0.3)
5. **Don't skip error handling**

---

## Testing

### Unit Tests

```python
def test_anthropic_adapter():
    adapter = AnthropicAdapter(api_key="test-key")
    assert adapter.default_model == "claude-3-5-sonnet-20241022"

def test_router_provider_selection():
    router = LLMRouter(
        config=RouterConfig(),
        anthropic_adapter=AnthropicAdapter("key")
    )

    provider = router._get_provider_for_task(TaskType.PLANNING)
    assert provider == "anthropic"
```

### Integration Tests

```python
@pytest.mark.integration
def test_openai_chat():
    adapter = OpenAIAdapter(api_key=os.getenv("OPENAI_API_KEY"))

    response = adapter.chat([
        Message(role="user", content="Say 'test passed'")
    ])

    assert "test passed" in response.content.lower()
    assert response.finish_reason == "stop"
```

### Mocking

```python
from unittest.mock import Mock

def test_with_mock():
    adapter = Mock(spec=LLMAdapter)
    adapter.chat.return_value = LLMResponse(
        content="Mocked response",
        finish_reason="stop"
    )

    response = adapter.chat([...])
    assert response.content == "Mocked response"
```

---

## Performance Optimization

### Caching

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_generate(prompt: str) -> str:
    response = adapter.generate(prompt)
    return response.content
```

### Streaming (Future)

```python
# Future feature
for chunk in adapter.stream_chat(messages):
    print(chunk.content, end="", flush=True)
```

### Batch Processing

```python
prompts = ["...", "...", "..."]

responses = []
for prompt in prompts:
    response = adapter.generate(prompt)
    responses.append(response)
    time.sleep(0.1)  # Rate limiting
```

---

## Cost Optimization

### 1. Use Cheaper Models

```python
# Expensive
response = router.chat(messages, model="claude-3-opus-20240229")

# Cheaper
response = router.chat(messages, model="claude-3-haiku-20240307")
```

### 2. Reduce Token Usage

```python
# Limit output length
response = adapter.chat(
    messages,
    max_tokens=500  # Instead of 4000
)

# Use lower temperature for deterministic tasks
response = adapter.chat(
    messages,
    temperature=0.0  # Deterministic, fewer tokens
)
```

### 3. Use Local Models

```python
# For simple tasks, use Ollama
if is_simple_task(prompt):
    response = ollama.generate(prompt)
else:
    response = anthropic.generate(prompt)
```

---

## References

- [Anthropic API Documentation](https://docs.anthropic.com/)
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [OpenRouter Documentation](https://openrouter.ai/docs)
- [Ollama Documentation](https://ollama.ai/docs)

---

## Troubleshooting

### API Key Errors

**Problem:** `401 Unauthorized`

**Solution:**
```bash
# Check environment variables
echo $ANTHROPIC_API_KEY
echo $OPENAI_API_KEY

# Set if missing
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Ollama Connection Refused

**Problem:** `Connection refused to localhost:11434`

**Solution:**
```bash
# Check if Ollama is running
ollama serve

# Or start in background
nohup ollama serve &
```

### Rate Limits

**Problem:** `429 Rate Limit Exceeded`

**Solution:**
- Increase `rate_limit_delay` in config
- Use cheaper models
- Implement request queue
- Enable Ollama fallback

---

**Status:** ✅ Production Ready
**Version:** 1.0.0
**Last Updated:** 2025-10-08
