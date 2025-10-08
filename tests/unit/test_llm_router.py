"""Unit tests for Sprint 2 LLM adapters and router."""

from unittest.mock import Mock, patch

import pytest

from kira.adapters.llm import (
    AnthropicAdapter,
    LLMErrorEnhanced,
    LLMResponse,
    LLMRouter,
    Message,
    OllamaAdapter,
    RouterConfig,
    TaskType,
)


class TestAnthropicAdapter:
    """Tests for Anthropic adapter."""

    def test_init(self):
        """Test adapter initialization."""
        adapter = AnthropicAdapter(api_key="test-key")
        assert adapter.api_key == "test-key"
        assert adapter.default_model == "claude-3-5-sonnet-20241022"

    def test_generate_success(self):
        """Test successful generation."""
        adapter = AnthropicAdapter(api_key="test-key")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "Test response"}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 20},
            "model": "claude-3-5-sonnet",
        }

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = adapter.generate("Test prompt")

            assert result.content == "Test response"
            assert result.usage["total_tokens"] == 30


class TestOllamaAdapter:
    """Tests for Ollama adapter."""

    def test_init(self):
        """Test adapter initialization."""
        adapter = OllamaAdapter()
        assert adapter.base_url == "http://localhost:11434"
        assert adapter.default_model == "llama2"

    def test_generate_success(self):
        """Test successful generation."""
        adapter = OllamaAdapter()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Ollama response",
            "prompt_eval_count": 10,
            "eval_count": 15,
        }

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = adapter.generate("Test prompt")

            assert result.content == "Ollama response"
            assert result.usage["total_tokens"] == 25


class TestLLMRouter:
    """Tests for LLM router."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = RouterConfig(
            planning_provider="anthropic",
            structuring_provider="openai",
            default_provider="openrouter",
            enable_ollama_fallback=True,
            max_retries=2,
        )

        self.mock_anthropic = Mock()
        self.mock_openai = Mock()
        self.mock_openrouter = Mock()
        self.mock_ollama = Mock()

    def test_route_planning_task(self):
        """Test routing planning task to Anthropic."""
        router = LLMRouter(
            self.config,
            anthropic_adapter=self.mock_anthropic,
            openai_adapter=self.mock_openai,
            openrouter_adapter=self.mock_openrouter,
        )

        messages = [Message(role="user", content="Plan something")]
        expected_response = LLMResponse(content="Plan response")

        self.mock_anthropic.chat.return_value = expected_response

        result = router.chat(messages, task_type=TaskType.PLANNING)

        assert result == expected_response
        self.mock_anthropic.chat.assert_called_once()

    def test_route_structuring_task(self):
        """Test routing structuring task to OpenAI."""
        router = LLMRouter(
            self.config,
            anthropic_adapter=self.mock_anthropic,
            openai_adapter=self.mock_openai,
            openrouter_adapter=self.mock_openrouter,
        )

        messages = [Message(role="user", content="Structure data")]
        expected_response = LLMResponse(content="Structured response")

        self.mock_openai.chat.return_value = expected_response

        result = router.chat(messages, task_type=TaskType.STRUCTURING)

        assert result == expected_response
        self.mock_openai.chat.assert_called_once()

    def test_fallback_to_ollama(self):
        """Test fallback to Ollama on error."""
        router = LLMRouter(
            self.config,
            openrouter_adapter=self.mock_openrouter,
            ollama_adapter=self.mock_ollama,
        )

        messages = [Message(role="user", content="Test")]

        # Make primary fail with retryable error
        from kira.adapters.llm import LLMTimeoutError

        self.mock_openrouter.chat.side_effect = LLMTimeoutError("Timeout")

        # Ollama succeeds
        fallback_response = LLMResponse(content="Ollama fallback")
        self.mock_ollama.chat.return_value = fallback_response

        result = router.chat(messages, task_type=TaskType.DEFAULT)

        assert result == fallback_response
        self.mock_ollama.chat.assert_called_once()

    def test_retry_on_rate_limit(self):
        """Test retry logic on rate limit."""
        router = LLMRouter(
            self.config,
            openrouter_adapter=self.mock_openrouter,
        )

        messages = [Message(role="user", content="Test")]

        from kira.adapters.llm import LLMRateLimitError

        # Fail once, then succeed
        self.mock_openrouter.chat.side_effect = [
            LLMRateLimitError("Rate limited"),
            LLMResponse(content="Success after retry"),
        ]

        with patch("time.sleep"):  # Speed up test
            result = router.chat(messages)

        assert result.content == "Success after retry"
        assert self.mock_openrouter.chat.call_count == 2
