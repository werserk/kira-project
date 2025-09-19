"""
Схемы валидации для Kira
"""
from pathlib import Path
from typing import List


def validate_vault_schemas(vault_path: str) -> List[str]:
    """
    Валидирует Vault против схем

    Args:
        vault_path: Путь к Vault

    Returns:
        Список ошибок валидации (пустой если валидно)
    """
    vault = Path(vault_path)

    if not vault.exists():
        return [f"Vault не найден: {vault_path}"]

    errors = []

    # Проверяем базовую структуру
    required_dirs = [".kira", "inbox", "projects", "archive"]
    for dir_name in required_dirs:
        dir_path = vault / dir_name
        if not dir_path.exists():
            errors.append(f"Отсутствует обязательная директория: {dir_name}")

    # Проверяем схемы
    schemas_dir = vault / ".kira" / "schemas"
    if schemas_dir.exists():
        schema_files = list(schemas_dir.glob("*.json"))
        if not schema_files:
            errors.append("Директория схем пуста")

    return errors
