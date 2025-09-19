"""
Тесты для плагина Inbox Normalizer
"""

import sys
import tempfile
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kira.plugin_sdk.context import PluginContext
from kira.plugins.inbox.src.kira_plugin_inbox.plugin import (
    InboxNormalizer,
    activate,
    handle_file_dropped,
    handle_message_received,
    normalize_command,
)


class TestInboxNormalizer:
    """Тесты для InboxNormalizer"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {"vault": {"path": self.temp_dir}}
        self.context = PluginContext(self.config)
        self.normalizer = InboxNormalizer(self.context)

    def teardown_method(self):
        """Очистка после каждого теста"""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_normalize_text(self):
        """Тест нормализации текста"""
        # Тест с лишними пробелами
        text = "  Это   тестовое   сообщение  с  лишними  пробелами  "
        normalized = self.normalizer.normalize_text(text)
        assert normalized == "Это тестовое сообщение с лишними пробелами"

        # Тест с переносами строк
        text = "Строка 1\n\n\nСтрока 2"
        normalized = self.normalizer.normalize_text(text)
        assert normalized == "Строка 1\n\nСтрока 2"

        # Тест с символами
        text = ".,!?;:Текст.,!?;:"
        normalized = self.normalizer.normalize_text(text)
        assert normalized == "Текст"

    def test_extract_metadata(self):
        """Тест извлечения метаданных"""
        # Тест заметки
        content = "# Важная заметка"
        metadata = self.normalizer.extract_metadata(content, "telegram")

        assert metadata["source"] == "telegram"
        assert metadata["type"] == "note"
        assert metadata["priority"] == "medium"

        # Тест задачи
        content = "Задача: сделать что-то важное"
        metadata = self.normalizer.extract_metadata(content)

        assert metadata["type"] == "task"
        assert metadata["priority"] == "high"

        # Тест с тегами
        content = "Сообщение с #тегом1 и #тегом2"
        metadata = self.normalizer.extract_metadata(content)

        assert "tags" in metadata
        assert "тегом1" in metadata["tags"]
        assert "тегом2" in metadata["tags"]

        # Тест ссылки
        content = "http://example.com"
        metadata = self.normalizer.extract_metadata(content)

        assert metadata["type"] == "link"

    def test_create_normalized_file(self):
        """Тест создания нормализованного файла"""
        content = "Тестовое сообщение"
        metadata = {
            "source": "test",
            "timestamp": "2024-01-01T12:00:00",
            "length": len(content),
            "type": "text",
            "priority": "medium",
            "tags": ["test"],
        }

        file_path = self.normalizer.create_normalized_file(content, metadata)

        assert file_path.exists()
        assert file_path.suffix == ".md"

        # Проверяем содержимое файла
        with open(file_path, encoding="utf-8") as f:
            file_content = f.read()

        assert "---" in file_content  # Frontmatter
        assert content in file_content
        assert "Inbox Normalizer" in file_content

    def test_process_message(self):
        """Тест обработки сообщения"""
        message = "Важное сообщение с #тегом"
        source = "telegram"

        result = self.normalizer.process_message(message, source)

        assert result["success"]
        assert "file_path" in result
        assert "metadata" in result

        # Проверяем, что файл создан
        file_path = Path(result["file_path"])
        assert file_path.exists()

        # Проверяем метаданные
        metadata = result["metadata"]
        assert metadata["source"] == source
        assert metadata["type"] == "text"
        assert "тегом" in metadata.get("tags", [])

    def test_process_file(self):
        """Тест обработки файла"""
        # Создаем тестовый файл
        test_file = self.normalizer.inbox_path / "test.txt"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("Содержимое тестового файла")

        result = self.normalizer.process_file(test_file)

        assert result["success"]
        assert "file_path" in result
        assert "original_file" in result
        assert "processed_file" in result

        # Проверяем, что оригинальный файл перемещен
        assert not test_file.exists()

        # Проверяем, что создан обработанный файл
        processed_file = Path(result["processed_file"])
        assert processed_file.exists()


class TestInboxPlugin:
    """Тесты для плагина inbox"""

    def setup_method(self):
        """Настройка перед каждым тестом"""
        self.temp_dir = tempfile.mkdtemp()
        self.config = {"vault": {"path": self.temp_dir}}
        self.context = PluginContext(self.config)

    def teardown_method(self):
        """Очистка после каждого теста"""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_activate(self):
        """Тест активации плагина"""
        # Активируем плагин
        activate(self.context)

        # Проверяем, что нормализатор создан
        from kira.plugins.inbox.src.kira_plugin_inbox.plugin import get_normalizer

        normalizer = get_normalizer()
        assert normalizer is not None

    def test_handle_message_received(self):
        """Тест обработки события получения сообщения"""
        # Активируем плагин
        activate(self.context)

        # Создаем тестовое событие
        event_data = {"message": "Тестовое сообщение", "source": "telegram"}

        # Обрабатываем событие
        handle_message_received(self.context, event_data)

        # Проверяем, что файл создан
        processed_dir = Path(self.temp_dir) / "processed"
        assert processed_dir.exists()

        # Должен быть создан хотя бы один файл
        files = list(processed_dir.glob("*.md"))
        assert len(files) > 0

    def test_handle_file_dropped(self):
        """Тест обработки события сброса файла"""
        # Активируем плагин
        activate(self.context)

        # Создаем тестовый файл
        test_file = Path(self.temp_dir) / "inbox" / "test.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("Содержимое файла")

        # Создаем тестовое событие
        event_data = {"file_path": str(test_file)}

        # Обрабатываем событие
        handle_file_dropped(self.context, event_data)

        # Проверяем, что файл обработан
        processed_dir = Path(self.temp_dir) / "processed"
        assert processed_dir.exists()

        # Должен быть создан обработанный файл
        files = list(processed_dir.glob("*.md"))
        assert len(files) > 0

    def test_normalize_command(self):
        """Тест команды нормализации"""
        # Активируем плагин
        activate(self.context)

        # Тестируем команду
        result = normalize_command(self.context, ["Тестовое", "сообщение"])

        assert "нормализовано" in result.lower()

        # Тестируем команду без аргументов
        result = normalize_command(self.context, [])
        assert "использование" in result.lower()


if __name__ == "__main__":
    import pytest

    pytest.main([__file__])
