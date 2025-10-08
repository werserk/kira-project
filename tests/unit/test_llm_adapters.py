"""Unit tests for LLM adapters."""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest

from kira.adapters.llm import (
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    Message,
    OpenAIAdapter,
    OpenRouterAdapter,
    Tool,
)


class TestOpenRouterAdapter:
    """Tests for OpenRouter adapter."""

    def test_init(self):
        """Test adapter initialization."""
        adapter = OpenRouterAdapter(
            api_key="test-key",
            default_model="test-model",
        )
        assert adapter.api_key == "test-key"
        assert adapter.default_model == "test-model"

    def test_generate_success(self):
        """Test successful text generation."""
        adapter = OpenRouterAdapter(api_key="test-key")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {"content": "Test response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            "model": "test-model",
        }

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = adapter.generate("Test prompt")

            assert result.content == "Test response"
            assert result.finish_reason == "stop"
            assert result.usage["total_tokens"] == 30

    def test_generate_timeout(self):
        """Test timeout handling."""
        adapter = OpenRouterAdapter(api_key="test-key")

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.side_effect = (
                __import__("httpx").TimeoutException("Timeout")
            )

            with pytest.raises(LLMTimeoutError):
                adapter.generate("Test prompt", timeout=1.0)

    def test_generate_rate_limit(self):
        """Test rate limit handling."""
        adapter = OpenRouterAdapter(api_key="test-key")

        mock_response = Mock()
        mock_response.status_code = 429

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            with pytest.raises(LLMRateLimitError):
                adapter.generate("Test prompt")

    def test_chat_with_messages(self):
        """Test chat with multiple messages."""
        adapter = OpenRouterAdapter(api_key="test-key")

        messages = [
            Message(role="system", content="You are helpful"),
            Message(role="user", content="Hello"),
        ]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {"content": "Hi there!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {},
            "model": "test-model",
        }

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = adapter.chat(messages)

            assert result.content == "Hi there!"

    def test_tool_call_with_function(self):
        """Test tool calling."""
        adapter = OpenRouterAdapter(api_key="test-key")

        messages = [Message(role="user", content="Create task")]
        tools = [
            Tool(
                name="create_task",
                description="Create a task",
                parameters={"type": "object", "properties": {}},
            )
        ]

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "function": {
                                    "name": "create_task",
                                    "arguments": '{"title": "Test"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {},
            "model": "test-model",
        }

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = adapter.tool_call(messages, tools)

            assert result.finish_reason == "tool_calls"
            assert len(result.tool_calls) == 1
            assert result.tool_calls[0].name == "create_task"
            assert result.tool_calls[0].arguments == {"title": "Test"}


class TestOpenAIAdapter:
    """Tests for OpenAI adapter."""

    def test_init(self):
        """Test adapter initialization."""
        adapter = OpenAIAdapter(
            api_key="test-key",
            default_model="gpt-4",
        )
        assert adapter.api_key == "test-key"
        assert adapter.default_model == "gpt-4"

    def test_generate_success(self):
        """Test successful generation."""
        adapter = OpenAIAdapter(api_key="test-key")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {"content": "OpenAI response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {},
            "model": "gpt-4",
        }

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            result = adapter.generate("Test")

            assert result.content == "OpenAI response"

    def test_api_error_handling(self):
        """Test API error handling."""
        adapter = OpenAIAdapter(api_key="test-key")

        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_response.json.side_effect = Exception("Not JSON")

        with patch("httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response

            with pytest.raises(LLMError):
                adapter.generate("Test")
