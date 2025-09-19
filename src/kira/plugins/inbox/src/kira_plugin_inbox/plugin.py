"""
Реализация плагина Inbox Normalizer
"""
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from kira.plugin_sdk.context import PluginContext
from kira.plugin_sdk.decorators import command, on_event


class InboxNormalizer:
    """Нормализатор входящих элементов"""

    def __init__(self, context: PluginContext):
        self.context = context
        self.inbox_path = Path(context.config.get('vault', {}).get('path', '')) / 'inbox'
        self.processed_path = Path(context.config.get('vault', {}).get('path', '')) / 'processed'

        # Создаем необходимые директории
        self.inbox_path.mkdir(parents=True, exist_ok=True)
        self.processed_path.mkdir(parents=True, exist_ok=True)

    def normalize_text(self, text: str) -> str:
        """Нормализует текст сообщения"""
        # Убираем лишние пробелы
        text = re.sub(r'\s+', ' ', text.strip())

        # Нормализуем переносы строк
        text = re.sub(r'\n\s*\n', '\n\n', text)

        # Убираем специальные символы в начале/конце
        text = text.strip('.,!?;:')

        return text

    def extract_metadata(self, content: str, source: str = None) -> Dict[str, Any]:
        """Извлекает метаданные из контента"""
        metadata = {
            'source': source or 'unknown',
            'timestamp': datetime.now().isoformat(),
            'length': len(content),
            'type': 'text'
        }

        # Определяем тип контента
        if content.startswith('# '):
            metadata['type'] = 'note'
        elif any(keyword in content.lower() for keyword in ['задача', 'task', 'todo']):
            metadata['type'] = 'task'
        elif any(keyword in content.lower() for keyword in ['встреча', 'meeting', 'call']):
            metadata['type'] = 'event'
        elif content.startswith('http'):
            metadata['type'] = 'link'

        # Извлекаем теги
        tags = re.findall(r'#(\w+)', content)
        if tags:
            metadata['tags'] = tags

        # Извлекаем приоритет
        if any(keyword in content.lower() for keyword in ['срочно', 'urgent', 'важно']):
            metadata['priority'] = 'high'
        elif any(keyword in content.lower() for keyword in ['низкий', 'low']):
            metadata['priority'] = 'low'
        else:
            metadata['priority'] = 'medium'

        return metadata

    def create_normalized_file(self, content: str, metadata: Dict[str, Any]) -> Path:
        """Создает нормализованный файл"""
        # Генерируем имя файла
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        content_type = metadata.get('type', 'text')
        filename = f"{timestamp}_{content_type}.md"

        # Создаем содержимое файла
        frontmatter = {
            'title': content[:50] + '...' if len(content) > 50 else content,
            'created': metadata['timestamp'],
            'source': metadata['source'],
            'type': metadata['type'],
            'priority': metadata.get('priority', 'medium'),
            'tags': metadata.get('tags', []),
            'length': metadata['length']
        }

        # Формируем Markdown с frontmatter
        file_content = f"""---
{json.dumps(frontmatter, ensure_ascii=False, indent=2)}
---

# {frontmatter['title']}

{content}

---
*Обработано плагином Inbox Normalizer*
"""

        # Сохраняем файл
        file_path = self.processed_path / filename
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(file_content)

        return file_path

    def process_message(self, message: str, source: str = None) -> Dict[str, Any]:
        """Обрабатывает входящее сообщение"""
        # Нормализуем текст
        normalized_text = self.normalize_text(message)

        # Извлекаем метаданные
        metadata = self.extract_metadata(normalized_text, source)

        # Создаем нормализованный файл
        file_path = self.create_normalized_file(normalized_text, metadata)

        # Публикуем событие
        self.context.events.publish('inbox.normalized', {
            'file_path': str(file_path),
            'metadata': metadata,
            'original_length': len(message),
            'normalized_length': len(normalized_text)
        })

        return {
            'file_path': str(file_path),
            'metadata': metadata,
            'success': True
        }

    def process_file(self, file_path: Path) -> Dict[str, Any]:
        """Обрабатывает входящий файл"""
        try:
            # Читаем файл
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Обрабатываем как сообщение
            result = self.process_message(content, source=str(file_path))

            # Перемещаем обработанный файл
            processed_file = self.processed_path / f"processed_{file_path.name}"
            file_path.rename(processed_file)

            result['original_file'] = str(file_path)
            result['processed_file'] = str(processed_file)

            return result

        except Exception as e:
            return {
                'file_path': str(file_path),
                'error': str(e),
                'success': False
            }


# Глобальный экземпляр нормализатора
_normalizer: Optional[InboxNormalizer] = None


def activate(context: PluginContext) -> None:
    """Активация плагина"""
    global _normalizer
    _normalizer = InboxNormalizer(context)

    # Публикуем событие активации
    context.events.publish('plugin.activated', {
        'plugin': 'kira-inbox',
        'version': '0.1.0',
        'capabilities': ['normalize']
    })


@on_event('message.received')
def handle_message_received(context: PluginContext, event_data: Dict[str, Any]) -> None:
    """Обработчик события получения сообщения"""
    if not _normalizer:
        return

    message = event_data.get('message', '')
    source = event_data.get('source', 'unknown')

    result = _normalizer.process_message(message, source)

    if result['success']:
        context.logger.info(f"Сообщение нормализовано: {result['file_path']}")
    else:
        context.logger.error(f"Ошибка нормализации сообщения: {result.get('error')}")


@on_event('file.dropped')
def handle_file_dropped(context: PluginContext, event_data: Dict[str, Any]) -> None:
    """Обработчик события сброса файла"""
    if not _normalizer:
        return

    file_path = Path(event_data.get('file_path', ''))

    if not file_path.exists():
        context.logger.error(f"Файл не найден: {file_path}")
        return

    result = _normalizer.process_file(file_path)

    if result['success']:
        context.logger.info(f"Файл обработан: {result['file_path']}")
    else:
        context.logger.error(f"Ошибка обработки файла: {result.get('error')}")


@command('inbox.normalize')
def normalize_command(context: PluginContext, args: List[str]) -> str:
    """Команда нормализации inbox"""
    if not _normalizer:
        return "Плагин не активирован"

    if not args:
        return "Использование: inbox.normalize <сообщение>"

    message = ' '.join(args)
    result = _normalizer.process_message(message)

    if result['success']:
        return f"Сообщение нормализовано: {result['file_path']}"
    else:
        return f"Ошибка: {result.get('error')}"


def get_normalizer() -> Optional[InboxNormalizer]:
    """Возвращает экземпляр нормализатора"""
    return _normalizer
