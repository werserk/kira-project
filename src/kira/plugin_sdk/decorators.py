"""
Декораторы для плагинов
"""
import functools
from typing import Any, Callable, Dict, List


def on_event(event_name: str):
    """
    Декоратор для обработчиков событий

    Args:
        event_name: Имя события для обработки
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # Добавляем метаданные для регистрации
        wrapper._is_event_handler = True
        wrapper._event_name = event_name

        return wrapper
    return decorator


def command(command_name: str):
    """
    Декоратор для команд плагина

    Args:
        command_name: Имя команды
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # Добавляем метаданные для регистрации
        wrapper._is_command = True
        wrapper._command_name = command_name

        return wrapper
    return decorator


def permission(perm: str):
    """
    Декоратор для проверки разрешений

    Args:
        perm: Требуемое разрешение
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # В реальной реализации здесь будет проверка разрешений
            print(f"🔐 Проверка разрешения: {perm}")
            return func(*args, **kwargs)

        # Добавляем метаданные
        wrapper._requires_permission = perm

        return wrapper
    return decorator


def timeout(seconds: int):
    """
    Декоратор для установки таймаута выполнения

    Args:
        seconds: Таймаут в секундах
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            print(f"⏱️  Таймаут: {seconds} секунд")
            return func(*args, **kwargs)

        # Добавляем метаданные
        wrapper._timeout = seconds

        return wrapper
    return decorator


def retry(max_attempts: int = 3, delay: float = 1.0):
    """
    Декоратор для повторных попыток выполнения

    Args:
        max_attempts: Максимальное количество попыток
        delay: Задержка между попытками в секундах
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        print(f"🔄 Попытка {attempt + 1}/{max_attempts} неудачна, повтор через {delay}с")
                        import time
                        time.sleep(delay)
                    else:
                        print(f"❌ Все попытки исчерпаны")
                        raise last_exception

            return None
        return wrapper
    return decorator
