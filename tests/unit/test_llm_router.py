"""Unit tests for LLM router."""

from unittest.mock import Mock

import pytest

from kira.adapters.llm import LLMErrorEnhanced, LLMResponse, LLMRouter, RouterConfig, Task
