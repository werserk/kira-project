"""Inbox plugin package."""

from .plugin import (
    InboxNormalizer,
    activate,
    get_normalizer,
    handle_file_dropped,
    handle_message_received,
    normalize_command,
)

__all__ = [
    "InboxNormalizer",
    "activate",
    "get_normalizer",
    "handle_file_dropped",
    "handle_message_received",
    "normalize_command",
]
