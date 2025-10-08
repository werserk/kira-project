"""Comprehensive tests for inbox normalizer plugin (ADR-013)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kira.plugin_sdk.context import PluginContext
from kira.plugins.inbox.src.kira_plugin_inbox.plugin import (
    ClarificationRequest,
    EntityClassification,
    InboxNormalizer,
    activate,
    get_normalizer,
)


class TestEntityClassification:
    """Test EntityClassification dataclass."""

    def test_classification_creation(self) -> None:
        """Test creating entity classification."""
        classification = EntityClassification(
            entity_type="task",
            confidence=0.85,
            extracted_fields={"title": "Test task"},
            reasoning="High confidence task classification",
        )

        assert classification.entity_type == "task"
        assert classification.confidence == 0.85
        assert "title" in classification.extracted_fields


class TestClarificationRequest:
    """Test ClarificationRequest dataclass."""

    def test_clarification_request_creation(self) -> None:
        """Test creating clarification request."""
        classification = EntityClassification(
            entity_type="event",
            confidence=0.6,
            extracted_fields={},
        )

        request = ClarificationRequest(
            request_id="clarify-123",
            content="Test content",
            classification=classification,
            suggested_fields={"title": "Test"},
        )

        assert request.request_id == "clarify-123"
        assert request.classification.entity_type == "event"
        assert request.classification.confidence == 0.6


class TestTextNormalization:
    """Test text normalization."""

    def test_normalize_text_whitespace(self) -> None:
        """Test whitespace normalization."""
        text = "Test   with    extra   spaces"
        result = InboxNormalizer.normalize_text(text)
        assert result == "Test with extra spaces"

    def test_normalize_text_newlines(self) -> None:
        """Test newline normalization."""
        text = "Line 1\n\n\n\nLine 2"
        result = InboxNormalizer.normalize_text(text)
        assert result == "Line 1\n\nLine 2"

    def test_normalize_text_punctuation(self) -> None:
        """Test punctuation stripping."""
        text = "  Test text...  "
        result = InboxNormalizer.normalize_text(text)
        assert result == "Test text"


class TestContentClassification:
    """Test content classification."""

    def setup_method(self) -> None:
        """Setup test environment."""
        context = MagicMock(spec=PluginContext)
        context.config = {"vault": {"path": "/tmp/test-vault"}}
        context.logger = MagicMock()
        context.events = MagicMock()
        context.vault = None

        self.normalizer = InboxNormalizer(context)

    def test_classify_task(self) -> None:
        """Test task classification."""
        content = "Нужно сделать задачу по исправлению бага"
        classification = self.normalizer.classify_content(content)

        assert classification.entity_type == "task"
        assert classification.confidence > 0.5

    def test_classify_event(self) -> None:
        """Test event classification."""
        content = "Событие завтра в 14:00"
        classification = self.normalizer.classify_content(content)

        assert classification.entity_type in ["event", "meeting"]
        assert "time" in classification.extracted_fields or classification.confidence > 0.3

    def test_classify_meeting(self) -> None:
        """Test meeting classification."""
        content = "Встреча с командой в 15:30"
        classification = self.normalizer.classify_content(content)

        assert classification.entity_type == "meeting"
        assert classification.confidence > 0.5

    def test_classify_email_draft(self) -> None:
        """Test email draft classification."""
        content = "Отправить письмо на test@example.com"
        classification = self.normalizer.classify_content(content)

        assert classification.entity_type == "email_draft"
        assert "recipients" in classification.extracted_fields

    def test_classify_research(self) -> None:
        """Test research classification."""
        content = "Изучить документацию по https://example.com/docs"
        classification = self.normalizer.classify_content(content)

        assert classification.entity_type == "research"
        assert "links" in classification.extracted_fields

    def test_classify_note_fallback(self) -> None:
        """Test note as fallback classification."""
        content = "Просто какая-то заметка"
        classification = self.normalizer.classify_content(content)

        assert classification.entity_type == "note"

    def test_extract_priority_high(self) -> None:
        """Test high priority extraction."""
        content = "Срочно: исправить критический баг"
        classification = self.normalizer.classify_content(content)

        assert classification.extracted_fields.get("priority") == "high"

    def test_extract_priority_low(self) -> None:
        """Test low priority extraction."""
        content = "Низкий приоритет: почитать статью"
        classification = self.normalizer.classify_content(content)

        assert classification.extracted_fields.get("priority") == "low"

    def test_extract_tags(self) -> None:
        """Test tag extraction."""
        content = "Заметка с #тегом1 и #тегом2"
        classification = self.normalizer.classify_content(content)

        assert "tags" in classification.extracted_fields
        tags = classification.extracted_fields["tags"]
        assert "тегом1" in tags
        assert "тегом2" in tags

    def test_extract_title_from_first_line(self) -> None:
        """Test title extraction from first line."""
        content = "# Заголовок заметки\n\nСодержимое"
        classification = self.normalizer.classify_content(content)

        assert "title" in classification.extracted_fields
        assert "Заголовок" in classification.extracted_fields["title"]

    def test_extract_time_from_content(self) -> None:
        """Test time extraction."""
        content = "Встреча в 14:30"
        classification = self.normalizer.classify_content(content)

        if classification.entity_type in ["event", "meeting"]:
            assert "time" in classification.extracted_fields


class TestMetadataExtraction:
    """Test metadata extraction."""

    def setup_method(self) -> None:
        """Setup test environment."""
        context = MagicMock(spec=PluginContext)
        context.config = {"vault": {"path": "/tmp/test-vault"}}
        context.logger = MagicMock()
        context.events = MagicMock()
        context.vault = None

        self.normalizer = InboxNormalizer(context)

    def test_extract_metadata_basic(self) -> None:
        """Test basic metadata extraction."""
        content = "Test content"
        metadata = self.normalizer.extract_metadata(content, source="telegram")

        assert metadata["source"] == "telegram"
        assert "timestamp" in metadata
        assert "length" in metadata
        assert "entity_type" in metadata

    def test_extract_metadata_with_classification(self) -> None:
        """Test metadata extraction with pre-computed classification."""
        content = "Task content"
        classification = EntityClassification(
            entity_type="task",
            confidence=0.9,
            extracted_fields={"title": "Test Task"},
        )

        metadata = self.normalizer.extract_metadata(content, classification=classification)

        assert metadata["entity_type"] == "task"
        assert metadata["confidence"] == 0.9
        assert metadata["title"] == "Test Task"


class TestEntityCreation:
    """Test entity creation."""

    def setup_method(self) -> None:
        """Setup test environment."""
        context = MagicMock(spec=PluginContext)
        context.config = {"vault": {"path": "/tmp/test-vault"}}
        context.logger = MagicMock()
        context.events = MagicMock()

        # Mock vault API
        mock_entity = MagicMock()
        mock_entity.id = "test-123"
        mock_entity.path = Path("/tmp/test-vault/processed/test-123.md")

        context.vault = MagicMock()
        context.vault.create_entity.return_value = mock_entity

        self.normalizer = InboxNormalizer(context)

    def test_create_entity_high_confidence(self) -> None:
        """Test entity creation with high confidence."""
        content = "Test task"
        metadata = {
            "entity_type": "task",
            "confidence": 0.9,
            "title": "Test Task",
            "source": "telegram",
        }

        result = self.normalizer.create_entity(content, metadata)

        assert result["success"]
        assert "entity_id" in result
        assert result["entity_type"] == "task"

    def test_create_entity_low_confidence_queues_clarification(self) -> None:
        """Test that low confidence triggers clarification queue."""
        self.normalizer.confidence_threshold = 0.75

        content = "Ambiguous content"
        metadata = {
            "entity_type": "note",
            "confidence": 0.5,  # Below threshold
            "title": "Ambiguous",
        }

        result = self.normalizer.create_entity(content, metadata)

        assert not result.get("success")
        assert result.get("requires_clarification")
        assert "request_id" in result


class TestClarificationQueue:
    """Test clarification queue."""

    def setup_method(self) -> None:
        """Setup test environment."""
        context = MagicMock(spec=PluginContext)
        context.config = {"vault": {"path": "/tmp/test-vault"}}
        context.logger = MagicMock()
        context.events = MagicMock()
        context.vault = MagicMock()

        self.normalizer = InboxNormalizer(context)
        self.normalizer.confidence_threshold = 0.75

    def test_queue_clarification(self) -> None:
        """Test queuing clarification request."""
        content = "Ambiguous content"
        metadata = {
            "entity_type": "note",
            "confidence": 0.6,
            "title": "Ambiguous",
        }

        result = self.normalizer._queue_clarification(content, metadata)

        assert result.get("requires_clarification")
        assert "request_id" in result

        # Check that request is in queue
        request_id = result["request_id"]
        assert request_id in self.normalizer._clarifications

    def test_clarification_confirmed(self) -> None:
        """Test handling clarification confirmation."""
        # Queue a clarification
        content = "Test content"
        metadata = {
            "entity_type": "task",
            "confidence": 0.6,
            "title": "Test",
        }
        result = self.normalizer._queue_clarification(content, metadata)
        request_id = result["request_id"]

        # Mock event
        event = MagicMock()
        event.payload = {
            "request_id": request_id,
            "choice": "confirm",
        }

        # Handle confirmation
        self.normalizer._handle_clarification_confirmed(event)

        # Request should be removed from queue
        assert request_id not in self.normalizer._clarifications

    def test_clarification_alternative_selected(self) -> None:
        """Test handling alternative entity type selection."""
        content = "Test content"
        metadata = {
            "entity_type": "note",
            "confidence": 0.6,
            "title": "Test",
        }
        result = self.normalizer._queue_clarification(content, metadata)
        request_id = result["request_id"]

        # User selects alternative
        event = MagicMock()
        event.payload = {
            "request_id": request_id,
            "choice": "alt_task",
        }

        self.normalizer._handle_clarification_confirmed(event)

        # Request should be removed
        assert request_id not in self.normalizer._clarifications

    def test_clarification_skipped(self) -> None:
        """Test handling clarification skip."""
        content = "Test content"
        metadata = {
            "entity_type": "note",
            "confidence": 0.6,
            "title": "Test",
        }
        result = self.normalizer._queue_clarification(content, metadata)
        request_id = result["request_id"]

        # User skips
        event = MagicMock()
        event.payload = {
            "request_id": request_id,
            "choice": "skip",
        }

        self.normalizer._handle_clarification_confirmed(event)

        # Request should be removed
        assert request_id not in self.normalizer._clarifications


class TestMessageProcessing:
    """Test message processing."""

    def setup_method(self) -> None:
        """Setup test environment."""
        context = MagicMock(spec=PluginContext)
        context.config = {"vault": {"path": "/tmp/test-vault"}}
        context.logger = MagicMock()
        context.events = MagicMock()

        mock_entity = MagicMock()
        mock_entity.id = "test-123"
        mock_entity.path = Path("/tmp/test-vault/processed/test-123.md")

        context.vault = MagicMock()
        context.vault.create_entity.return_value = mock_entity

        self.normalizer = InboxNormalizer(context)

    def test_process_message_task(self) -> None:
        """Test processing task message."""
        message = "Нужно сделать задачу: исправить баг в авторизации"
        result = self.normalizer.process_message(message, source="telegram")

        assert "success" in result or "requires_clarification" in result

    def test_process_message_with_source(self) -> None:
        """Test processing message with source."""
        message = "Test message"
        result = self.normalizer.process_message(message, source="telegram")

        assert result is not None


class TestEventHandling:
    """Test event handling."""

    def setup_method(self) -> None:
        """Setup test environment."""
        context = MagicMock(spec=PluginContext)
        context.config = {"vault": {"path": "/tmp/test-vault"}}
        context.logger = MagicMock()
        context.events = MagicMock()

        mock_entity = MagicMock()
        mock_entity.id = "test-123"
        context.vault = MagicMock()
        context.vault.create_entity.return_value = mock_entity

        self.normalizer = InboxNormalizer(context)

    def test_handle_message_received(self) -> None:
        """Test handling message.received event."""
        event = MagicMock()
        event.payload = {
            "message": "Test message content",
            "source": "telegram",
        }

        self.normalizer._handle_message_received(event)

        # Should process without errors

    def test_handle_message_received_empty(self) -> None:
        """Test handling empty message."""
        event = MagicMock()
        event.payload = {"message": ""}

        # Should not raise exception
        self.normalizer._handle_message_received(event)


class TestTelegramIntegration:
    """Test Telegram integration."""

    def setup_method(self) -> None:
        """Setup test environment."""
        context = MagicMock(spec=PluginContext)
        context.config = {"vault": {"path": "/tmp/test-vault"}}
        context.logger = MagicMock()
        context.events = MagicMock()
        context.vault = MagicMock()

        self.normalizer = InboxNormalizer(context)

    def test_request_telegram_confirmation(self) -> None:
        """Test requesting Telegram confirmation."""
        classification = EntityClassification(
            entity_type="task",
            confidence=0.6,
            extracted_fields={"title": "Test"},
        )

        request = ClarificationRequest(
            request_id="test-123",
            content="Test content",
            classification=classification,
            suggested_fields={"title": "Test"},
        )

        self.normalizer._request_telegram_confirmation(request)

        # Should publish telegram.confirmation_request event
        assert self.normalizer.context.events.publish.called


class TestPluginActivation:
    """Test plugin activation."""

    def test_activate_plugin(self) -> None:
        """Test plugin activation."""
        context = MagicMock(spec=PluginContext)
        context.config = {"vault": {"path": "/tmp/test-vault"}}
        context.logger = MagicMock()
        context.events = MagicMock()
        context.vault = None

        result = activate(context)

        assert result["status"] == "ok"
        assert result["plugin"] == "kira-inbox"

    def test_get_normalizer_after_activation(self) -> None:
        """Test getting normalizer after activation."""
        context = MagicMock(spec=PluginContext)
        context.config = {"vault": {"path": "/tmp/test-vault"}}
        context.logger = MagicMock()
        context.events = MagicMock()
        context.vault = None

        activate(context)
        normalizer = get_normalizer()

        assert normalizer is not None
        assert isinstance(normalizer, InboxNormalizer)


class TestEventPublishing:
    """Test event publishing."""

    def setup_method(self) -> None:
        """Setup test environment."""
        context = MagicMock(spec=PluginContext)
        context.config = {"vault": {"path": "/tmp/test-vault"}}
        context.logger = MagicMock()
        context.events = MagicMock()

        mock_entity = MagicMock()
        mock_entity.id = "test-123"
        mock_entity.path = Path("/tmp/test-vault/processed/test-123.md")

        context.vault = MagicMock()
        context.vault.create_entity.return_value = mock_entity

        self.normalizer = InboxNormalizer(context)

    def test_inbox_normalized_event_published(self) -> None:
        """Test that inbox.normalized event is published."""
        content = "Test task content"
        metadata = {
            "entity_type": "task",
            "confidence": 0.9,
            "title": "Test",
            "source": "telegram",
        }

        self.normalizer.create_entity(content, metadata)

        # Check that inbox.normalized event was published
        calls = self.normalizer.context.events.publish.call_args_list
        event_names = [call[0][0] for call in calls]

        assert "inbox.normalized" in event_names


class TestErrorHandling:
    """Test error handling."""

    def setup_method(self) -> None:
        """Setup test environment."""
        context = MagicMock(spec=PluginContext)
        context.config = {"vault": {"path": "/tmp/test-vault"}}
        context.logger = MagicMock()
        context.events = MagicMock()
        context.vault = MagicMock()
        context.vault.create_entity.side_effect = Exception("Test error")

        self.normalizer = InboxNormalizer(context)

    def test_create_entity_handles_exception(self) -> None:
        """Test that entity creation handles exceptions gracefully."""
        content = "Test content"
        metadata = {
            "entity_type": "task",
            "confidence": 0.9,
            "title": "Test",
        }

        result = self.normalizer.create_entity(content, metadata)

        assert not result["success"]
        assert "error" in result


class TestMultipleLanguages:
    """Test multi-language support."""

    def setup_method(self) -> None:
        """Setup test environment."""
        context = MagicMock(spec=PluginContext)
        context.config = {"vault": {"path": "/tmp/test-vault"}}
        context.logger = MagicMock()
        context.events = MagicMock()
        context.vault = None

        self.normalizer = InboxNormalizer(context)

    def test_classify_russian_task(self) -> None:
        """Test Russian task classification."""
        content = "Задача: реализовать новую функцию"
        classification = self.normalizer.classify_content(content)

        assert classification.entity_type == "task"

    def test_classify_english_task(self) -> None:
        """Test English task classification."""
        content = "Task: implement new feature"
        classification = self.normalizer.classify_content(content)

        assert classification.entity_type == "task"

    def test_classify_mixed_content(self) -> None:
        """Test mixed language content."""
        content = "Meeting tomorrow at офис"
        classification = self.normalizer.classify_content(content)

        # Should classify based on keywords present
        assert classification.entity_type in ["meeting", "event"]
