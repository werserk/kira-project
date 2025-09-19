"""
Google Calendar Adapter
"""
from typing import Any, Dict, Optional


class GCalAdapter:
    """Адаптер для работы с Google Calendar"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def pull(self, calendar_id: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
        """Получает события из календаря"""
        print(f"Получаем события из календаря (дней: {days})")

        # Заглушка
        return {
            "events_count": 10,
            "processed_count": 8
        }

    def push(self, calendar_id: Optional[str] = None, dry_run: bool = False) -> Dict[str, Any]:
        """Отправляет события в календарь"""
        if dry_run:
            print("Dry-run: показываем что будет отправлено")
        else:
            print("Отправляем события в календарь")

        # Заглушка
        return {
            "events_count": 5,
            "sent_count": 3 if not dry_run else 0
        }
