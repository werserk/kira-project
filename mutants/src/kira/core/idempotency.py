"""Event idempotency and deduplication (Phase 2, Point 7).

Ensures re-publishing the same logical event is a no-op.
Tracks seen events in SQLite with TTL cleanup.

event_id = sha256(source, external_id, normalized_payload)
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import timedelta
from pathlib import Path
from typing import Any

from .time import format_utc_iso8601, get_current_utc

__all__ = [
    "EventDedupeStore",
    "create_dedupe_store",
    "generate_event_id",
    "normalize_payload_for_hashing",
]
from inspect import signature as _mutmut_signature
from typing import Annotated
from typing import Callable
from typing import ClassVar


MutantDict = Annotated[dict[str, Callable], "Mutant"]


def _mutmut_trampoline(orig, mutants, call_args, call_kwargs, self_arg = None):
    """Forward call to original or mutated function, depending on the environment"""
    import os
    mutant_under_test = os.environ['MUTANT_UNDER_TEST']
    if mutant_under_test == 'fail':
        from mutmut.__main__ import MutmutProgrammaticFailException
        raise MutmutProgrammaticFailException('Failed programmatically')      
    elif mutant_under_test == 'stats':
        from mutmut.__main__ import record_trampoline_hit
        record_trampoline_hit(orig.__module__ + '.' + orig.__name__)
        result = orig(*call_args, **call_kwargs)
        return result
    prefix = orig.__module__ + '.' + orig.__name__ + '__mutmut_'
    if not mutant_under_test.startswith(prefix):
        result = orig(*call_args, **call_kwargs)
        return result
    mutant_name = mutant_under_test.rpartition('.')[-1]
    if self_arg:
        # call to a class method where self is not bound
        result = mutants[mutant_name](self_arg, *call_args, **call_kwargs)
    else:
        result = mutants[mutant_name](*call_args, **call_kwargs)
    return result


def x_normalize_payload_for_hashing__mutmut_orig(payload: dict[str, Any]) -> str:
    """Normalize payload for consistent hashing.

    Ensures identical logical payloads produce identical hashes.

    Parameters
    ----------
    payload
        Event payload to normalize

    Returns
    -------
    str
        Normalized JSON string for hashing
    """
    # Remove fields that don't affect logical identity
    normalized = payload.copy()

    # Remove timing/metadata fields that vary between retries
    for key in ["received_at", "processed_at", "retry_count", "trace_id"]:
        normalized.pop(key, None)

    # Sort keys for deterministic serialization
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def x_normalize_payload_for_hashing__mutmut_1(payload: dict[str, Any]) -> str:
    """Normalize payload for consistent hashing.

    Ensures identical logical payloads produce identical hashes.

    Parameters
    ----------
    payload
        Event payload to normalize

    Returns
    -------
    str
        Normalized JSON string for hashing
    """
    # Remove fields that don't affect logical identity
    normalized = None

    # Remove timing/metadata fields that vary between retries
    for key in ["received_at", "processed_at", "retry_count", "trace_id"]:
        normalized.pop(key, None)

    # Sort keys for deterministic serialization
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def x_normalize_payload_for_hashing__mutmut_2(payload: dict[str, Any]) -> str:
    """Normalize payload for consistent hashing.

    Ensures identical logical payloads produce identical hashes.

    Parameters
    ----------
    payload
        Event payload to normalize

    Returns
    -------
    str
        Normalized JSON string for hashing
    """
    # Remove fields that don't affect logical identity
    normalized = payload.copy()

    # Remove timing/metadata fields that vary between retries
    for key in ["XXreceived_atXX", "processed_at", "retry_count", "trace_id"]:
        normalized.pop(key, None)

    # Sort keys for deterministic serialization
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def x_normalize_payload_for_hashing__mutmut_3(payload: dict[str, Any]) -> str:
    """Normalize payload for consistent hashing.

    Ensures identical logical payloads produce identical hashes.

    Parameters
    ----------
    payload
        Event payload to normalize

    Returns
    -------
    str
        Normalized JSON string for hashing
    """
    # Remove fields that don't affect logical identity
    normalized = payload.copy()

    # Remove timing/metadata fields that vary between retries
    for key in ["RECEIVED_AT", "processed_at", "retry_count", "trace_id"]:
        normalized.pop(key, None)

    # Sort keys for deterministic serialization
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def x_normalize_payload_for_hashing__mutmut_4(payload: dict[str, Any]) -> str:
    """Normalize payload for consistent hashing.

    Ensures identical logical payloads produce identical hashes.

    Parameters
    ----------
    payload
        Event payload to normalize

    Returns
    -------
    str
        Normalized JSON string for hashing
    """
    # Remove fields that don't affect logical identity
    normalized = payload.copy()

    # Remove timing/metadata fields that vary between retries
    for key in ["received_at", "XXprocessed_atXX", "retry_count", "trace_id"]:
        normalized.pop(key, None)

    # Sort keys for deterministic serialization
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def x_normalize_payload_for_hashing__mutmut_5(payload: dict[str, Any]) -> str:
    """Normalize payload for consistent hashing.

    Ensures identical logical payloads produce identical hashes.

    Parameters
    ----------
    payload
        Event payload to normalize

    Returns
    -------
    str
        Normalized JSON string for hashing
    """
    # Remove fields that don't affect logical identity
    normalized = payload.copy()

    # Remove timing/metadata fields that vary between retries
    for key in ["received_at", "PROCESSED_AT", "retry_count", "trace_id"]:
        normalized.pop(key, None)

    # Sort keys for deterministic serialization
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def x_normalize_payload_for_hashing__mutmut_6(payload: dict[str, Any]) -> str:
    """Normalize payload for consistent hashing.

    Ensures identical logical payloads produce identical hashes.

    Parameters
    ----------
    payload
        Event payload to normalize

    Returns
    -------
    str
        Normalized JSON string for hashing
    """
    # Remove fields that don't affect logical identity
    normalized = payload.copy()

    # Remove timing/metadata fields that vary between retries
    for key in ["received_at", "processed_at", "XXretry_countXX", "trace_id"]:
        normalized.pop(key, None)

    # Sort keys for deterministic serialization
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def x_normalize_payload_for_hashing__mutmut_7(payload: dict[str, Any]) -> str:
    """Normalize payload for consistent hashing.

    Ensures identical logical payloads produce identical hashes.

    Parameters
    ----------
    payload
        Event payload to normalize

    Returns
    -------
    str
        Normalized JSON string for hashing
    """
    # Remove fields that don't affect logical identity
    normalized = payload.copy()

    # Remove timing/metadata fields that vary between retries
    for key in ["received_at", "processed_at", "RETRY_COUNT", "trace_id"]:
        normalized.pop(key, None)

    # Sort keys for deterministic serialization
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def x_normalize_payload_for_hashing__mutmut_8(payload: dict[str, Any]) -> str:
    """Normalize payload for consistent hashing.

    Ensures identical logical payloads produce identical hashes.

    Parameters
    ----------
    payload
        Event payload to normalize

    Returns
    -------
    str
        Normalized JSON string for hashing
    """
    # Remove fields that don't affect logical identity
    normalized = payload.copy()

    # Remove timing/metadata fields that vary between retries
    for key in ["received_at", "processed_at", "retry_count", "XXtrace_idXX"]:
        normalized.pop(key, None)

    # Sort keys for deterministic serialization
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def x_normalize_payload_for_hashing__mutmut_9(payload: dict[str, Any]) -> str:
    """Normalize payload for consistent hashing.

    Ensures identical logical payloads produce identical hashes.

    Parameters
    ----------
    payload
        Event payload to normalize

    Returns
    -------
    str
        Normalized JSON string for hashing
    """
    # Remove fields that don't affect logical identity
    normalized = payload.copy()

    # Remove timing/metadata fields that vary between retries
    for key in ["received_at", "processed_at", "retry_count", "TRACE_ID"]:
        normalized.pop(key, None)

    # Sort keys for deterministic serialization
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def x_normalize_payload_for_hashing__mutmut_10(payload: dict[str, Any]) -> str:
    """Normalize payload for consistent hashing.

    Ensures identical logical payloads produce identical hashes.

    Parameters
    ----------
    payload
        Event payload to normalize

    Returns
    -------
    str
        Normalized JSON string for hashing
    """
    # Remove fields that don't affect logical identity
    normalized = payload.copy()

    # Remove timing/metadata fields that vary between retries
    for key in ["received_at", "processed_at", "retry_count", "trace_id"]:
        normalized.pop(None, None)

    # Sort keys for deterministic serialization
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def x_normalize_payload_for_hashing__mutmut_11(payload: dict[str, Any]) -> str:
    """Normalize payload for consistent hashing.

    Ensures identical logical payloads produce identical hashes.

    Parameters
    ----------
    payload
        Event payload to normalize

    Returns
    -------
    str
        Normalized JSON string for hashing
    """
    # Remove fields that don't affect logical identity
    normalized = payload.copy()

    # Remove timing/metadata fields that vary between retries
    for key in ["received_at", "processed_at", "retry_count", "trace_id"]:
        normalized.pop(None)

    # Sort keys for deterministic serialization
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def x_normalize_payload_for_hashing__mutmut_12(payload: dict[str, Any]) -> str:
    """Normalize payload for consistent hashing.

    Ensures identical logical payloads produce identical hashes.

    Parameters
    ----------
    payload
        Event payload to normalize

    Returns
    -------
    str
        Normalized JSON string for hashing
    """
    # Remove fields that don't affect logical identity
    normalized = payload.copy()

    # Remove timing/metadata fields that vary between retries
    for key in ["received_at", "processed_at", "retry_count", "trace_id"]:
        normalized.pop(key, )

    # Sort keys for deterministic serialization
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def x_normalize_payload_for_hashing__mutmut_13(payload: dict[str, Any]) -> str:
    """Normalize payload for consistent hashing.

    Ensures identical logical payloads produce identical hashes.

    Parameters
    ----------
    payload
        Event payload to normalize

    Returns
    -------
    str
        Normalized JSON string for hashing
    """
    # Remove fields that don't affect logical identity
    normalized = payload.copy()

    # Remove timing/metadata fields that vary between retries
    for key in ["received_at", "processed_at", "retry_count", "trace_id"]:
        normalized.pop(key, None)

    # Sort keys for deterministic serialization
    return json.dumps(None, sort_keys=True, separators=(",", ":"))


def x_normalize_payload_for_hashing__mutmut_14(payload: dict[str, Any]) -> str:
    """Normalize payload for consistent hashing.

    Ensures identical logical payloads produce identical hashes.

    Parameters
    ----------
    payload
        Event payload to normalize

    Returns
    -------
    str
        Normalized JSON string for hashing
    """
    # Remove fields that don't affect logical identity
    normalized = payload.copy()

    # Remove timing/metadata fields that vary between retries
    for key in ["received_at", "processed_at", "retry_count", "trace_id"]:
        normalized.pop(key, None)

    # Sort keys for deterministic serialization
    return json.dumps(normalized, sort_keys=None, separators=(",", ":"))


def x_normalize_payload_for_hashing__mutmut_15(payload: dict[str, Any]) -> str:
    """Normalize payload for consistent hashing.

    Ensures identical logical payloads produce identical hashes.

    Parameters
    ----------
    payload
        Event payload to normalize

    Returns
    -------
    str
        Normalized JSON string for hashing
    """
    # Remove fields that don't affect logical identity
    normalized = payload.copy()

    # Remove timing/metadata fields that vary between retries
    for key in ["received_at", "processed_at", "retry_count", "trace_id"]:
        normalized.pop(key, None)

    # Sort keys for deterministic serialization
    return json.dumps(normalized, sort_keys=True, separators=None)


def x_normalize_payload_for_hashing__mutmut_16(payload: dict[str, Any]) -> str:
    """Normalize payload for consistent hashing.

    Ensures identical logical payloads produce identical hashes.

    Parameters
    ----------
    payload
        Event payload to normalize

    Returns
    -------
    str
        Normalized JSON string for hashing
    """
    # Remove fields that don't affect logical identity
    normalized = payload.copy()

    # Remove timing/metadata fields that vary between retries
    for key in ["received_at", "processed_at", "retry_count", "trace_id"]:
        normalized.pop(key, None)

    # Sort keys for deterministic serialization
    return json.dumps(sort_keys=True, separators=(",", ":"))


def x_normalize_payload_for_hashing__mutmut_17(payload: dict[str, Any]) -> str:
    """Normalize payload for consistent hashing.

    Ensures identical logical payloads produce identical hashes.

    Parameters
    ----------
    payload
        Event payload to normalize

    Returns
    -------
    str
        Normalized JSON string for hashing
    """
    # Remove fields that don't affect logical identity
    normalized = payload.copy()

    # Remove timing/metadata fields that vary between retries
    for key in ["received_at", "processed_at", "retry_count", "trace_id"]:
        normalized.pop(key, None)

    # Sort keys for deterministic serialization
    return json.dumps(normalized, separators=(",", ":"))


def x_normalize_payload_for_hashing__mutmut_18(payload: dict[str, Any]) -> str:
    """Normalize payload for consistent hashing.

    Ensures identical logical payloads produce identical hashes.

    Parameters
    ----------
    payload
        Event payload to normalize

    Returns
    -------
    str
        Normalized JSON string for hashing
    """
    # Remove fields that don't affect logical identity
    normalized = payload.copy()

    # Remove timing/metadata fields that vary between retries
    for key in ["received_at", "processed_at", "retry_count", "trace_id"]:
        normalized.pop(key, None)

    # Sort keys for deterministic serialization
    return json.dumps(normalized, sort_keys=True, )


def x_normalize_payload_for_hashing__mutmut_19(payload: dict[str, Any]) -> str:
    """Normalize payload for consistent hashing.

    Ensures identical logical payloads produce identical hashes.

    Parameters
    ----------
    payload
        Event payload to normalize

    Returns
    -------
    str
        Normalized JSON string for hashing
    """
    # Remove fields that don't affect logical identity
    normalized = payload.copy()

    # Remove timing/metadata fields that vary between retries
    for key in ["received_at", "processed_at", "retry_count", "trace_id"]:
        normalized.pop(key, None)

    # Sort keys for deterministic serialization
    return json.dumps(normalized, sort_keys=False, separators=(",", ":"))


def x_normalize_payload_for_hashing__mutmut_20(payload: dict[str, Any]) -> str:
    """Normalize payload for consistent hashing.

    Ensures identical logical payloads produce identical hashes.

    Parameters
    ----------
    payload
        Event payload to normalize

    Returns
    -------
    str
        Normalized JSON string for hashing
    """
    # Remove fields that don't affect logical identity
    normalized = payload.copy()

    # Remove timing/metadata fields that vary between retries
    for key in ["received_at", "processed_at", "retry_count", "trace_id"]:
        normalized.pop(key, None)

    # Sort keys for deterministic serialization
    return json.dumps(normalized, sort_keys=True, separators=("XX,XX", ":"))


def x_normalize_payload_for_hashing__mutmut_21(payload: dict[str, Any]) -> str:
    """Normalize payload for consistent hashing.

    Ensures identical logical payloads produce identical hashes.

    Parameters
    ----------
    payload
        Event payload to normalize

    Returns
    -------
    str
        Normalized JSON string for hashing
    """
    # Remove fields that don't affect logical identity
    normalized = payload.copy()

    # Remove timing/metadata fields that vary between retries
    for key in ["received_at", "processed_at", "retry_count", "trace_id"]:
        normalized.pop(key, None)

    # Sort keys for deterministic serialization
    return json.dumps(normalized, sort_keys=True, separators=(",", "XX:XX"))

x_normalize_payload_for_hashing__mutmut_mutants : ClassVar[MutantDict] = {
'x_normalize_payload_for_hashing__mutmut_1': x_normalize_payload_for_hashing__mutmut_1, 
    'x_normalize_payload_for_hashing__mutmut_2': x_normalize_payload_for_hashing__mutmut_2, 
    'x_normalize_payload_for_hashing__mutmut_3': x_normalize_payload_for_hashing__mutmut_3, 
    'x_normalize_payload_for_hashing__mutmut_4': x_normalize_payload_for_hashing__mutmut_4, 
    'x_normalize_payload_for_hashing__mutmut_5': x_normalize_payload_for_hashing__mutmut_5, 
    'x_normalize_payload_for_hashing__mutmut_6': x_normalize_payload_for_hashing__mutmut_6, 
    'x_normalize_payload_for_hashing__mutmut_7': x_normalize_payload_for_hashing__mutmut_7, 
    'x_normalize_payload_for_hashing__mutmut_8': x_normalize_payload_for_hashing__mutmut_8, 
    'x_normalize_payload_for_hashing__mutmut_9': x_normalize_payload_for_hashing__mutmut_9, 
    'x_normalize_payload_for_hashing__mutmut_10': x_normalize_payload_for_hashing__mutmut_10, 
    'x_normalize_payload_for_hashing__mutmut_11': x_normalize_payload_for_hashing__mutmut_11, 
    'x_normalize_payload_for_hashing__mutmut_12': x_normalize_payload_for_hashing__mutmut_12, 
    'x_normalize_payload_for_hashing__mutmut_13': x_normalize_payload_for_hashing__mutmut_13, 
    'x_normalize_payload_for_hashing__mutmut_14': x_normalize_payload_for_hashing__mutmut_14, 
    'x_normalize_payload_for_hashing__mutmut_15': x_normalize_payload_for_hashing__mutmut_15, 
    'x_normalize_payload_for_hashing__mutmut_16': x_normalize_payload_for_hashing__mutmut_16, 
    'x_normalize_payload_for_hashing__mutmut_17': x_normalize_payload_for_hashing__mutmut_17, 
    'x_normalize_payload_for_hashing__mutmut_18': x_normalize_payload_for_hashing__mutmut_18, 
    'x_normalize_payload_for_hashing__mutmut_19': x_normalize_payload_for_hashing__mutmut_19, 
    'x_normalize_payload_for_hashing__mutmut_20': x_normalize_payload_for_hashing__mutmut_20, 
    'x_normalize_payload_for_hashing__mutmut_21': x_normalize_payload_for_hashing__mutmut_21
}

def normalize_payload_for_hashing(*args, **kwargs):
    result = _mutmut_trampoline(x_normalize_payload_for_hashing__mutmut_orig, x_normalize_payload_for_hashing__mutmut_mutants, args, kwargs)
    return result 

normalize_payload_for_hashing.__signature__ = _mutmut_signature(x_normalize_payload_for_hashing__mutmut_orig)
x_normalize_payload_for_hashing__mutmut_orig.__name__ = 'x_normalize_payload_for_hashing'


def x_generate_event_id__mutmut_orig(
    source: str,
    external_id: str,
    payload: dict[str, Any],
) -> str:
    """Generate deterministic event ID (Phase 2, Point 7).

    event_id = sha256(source, external_id, normalized_payload)

    Identical logical events produce identical IDs,
    enabling deduplication.

    Parameters
    ----------
    source
        Event source (e.g., "telegram", "gcal", "cli")
    external_id
        External identifier from source system
    payload
        Event payload

    Returns
    -------
    str
        Event ID (hex-encoded SHA-256)

    Example
    -------
    >>> payload = {"message": "test", "user": "alice"}
    >>> event_id = generate_event_id("telegram", "msg-123", payload)
    >>> len(event_id)
    64
    """
    # Normalize payload
    normalized_payload = normalize_payload_for_hashing(payload)

    # Combine components
    components = [
        source,
        external_id,
        normalized_payload,
    ]
    combined = "|".join(components)

    # Hash
    hash_obj = hashlib.sha256(combined.encode("utf-8"))
    return hash_obj.hexdigest()


def x_generate_event_id__mutmut_1(
    source: str,
    external_id: str,
    payload: dict[str, Any],
) -> str:
    """Generate deterministic event ID (Phase 2, Point 7).

    event_id = sha256(source, external_id, normalized_payload)

    Identical logical events produce identical IDs,
    enabling deduplication.

    Parameters
    ----------
    source
        Event source (e.g., "telegram", "gcal", "cli")
    external_id
        External identifier from source system
    payload
        Event payload

    Returns
    -------
    str
        Event ID (hex-encoded SHA-256)

    Example
    -------
    >>> payload = {"message": "test", "user": "alice"}
    >>> event_id = generate_event_id("telegram", "msg-123", payload)
    >>> len(event_id)
    64
    """
    # Normalize payload
    normalized_payload = None

    # Combine components
    components = [
        source,
        external_id,
        normalized_payload,
    ]
    combined = "|".join(components)

    # Hash
    hash_obj = hashlib.sha256(combined.encode("utf-8"))
    return hash_obj.hexdigest()


def x_generate_event_id__mutmut_2(
    source: str,
    external_id: str,
    payload: dict[str, Any],
) -> str:
    """Generate deterministic event ID (Phase 2, Point 7).

    event_id = sha256(source, external_id, normalized_payload)

    Identical logical events produce identical IDs,
    enabling deduplication.

    Parameters
    ----------
    source
        Event source (e.g., "telegram", "gcal", "cli")
    external_id
        External identifier from source system
    payload
        Event payload

    Returns
    -------
    str
        Event ID (hex-encoded SHA-256)

    Example
    -------
    >>> payload = {"message": "test", "user": "alice"}
    >>> event_id = generate_event_id("telegram", "msg-123", payload)
    >>> len(event_id)
    64
    """
    # Normalize payload
    normalized_payload = normalize_payload_for_hashing(None)

    # Combine components
    components = [
        source,
        external_id,
        normalized_payload,
    ]
    combined = "|".join(components)

    # Hash
    hash_obj = hashlib.sha256(combined.encode("utf-8"))
    return hash_obj.hexdigest()


def x_generate_event_id__mutmut_3(
    source: str,
    external_id: str,
    payload: dict[str, Any],
) -> str:
    """Generate deterministic event ID (Phase 2, Point 7).

    event_id = sha256(source, external_id, normalized_payload)

    Identical logical events produce identical IDs,
    enabling deduplication.

    Parameters
    ----------
    source
        Event source (e.g., "telegram", "gcal", "cli")
    external_id
        External identifier from source system
    payload
        Event payload

    Returns
    -------
    str
        Event ID (hex-encoded SHA-256)

    Example
    -------
    >>> payload = {"message": "test", "user": "alice"}
    >>> event_id = generate_event_id("telegram", "msg-123", payload)
    >>> len(event_id)
    64
    """
    # Normalize payload
    normalized_payload = normalize_payload_for_hashing(payload)

    # Combine components
    components = None
    combined = "|".join(components)

    # Hash
    hash_obj = hashlib.sha256(combined.encode("utf-8"))
    return hash_obj.hexdigest()


def x_generate_event_id__mutmut_4(
    source: str,
    external_id: str,
    payload: dict[str, Any],
) -> str:
    """Generate deterministic event ID (Phase 2, Point 7).

    event_id = sha256(source, external_id, normalized_payload)

    Identical logical events produce identical IDs,
    enabling deduplication.

    Parameters
    ----------
    source
        Event source (e.g., "telegram", "gcal", "cli")
    external_id
        External identifier from source system
    payload
        Event payload

    Returns
    -------
    str
        Event ID (hex-encoded SHA-256)

    Example
    -------
    >>> payload = {"message": "test", "user": "alice"}
    >>> event_id = generate_event_id("telegram", "msg-123", payload)
    >>> len(event_id)
    64
    """
    # Normalize payload
    normalized_payload = normalize_payload_for_hashing(payload)

    # Combine components
    components = [
        source,
        external_id,
        normalized_payload,
    ]
    combined = None

    # Hash
    hash_obj = hashlib.sha256(combined.encode("utf-8"))
    return hash_obj.hexdigest()


def x_generate_event_id__mutmut_5(
    source: str,
    external_id: str,
    payload: dict[str, Any],
) -> str:
    """Generate deterministic event ID (Phase 2, Point 7).

    event_id = sha256(source, external_id, normalized_payload)

    Identical logical events produce identical IDs,
    enabling deduplication.

    Parameters
    ----------
    source
        Event source (e.g., "telegram", "gcal", "cli")
    external_id
        External identifier from source system
    payload
        Event payload

    Returns
    -------
    str
        Event ID (hex-encoded SHA-256)

    Example
    -------
    >>> payload = {"message": "test", "user": "alice"}
    >>> event_id = generate_event_id("telegram", "msg-123", payload)
    >>> len(event_id)
    64
    """
    # Normalize payload
    normalized_payload = normalize_payload_for_hashing(payload)

    # Combine components
    components = [
        source,
        external_id,
        normalized_payload,
    ]
    combined = "|".join(None)

    # Hash
    hash_obj = hashlib.sha256(combined.encode("utf-8"))
    return hash_obj.hexdigest()


def x_generate_event_id__mutmut_6(
    source: str,
    external_id: str,
    payload: dict[str, Any],
) -> str:
    """Generate deterministic event ID (Phase 2, Point 7).

    event_id = sha256(source, external_id, normalized_payload)

    Identical logical events produce identical IDs,
    enabling deduplication.

    Parameters
    ----------
    source
        Event source (e.g., "telegram", "gcal", "cli")
    external_id
        External identifier from source system
    payload
        Event payload

    Returns
    -------
    str
        Event ID (hex-encoded SHA-256)

    Example
    -------
    >>> payload = {"message": "test", "user": "alice"}
    >>> event_id = generate_event_id("telegram", "msg-123", payload)
    >>> len(event_id)
    64
    """
    # Normalize payload
    normalized_payload = normalize_payload_for_hashing(payload)

    # Combine components
    components = [
        source,
        external_id,
        normalized_payload,
    ]
    combined = "XX|XX".join(components)

    # Hash
    hash_obj = hashlib.sha256(combined.encode("utf-8"))
    return hash_obj.hexdigest()


def x_generate_event_id__mutmut_7(
    source: str,
    external_id: str,
    payload: dict[str, Any],
) -> str:
    """Generate deterministic event ID (Phase 2, Point 7).

    event_id = sha256(source, external_id, normalized_payload)

    Identical logical events produce identical IDs,
    enabling deduplication.

    Parameters
    ----------
    source
        Event source (e.g., "telegram", "gcal", "cli")
    external_id
        External identifier from source system
    payload
        Event payload

    Returns
    -------
    str
        Event ID (hex-encoded SHA-256)

    Example
    -------
    >>> payload = {"message": "test", "user": "alice"}
    >>> event_id = generate_event_id("telegram", "msg-123", payload)
    >>> len(event_id)
    64
    """
    # Normalize payload
    normalized_payload = normalize_payload_for_hashing(payload)

    # Combine components
    components = [
        source,
        external_id,
        normalized_payload,
    ]
    combined = "|".join(components)

    # Hash
    hash_obj = None
    return hash_obj.hexdigest()


def x_generate_event_id__mutmut_8(
    source: str,
    external_id: str,
    payload: dict[str, Any],
) -> str:
    """Generate deterministic event ID (Phase 2, Point 7).

    event_id = sha256(source, external_id, normalized_payload)

    Identical logical events produce identical IDs,
    enabling deduplication.

    Parameters
    ----------
    source
        Event source (e.g., "telegram", "gcal", "cli")
    external_id
        External identifier from source system
    payload
        Event payload

    Returns
    -------
    str
        Event ID (hex-encoded SHA-256)

    Example
    -------
    >>> payload = {"message": "test", "user": "alice"}
    >>> event_id = generate_event_id("telegram", "msg-123", payload)
    >>> len(event_id)
    64
    """
    # Normalize payload
    normalized_payload = normalize_payload_for_hashing(payload)

    # Combine components
    components = [
        source,
        external_id,
        normalized_payload,
    ]
    combined = "|".join(components)

    # Hash
    hash_obj = hashlib.sha256(None)
    return hash_obj.hexdigest()


def x_generate_event_id__mutmut_9(
    source: str,
    external_id: str,
    payload: dict[str, Any],
) -> str:
    """Generate deterministic event ID (Phase 2, Point 7).

    event_id = sha256(source, external_id, normalized_payload)

    Identical logical events produce identical IDs,
    enabling deduplication.

    Parameters
    ----------
    source
        Event source (e.g., "telegram", "gcal", "cli")
    external_id
        External identifier from source system
    payload
        Event payload

    Returns
    -------
    str
        Event ID (hex-encoded SHA-256)

    Example
    -------
    >>> payload = {"message": "test", "user": "alice"}
    >>> event_id = generate_event_id("telegram", "msg-123", payload)
    >>> len(event_id)
    64
    """
    # Normalize payload
    normalized_payload = normalize_payload_for_hashing(payload)

    # Combine components
    components = [
        source,
        external_id,
        normalized_payload,
    ]
    combined = "|".join(components)

    # Hash
    hash_obj = hashlib.sha256(combined.encode(None))
    return hash_obj.hexdigest()


def x_generate_event_id__mutmut_10(
    source: str,
    external_id: str,
    payload: dict[str, Any],
) -> str:
    """Generate deterministic event ID (Phase 2, Point 7).

    event_id = sha256(source, external_id, normalized_payload)

    Identical logical events produce identical IDs,
    enabling deduplication.

    Parameters
    ----------
    source
        Event source (e.g., "telegram", "gcal", "cli")
    external_id
        External identifier from source system
    payload
        Event payload

    Returns
    -------
    str
        Event ID (hex-encoded SHA-256)

    Example
    -------
    >>> payload = {"message": "test", "user": "alice"}
    >>> event_id = generate_event_id("telegram", "msg-123", payload)
    >>> len(event_id)
    64
    """
    # Normalize payload
    normalized_payload = normalize_payload_for_hashing(payload)

    # Combine components
    components = [
        source,
        external_id,
        normalized_payload,
    ]
    combined = "|".join(components)

    # Hash
    hash_obj = hashlib.sha256(combined.encode("XXutf-8XX"))
    return hash_obj.hexdigest()


def x_generate_event_id__mutmut_11(
    source: str,
    external_id: str,
    payload: dict[str, Any],
) -> str:
    """Generate deterministic event ID (Phase 2, Point 7).

    event_id = sha256(source, external_id, normalized_payload)

    Identical logical events produce identical IDs,
    enabling deduplication.

    Parameters
    ----------
    source
        Event source (e.g., "telegram", "gcal", "cli")
    external_id
        External identifier from source system
    payload
        Event payload

    Returns
    -------
    str
        Event ID (hex-encoded SHA-256)

    Example
    -------
    >>> payload = {"message": "test", "user": "alice"}
    >>> event_id = generate_event_id("telegram", "msg-123", payload)
    >>> len(event_id)
    64
    """
    # Normalize payload
    normalized_payload = normalize_payload_for_hashing(payload)

    # Combine components
    components = [
        source,
        external_id,
        normalized_payload,
    ]
    combined = "|".join(components)

    # Hash
    hash_obj = hashlib.sha256(combined.encode("UTF-8"))
    return hash_obj.hexdigest()

x_generate_event_id__mutmut_mutants : ClassVar[MutantDict] = {
'x_generate_event_id__mutmut_1': x_generate_event_id__mutmut_1, 
    'x_generate_event_id__mutmut_2': x_generate_event_id__mutmut_2, 
    'x_generate_event_id__mutmut_3': x_generate_event_id__mutmut_3, 
    'x_generate_event_id__mutmut_4': x_generate_event_id__mutmut_4, 
    'x_generate_event_id__mutmut_5': x_generate_event_id__mutmut_5, 
    'x_generate_event_id__mutmut_6': x_generate_event_id__mutmut_6, 
    'x_generate_event_id__mutmut_7': x_generate_event_id__mutmut_7, 
    'x_generate_event_id__mutmut_8': x_generate_event_id__mutmut_8, 
    'x_generate_event_id__mutmut_9': x_generate_event_id__mutmut_9, 
    'x_generate_event_id__mutmut_10': x_generate_event_id__mutmut_10, 
    'x_generate_event_id__mutmut_11': x_generate_event_id__mutmut_11
}

def generate_event_id(*args, **kwargs):
    result = _mutmut_trampoline(x_generate_event_id__mutmut_orig, x_generate_event_id__mutmut_mutants, args, kwargs)
    return result 

generate_event_id.__signature__ = _mutmut_signature(x_generate_event_id__mutmut_orig)
x_generate_event_id__mutmut_orig.__name__ = 'x_generate_event_id'


class EventDedupeStore:
    """Dedupe store for tracking seen events (Phase 2, Point 7).

    Tracks seen_events(event_id, first_seen_ts) in SQLite.
    Provides TTL-based cleanup.

    Re-publishing the same logical event is a no-op.
    """

    def xǁEventDedupeStoreǁ__init____mutmut_orig(self, db_path: Path | str) -> None:
        """Initialize dedupe store.

        Parameters
        ----------
        db_path
            Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None
        self._init_database()

    def xǁEventDedupeStoreǁ__init____mutmut_1(self, db_path: Path | str) -> None:
        """Initialize dedupe store.

        Parameters
        ----------
        db_path
            Path to SQLite database file
        """
        self.db_path = None
        self._conn: sqlite3.Connection | None = None
        self._init_database()

    def xǁEventDedupeStoreǁ__init____mutmut_2(self, db_path: Path | str) -> None:
        """Initialize dedupe store.

        Parameters
        ----------
        db_path
            Path to SQLite database file
        """
        self.db_path = Path(None)
        self._conn: sqlite3.Connection | None = None
        self._init_database()

    def xǁEventDedupeStoreǁ__init____mutmut_3(self, db_path: Path | str) -> None:
        """Initialize dedupe store.

        Parameters
        ----------
        db_path
            Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = ""
        self._init_database()
    
    xǁEventDedupeStoreǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁEventDedupeStoreǁ__init____mutmut_1': xǁEventDedupeStoreǁ__init____mutmut_1, 
        'xǁEventDedupeStoreǁ__init____mutmut_2': xǁEventDedupeStoreǁ__init____mutmut_2, 
        'xǁEventDedupeStoreǁ__init____mutmut_3': xǁEventDedupeStoreǁ__init____mutmut_3
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁEventDedupeStoreǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁEventDedupeStoreǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁEventDedupeStoreǁ__init____mutmut_orig)
    xǁEventDedupeStoreǁ__init____mutmut_orig.__name__ = 'xǁEventDedupeStoreǁ__init__'

    def xǁEventDedupeStoreǁ_init_database__mutmut_orig(self) -> None:
        """Initialize database schema."""
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = self._get_connection()
        cursor = conn.cursor()

        # Create seen_events table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_events (
                event_id TEXT PRIMARY KEY,
                first_seen_ts TEXT NOT NULL,
                last_seen_ts TEXT NOT NULL,
                seen_count INTEGER NOT NULL DEFAULT 1,
                source TEXT,
                external_id TEXT,
                metadata TEXT
            )
        """
        )

        # Index for TTL cleanup
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_seen_events_first_seen
            ON seen_events(first_seen_ts)
        """
        )

        conn.commit()

    def xǁEventDedupeStoreǁ_init_database__mutmut_1(self) -> None:
        """Initialize database schema."""
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=None, exist_ok=True)

        conn = self._get_connection()
        cursor = conn.cursor()

        # Create seen_events table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_events (
                event_id TEXT PRIMARY KEY,
                first_seen_ts TEXT NOT NULL,
                last_seen_ts TEXT NOT NULL,
                seen_count INTEGER NOT NULL DEFAULT 1,
                source TEXT,
                external_id TEXT,
                metadata TEXT
            )
        """
        )

        # Index for TTL cleanup
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_seen_events_first_seen
            ON seen_events(first_seen_ts)
        """
        )

        conn.commit()

    def xǁEventDedupeStoreǁ_init_database__mutmut_2(self) -> None:
        """Initialize database schema."""
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=None)

        conn = self._get_connection()
        cursor = conn.cursor()

        # Create seen_events table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_events (
                event_id TEXT PRIMARY KEY,
                first_seen_ts TEXT NOT NULL,
                last_seen_ts TEXT NOT NULL,
                seen_count INTEGER NOT NULL DEFAULT 1,
                source TEXT,
                external_id TEXT,
                metadata TEXT
            )
        """
        )

        # Index for TTL cleanup
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_seen_events_first_seen
            ON seen_events(first_seen_ts)
        """
        )

        conn.commit()

    def xǁEventDedupeStoreǁ_init_database__mutmut_3(self) -> None:
        """Initialize database schema."""
        # Ensure directory exists
        self.db_path.parent.mkdir(exist_ok=True)

        conn = self._get_connection()
        cursor = conn.cursor()

        # Create seen_events table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_events (
                event_id TEXT PRIMARY KEY,
                first_seen_ts TEXT NOT NULL,
                last_seen_ts TEXT NOT NULL,
                seen_count INTEGER NOT NULL DEFAULT 1,
                source TEXT,
                external_id TEXT,
                metadata TEXT
            )
        """
        )

        # Index for TTL cleanup
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_seen_events_first_seen
            ON seen_events(first_seen_ts)
        """
        )

        conn.commit()

    def xǁEventDedupeStoreǁ_init_database__mutmut_4(self) -> None:
        """Initialize database schema."""
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, )

        conn = self._get_connection()
        cursor = conn.cursor()

        # Create seen_events table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_events (
                event_id TEXT PRIMARY KEY,
                first_seen_ts TEXT NOT NULL,
                last_seen_ts TEXT NOT NULL,
                seen_count INTEGER NOT NULL DEFAULT 1,
                source TEXT,
                external_id TEXT,
                metadata TEXT
            )
        """
        )

        # Index for TTL cleanup
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_seen_events_first_seen
            ON seen_events(first_seen_ts)
        """
        )

        conn.commit()

    def xǁEventDedupeStoreǁ_init_database__mutmut_5(self) -> None:
        """Initialize database schema."""
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=False, exist_ok=True)

        conn = self._get_connection()
        cursor = conn.cursor()

        # Create seen_events table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_events (
                event_id TEXT PRIMARY KEY,
                first_seen_ts TEXT NOT NULL,
                last_seen_ts TEXT NOT NULL,
                seen_count INTEGER NOT NULL DEFAULT 1,
                source TEXT,
                external_id TEXT,
                metadata TEXT
            )
        """
        )

        # Index for TTL cleanup
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_seen_events_first_seen
            ON seen_events(first_seen_ts)
        """
        )

        conn.commit()

    def xǁEventDedupeStoreǁ_init_database__mutmut_6(self) -> None:
        """Initialize database schema."""
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=False)

        conn = self._get_connection()
        cursor = conn.cursor()

        # Create seen_events table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_events (
                event_id TEXT PRIMARY KEY,
                first_seen_ts TEXT NOT NULL,
                last_seen_ts TEXT NOT NULL,
                seen_count INTEGER NOT NULL DEFAULT 1,
                source TEXT,
                external_id TEXT,
                metadata TEXT
            )
        """
        )

        # Index for TTL cleanup
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_seen_events_first_seen
            ON seen_events(first_seen_ts)
        """
        )

        conn.commit()

    def xǁEventDedupeStoreǁ_init_database__mutmut_7(self) -> None:
        """Initialize database schema."""
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = None
        cursor = conn.cursor()

        # Create seen_events table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_events (
                event_id TEXT PRIMARY KEY,
                first_seen_ts TEXT NOT NULL,
                last_seen_ts TEXT NOT NULL,
                seen_count INTEGER NOT NULL DEFAULT 1,
                source TEXT,
                external_id TEXT,
                metadata TEXT
            )
        """
        )

        # Index for TTL cleanup
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_seen_events_first_seen
            ON seen_events(first_seen_ts)
        """
        )

        conn.commit()

    def xǁEventDedupeStoreǁ_init_database__mutmut_8(self) -> None:
        """Initialize database schema."""
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = self._get_connection()
        cursor = None

        # Create seen_events table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_events (
                event_id TEXT PRIMARY KEY,
                first_seen_ts TEXT NOT NULL,
                last_seen_ts TEXT NOT NULL,
                seen_count INTEGER NOT NULL DEFAULT 1,
                source TEXT,
                external_id TEXT,
                metadata TEXT
            )
        """
        )

        # Index for TTL cleanup
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_seen_events_first_seen
            ON seen_events(first_seen_ts)
        """
        )

        conn.commit()

    def xǁEventDedupeStoreǁ_init_database__mutmut_9(self) -> None:
        """Initialize database schema."""
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = self._get_connection()
        cursor = conn.cursor()

        # Create seen_events table
        cursor.execute(
            None
        )

        # Index for TTL cleanup
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_seen_events_first_seen
            ON seen_events(first_seen_ts)
        """
        )

        conn.commit()

    def xǁEventDedupeStoreǁ_init_database__mutmut_10(self) -> None:
        """Initialize database schema."""
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = self._get_connection()
        cursor = conn.cursor()

        # Create seen_events table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_events (
                event_id TEXT PRIMARY KEY,
                first_seen_ts TEXT NOT NULL,
                last_seen_ts TEXT NOT NULL,
                seen_count INTEGER NOT NULL DEFAULT 1,
                source TEXT,
                external_id TEXT,
                metadata TEXT
            )
        """
        )

        # Index for TTL cleanup
        cursor.execute(
            None
        )

        conn.commit()
    
    xǁEventDedupeStoreǁ_init_database__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁEventDedupeStoreǁ_init_database__mutmut_1': xǁEventDedupeStoreǁ_init_database__mutmut_1, 
        'xǁEventDedupeStoreǁ_init_database__mutmut_2': xǁEventDedupeStoreǁ_init_database__mutmut_2, 
        'xǁEventDedupeStoreǁ_init_database__mutmut_3': xǁEventDedupeStoreǁ_init_database__mutmut_3, 
        'xǁEventDedupeStoreǁ_init_database__mutmut_4': xǁEventDedupeStoreǁ_init_database__mutmut_4, 
        'xǁEventDedupeStoreǁ_init_database__mutmut_5': xǁEventDedupeStoreǁ_init_database__mutmut_5, 
        'xǁEventDedupeStoreǁ_init_database__mutmut_6': xǁEventDedupeStoreǁ_init_database__mutmut_6, 
        'xǁEventDedupeStoreǁ_init_database__mutmut_7': xǁEventDedupeStoreǁ_init_database__mutmut_7, 
        'xǁEventDedupeStoreǁ_init_database__mutmut_8': xǁEventDedupeStoreǁ_init_database__mutmut_8, 
        'xǁEventDedupeStoreǁ_init_database__mutmut_9': xǁEventDedupeStoreǁ_init_database__mutmut_9, 
        'xǁEventDedupeStoreǁ_init_database__mutmut_10': xǁEventDedupeStoreǁ_init_database__mutmut_10
    }
    
    def _init_database(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁEventDedupeStoreǁ_init_database__mutmut_orig"), object.__getattribute__(self, "xǁEventDedupeStoreǁ_init_database__mutmut_mutants"), args, kwargs, self)
        return result 
    
    _init_database.__signature__ = _mutmut_signature(xǁEventDedupeStoreǁ_init_database__mutmut_orig)
    xǁEventDedupeStoreǁ_init_database__mutmut_orig.__name__ = 'xǁEventDedupeStoreǁ_init_database'

    def xǁEventDedupeStoreǁ_get_connection__mutmut_orig(self) -> sqlite3.Connection:
        """Get database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def xǁEventDedupeStoreǁ_get_connection__mutmut_1(self) -> sqlite3.Connection:
        """Get database connection."""
        if self._conn is not None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def xǁEventDedupeStoreǁ_get_connection__mutmut_2(self) -> sqlite3.Connection:
        """Get database connection."""
        if self._conn is None:
            self._conn = None
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def xǁEventDedupeStoreǁ_get_connection__mutmut_3(self) -> sqlite3.Connection:
        """Get database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(None)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def xǁEventDedupeStoreǁ_get_connection__mutmut_4(self) -> sqlite3.Connection:
        """Get database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(None))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def xǁEventDedupeStoreǁ_get_connection__mutmut_5(self) -> sqlite3.Connection:
        """Get database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = None
        return self._conn
    
    xǁEventDedupeStoreǁ_get_connection__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁEventDedupeStoreǁ_get_connection__mutmut_1': xǁEventDedupeStoreǁ_get_connection__mutmut_1, 
        'xǁEventDedupeStoreǁ_get_connection__mutmut_2': xǁEventDedupeStoreǁ_get_connection__mutmut_2, 
        'xǁEventDedupeStoreǁ_get_connection__mutmut_3': xǁEventDedupeStoreǁ_get_connection__mutmut_3, 
        'xǁEventDedupeStoreǁ_get_connection__mutmut_4': xǁEventDedupeStoreǁ_get_connection__mutmut_4, 
        'xǁEventDedupeStoreǁ_get_connection__mutmut_5': xǁEventDedupeStoreǁ_get_connection__mutmut_5
    }
    
    def _get_connection(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁEventDedupeStoreǁ_get_connection__mutmut_orig"), object.__getattribute__(self, "xǁEventDedupeStoreǁ_get_connection__mutmut_mutants"), args, kwargs, self)
        return result 
    
    _get_connection.__signature__ = _mutmut_signature(xǁEventDedupeStoreǁ_get_connection__mutmut_orig)
    xǁEventDedupeStoreǁ_get_connection__mutmut_orig.__name__ = 'xǁEventDedupeStoreǁ_get_connection'

    def xǁEventDedupeStoreǁis_duplicate__mutmut_orig(self, event_id: str) -> bool:
        """Check if event has been seen before.

        Parameters
        ----------
        event_id
            Event ID to check

        Returns
        -------
        bool
            True if event was already seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT event_id FROM seen_events WHERE event_id = ?", (event_id,))

        return cursor.fetchone() is not None

    def xǁEventDedupeStoreǁis_duplicate__mutmut_1(self, event_id: str) -> bool:
        """Check if event has been seen before.

        Parameters
        ----------
        event_id
            Event ID to check

        Returns
        -------
        bool
            True if event was already seen
        """
        conn = None
        cursor = conn.cursor()

        cursor.execute("SELECT event_id FROM seen_events WHERE event_id = ?", (event_id,))

        return cursor.fetchone() is not None

    def xǁEventDedupeStoreǁis_duplicate__mutmut_2(self, event_id: str) -> bool:
        """Check if event has been seen before.

        Parameters
        ----------
        event_id
            Event ID to check

        Returns
        -------
        bool
            True if event was already seen
        """
        conn = self._get_connection()
        cursor = None

        cursor.execute("SELECT event_id FROM seen_events WHERE event_id = ?", (event_id,))

        return cursor.fetchone() is not None

    def xǁEventDedupeStoreǁis_duplicate__mutmut_3(self, event_id: str) -> bool:
        """Check if event has been seen before.

        Parameters
        ----------
        event_id
            Event ID to check

        Returns
        -------
        bool
            True if event was already seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(None, (event_id,))

        return cursor.fetchone() is not None

    def xǁEventDedupeStoreǁis_duplicate__mutmut_4(self, event_id: str) -> bool:
        """Check if event has been seen before.

        Parameters
        ----------
        event_id
            Event ID to check

        Returns
        -------
        bool
            True if event was already seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT event_id FROM seen_events WHERE event_id = ?", None)

        return cursor.fetchone() is not None

    def xǁEventDedupeStoreǁis_duplicate__mutmut_5(self, event_id: str) -> bool:
        """Check if event has been seen before.

        Parameters
        ----------
        event_id
            Event ID to check

        Returns
        -------
        bool
            True if event was already seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute((event_id,))

        return cursor.fetchone() is not None

    def xǁEventDedupeStoreǁis_duplicate__mutmut_6(self, event_id: str) -> bool:
        """Check if event has been seen before.

        Parameters
        ----------
        event_id
            Event ID to check

        Returns
        -------
        bool
            True if event was already seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT event_id FROM seen_events WHERE event_id = ?", )

        return cursor.fetchone() is not None

    def xǁEventDedupeStoreǁis_duplicate__mutmut_7(self, event_id: str) -> bool:
        """Check if event has been seen before.

        Parameters
        ----------
        event_id
            Event ID to check

        Returns
        -------
        bool
            True if event was already seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("XXSELECT event_id FROM seen_events WHERE event_id = ?XX", (event_id,))

        return cursor.fetchone() is not None

    def xǁEventDedupeStoreǁis_duplicate__mutmut_8(self, event_id: str) -> bool:
        """Check if event has been seen before.

        Parameters
        ----------
        event_id
            Event ID to check

        Returns
        -------
        bool
            True if event was already seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("select event_id from seen_events where event_id = ?", (event_id,))

        return cursor.fetchone() is not None

    def xǁEventDedupeStoreǁis_duplicate__mutmut_9(self, event_id: str) -> bool:
        """Check if event has been seen before.

        Parameters
        ----------
        event_id
            Event ID to check

        Returns
        -------
        bool
            True if event was already seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT EVENT_ID FROM SEEN_EVENTS WHERE EVENT_ID = ?", (event_id,))

        return cursor.fetchone() is not None

    def xǁEventDedupeStoreǁis_duplicate__mutmut_10(self, event_id: str) -> bool:
        """Check if event has been seen before.

        Parameters
        ----------
        event_id
            Event ID to check

        Returns
        -------
        bool
            True if event was already seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT event_id FROM seen_events WHERE event_id = ?", (event_id,))

        return cursor.fetchone() is None
    
    xǁEventDedupeStoreǁis_duplicate__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁEventDedupeStoreǁis_duplicate__mutmut_1': xǁEventDedupeStoreǁis_duplicate__mutmut_1, 
        'xǁEventDedupeStoreǁis_duplicate__mutmut_2': xǁEventDedupeStoreǁis_duplicate__mutmut_2, 
        'xǁEventDedupeStoreǁis_duplicate__mutmut_3': xǁEventDedupeStoreǁis_duplicate__mutmut_3, 
        'xǁEventDedupeStoreǁis_duplicate__mutmut_4': xǁEventDedupeStoreǁis_duplicate__mutmut_4, 
        'xǁEventDedupeStoreǁis_duplicate__mutmut_5': xǁEventDedupeStoreǁis_duplicate__mutmut_5, 
        'xǁEventDedupeStoreǁis_duplicate__mutmut_6': xǁEventDedupeStoreǁis_duplicate__mutmut_6, 
        'xǁEventDedupeStoreǁis_duplicate__mutmut_7': xǁEventDedupeStoreǁis_duplicate__mutmut_7, 
        'xǁEventDedupeStoreǁis_duplicate__mutmut_8': xǁEventDedupeStoreǁis_duplicate__mutmut_8, 
        'xǁEventDedupeStoreǁis_duplicate__mutmut_9': xǁEventDedupeStoreǁis_duplicate__mutmut_9, 
        'xǁEventDedupeStoreǁis_duplicate__mutmut_10': xǁEventDedupeStoreǁis_duplicate__mutmut_10
    }
    
    def is_duplicate(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁEventDedupeStoreǁis_duplicate__mutmut_orig"), object.__getattribute__(self, "xǁEventDedupeStoreǁis_duplicate__mutmut_mutants"), args, kwargs, self)
        return result 
    
    is_duplicate.__signature__ = _mutmut_signature(xǁEventDedupeStoreǁis_duplicate__mutmut_orig)
    xǁEventDedupeStoreǁis_duplicate__mutmut_orig.__name__ = 'xǁEventDedupeStoreǁis_duplicate'

    def xǁEventDedupeStoreǁmark_seen__mutmut_orig(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.

        If event was already seen, updates last_seen_ts and seen_count.

        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata

        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = format_utc_iso8601(get_current_utc())
        metadata_json = json.dumps(metadata) if metadata else None

        # Check if already exists
        cursor.execute("SELECT seen_count FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is not None:
            # Update existing
            cursor.execute(
                """
                UPDATE seen_events
                SET last_seen_ts = ?,
                    seen_count = seen_count + 1
                WHERE event_id = ?
            """,
                (now, event_id),
            )
            conn.commit()
            return False  # Duplicate
        # Insert new
        cursor.execute(
            """
                INSERT INTO seen_events
                (event_id, first_seen_ts, last_seen_ts, seen_count, source, external_id, metadata)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (event_id, now, now, source, external_id, metadata_json),
        )
        conn.commit()
        return True  # First time

    def xǁEventDedupeStoreǁmark_seen__mutmut_1(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.

        If event was already seen, updates last_seen_ts and seen_count.

        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata

        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = None
        cursor = conn.cursor()

        now = format_utc_iso8601(get_current_utc())
        metadata_json = json.dumps(metadata) if metadata else None

        # Check if already exists
        cursor.execute("SELECT seen_count FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is not None:
            # Update existing
            cursor.execute(
                """
                UPDATE seen_events
                SET last_seen_ts = ?,
                    seen_count = seen_count + 1
                WHERE event_id = ?
            """,
                (now, event_id),
            )
            conn.commit()
            return False  # Duplicate
        # Insert new
        cursor.execute(
            """
                INSERT INTO seen_events
                (event_id, first_seen_ts, last_seen_ts, seen_count, source, external_id, metadata)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (event_id, now, now, source, external_id, metadata_json),
        )
        conn.commit()
        return True  # First time

    def xǁEventDedupeStoreǁmark_seen__mutmut_2(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.

        If event was already seen, updates last_seen_ts and seen_count.

        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata

        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = self._get_connection()
        cursor = None

        now = format_utc_iso8601(get_current_utc())
        metadata_json = json.dumps(metadata) if metadata else None

        # Check if already exists
        cursor.execute("SELECT seen_count FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is not None:
            # Update existing
            cursor.execute(
                """
                UPDATE seen_events
                SET last_seen_ts = ?,
                    seen_count = seen_count + 1
                WHERE event_id = ?
            """,
                (now, event_id),
            )
            conn.commit()
            return False  # Duplicate
        # Insert new
        cursor.execute(
            """
                INSERT INTO seen_events
                (event_id, first_seen_ts, last_seen_ts, seen_count, source, external_id, metadata)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (event_id, now, now, source, external_id, metadata_json),
        )
        conn.commit()
        return True  # First time

    def xǁEventDedupeStoreǁmark_seen__mutmut_3(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.

        If event was already seen, updates last_seen_ts and seen_count.

        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata

        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = None
        metadata_json = json.dumps(metadata) if metadata else None

        # Check if already exists
        cursor.execute("SELECT seen_count FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is not None:
            # Update existing
            cursor.execute(
                """
                UPDATE seen_events
                SET last_seen_ts = ?,
                    seen_count = seen_count + 1
                WHERE event_id = ?
            """,
                (now, event_id),
            )
            conn.commit()
            return False  # Duplicate
        # Insert new
        cursor.execute(
            """
                INSERT INTO seen_events
                (event_id, first_seen_ts, last_seen_ts, seen_count, source, external_id, metadata)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (event_id, now, now, source, external_id, metadata_json),
        )
        conn.commit()
        return True  # First time

    def xǁEventDedupeStoreǁmark_seen__mutmut_4(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.

        If event was already seen, updates last_seen_ts and seen_count.

        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata

        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = format_utc_iso8601(None)
        metadata_json = json.dumps(metadata) if metadata else None

        # Check if already exists
        cursor.execute("SELECT seen_count FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is not None:
            # Update existing
            cursor.execute(
                """
                UPDATE seen_events
                SET last_seen_ts = ?,
                    seen_count = seen_count + 1
                WHERE event_id = ?
            """,
                (now, event_id),
            )
            conn.commit()
            return False  # Duplicate
        # Insert new
        cursor.execute(
            """
                INSERT INTO seen_events
                (event_id, first_seen_ts, last_seen_ts, seen_count, source, external_id, metadata)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (event_id, now, now, source, external_id, metadata_json),
        )
        conn.commit()
        return True  # First time

    def xǁEventDedupeStoreǁmark_seen__mutmut_5(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.

        If event was already seen, updates last_seen_ts and seen_count.

        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata

        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = format_utc_iso8601(get_current_utc())
        metadata_json = None

        # Check if already exists
        cursor.execute("SELECT seen_count FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is not None:
            # Update existing
            cursor.execute(
                """
                UPDATE seen_events
                SET last_seen_ts = ?,
                    seen_count = seen_count + 1
                WHERE event_id = ?
            """,
                (now, event_id),
            )
            conn.commit()
            return False  # Duplicate
        # Insert new
        cursor.execute(
            """
                INSERT INTO seen_events
                (event_id, first_seen_ts, last_seen_ts, seen_count, source, external_id, metadata)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (event_id, now, now, source, external_id, metadata_json),
        )
        conn.commit()
        return True  # First time

    def xǁEventDedupeStoreǁmark_seen__mutmut_6(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.

        If event was already seen, updates last_seen_ts and seen_count.

        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata

        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = format_utc_iso8601(get_current_utc())
        metadata_json = json.dumps(None) if metadata else None

        # Check if already exists
        cursor.execute("SELECT seen_count FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is not None:
            # Update existing
            cursor.execute(
                """
                UPDATE seen_events
                SET last_seen_ts = ?,
                    seen_count = seen_count + 1
                WHERE event_id = ?
            """,
                (now, event_id),
            )
            conn.commit()
            return False  # Duplicate
        # Insert new
        cursor.execute(
            """
                INSERT INTO seen_events
                (event_id, first_seen_ts, last_seen_ts, seen_count, source, external_id, metadata)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (event_id, now, now, source, external_id, metadata_json),
        )
        conn.commit()
        return True  # First time

    def xǁEventDedupeStoreǁmark_seen__mutmut_7(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.

        If event was already seen, updates last_seen_ts and seen_count.

        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata

        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = format_utc_iso8601(get_current_utc())
        metadata_json = json.dumps(metadata) if metadata else None

        # Check if already exists
        cursor.execute(None, (event_id,))
        row = cursor.fetchone()

        if row is not None:
            # Update existing
            cursor.execute(
                """
                UPDATE seen_events
                SET last_seen_ts = ?,
                    seen_count = seen_count + 1
                WHERE event_id = ?
            """,
                (now, event_id),
            )
            conn.commit()
            return False  # Duplicate
        # Insert new
        cursor.execute(
            """
                INSERT INTO seen_events
                (event_id, first_seen_ts, last_seen_ts, seen_count, source, external_id, metadata)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (event_id, now, now, source, external_id, metadata_json),
        )
        conn.commit()
        return True  # First time

    def xǁEventDedupeStoreǁmark_seen__mutmut_8(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.

        If event was already seen, updates last_seen_ts and seen_count.

        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata

        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = format_utc_iso8601(get_current_utc())
        metadata_json = json.dumps(metadata) if metadata else None

        # Check if already exists
        cursor.execute("SELECT seen_count FROM seen_events WHERE event_id = ?", None)
        row = cursor.fetchone()

        if row is not None:
            # Update existing
            cursor.execute(
                """
                UPDATE seen_events
                SET last_seen_ts = ?,
                    seen_count = seen_count + 1
                WHERE event_id = ?
            """,
                (now, event_id),
            )
            conn.commit()
            return False  # Duplicate
        # Insert new
        cursor.execute(
            """
                INSERT INTO seen_events
                (event_id, first_seen_ts, last_seen_ts, seen_count, source, external_id, metadata)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (event_id, now, now, source, external_id, metadata_json),
        )
        conn.commit()
        return True  # First time

    def xǁEventDedupeStoreǁmark_seen__mutmut_9(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.

        If event was already seen, updates last_seen_ts and seen_count.

        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata

        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = format_utc_iso8601(get_current_utc())
        metadata_json = json.dumps(metadata) if metadata else None

        # Check if already exists
        cursor.execute((event_id,))
        row = cursor.fetchone()

        if row is not None:
            # Update existing
            cursor.execute(
                """
                UPDATE seen_events
                SET last_seen_ts = ?,
                    seen_count = seen_count + 1
                WHERE event_id = ?
            """,
                (now, event_id),
            )
            conn.commit()
            return False  # Duplicate
        # Insert new
        cursor.execute(
            """
                INSERT INTO seen_events
                (event_id, first_seen_ts, last_seen_ts, seen_count, source, external_id, metadata)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (event_id, now, now, source, external_id, metadata_json),
        )
        conn.commit()
        return True  # First time

    def xǁEventDedupeStoreǁmark_seen__mutmut_10(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.

        If event was already seen, updates last_seen_ts and seen_count.

        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata

        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = format_utc_iso8601(get_current_utc())
        metadata_json = json.dumps(metadata) if metadata else None

        # Check if already exists
        cursor.execute("SELECT seen_count FROM seen_events WHERE event_id = ?", )
        row = cursor.fetchone()

        if row is not None:
            # Update existing
            cursor.execute(
                """
                UPDATE seen_events
                SET last_seen_ts = ?,
                    seen_count = seen_count + 1
                WHERE event_id = ?
            """,
                (now, event_id),
            )
            conn.commit()
            return False  # Duplicate
        # Insert new
        cursor.execute(
            """
                INSERT INTO seen_events
                (event_id, first_seen_ts, last_seen_ts, seen_count, source, external_id, metadata)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (event_id, now, now, source, external_id, metadata_json),
        )
        conn.commit()
        return True  # First time

    def xǁEventDedupeStoreǁmark_seen__mutmut_11(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.

        If event was already seen, updates last_seen_ts and seen_count.

        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata

        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = format_utc_iso8601(get_current_utc())
        metadata_json = json.dumps(metadata) if metadata else None

        # Check if already exists
        cursor.execute("XXSELECT seen_count FROM seen_events WHERE event_id = ?XX", (event_id,))
        row = cursor.fetchone()

        if row is not None:
            # Update existing
            cursor.execute(
                """
                UPDATE seen_events
                SET last_seen_ts = ?,
                    seen_count = seen_count + 1
                WHERE event_id = ?
            """,
                (now, event_id),
            )
            conn.commit()
            return False  # Duplicate
        # Insert new
        cursor.execute(
            """
                INSERT INTO seen_events
                (event_id, first_seen_ts, last_seen_ts, seen_count, source, external_id, metadata)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (event_id, now, now, source, external_id, metadata_json),
        )
        conn.commit()
        return True  # First time

    def xǁEventDedupeStoreǁmark_seen__mutmut_12(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.

        If event was already seen, updates last_seen_ts and seen_count.

        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata

        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = format_utc_iso8601(get_current_utc())
        metadata_json = json.dumps(metadata) if metadata else None

        # Check if already exists
        cursor.execute("select seen_count from seen_events where event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is not None:
            # Update existing
            cursor.execute(
                """
                UPDATE seen_events
                SET last_seen_ts = ?,
                    seen_count = seen_count + 1
                WHERE event_id = ?
            """,
                (now, event_id),
            )
            conn.commit()
            return False  # Duplicate
        # Insert new
        cursor.execute(
            """
                INSERT INTO seen_events
                (event_id, first_seen_ts, last_seen_ts, seen_count, source, external_id, metadata)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (event_id, now, now, source, external_id, metadata_json),
        )
        conn.commit()
        return True  # First time

    def xǁEventDedupeStoreǁmark_seen__mutmut_13(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.

        If event was already seen, updates last_seen_ts and seen_count.

        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata

        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = format_utc_iso8601(get_current_utc())
        metadata_json = json.dumps(metadata) if metadata else None

        # Check if already exists
        cursor.execute("SELECT SEEN_COUNT FROM SEEN_EVENTS WHERE EVENT_ID = ?", (event_id,))
        row = cursor.fetchone()

        if row is not None:
            # Update existing
            cursor.execute(
                """
                UPDATE seen_events
                SET last_seen_ts = ?,
                    seen_count = seen_count + 1
                WHERE event_id = ?
            """,
                (now, event_id),
            )
            conn.commit()
            return False  # Duplicate
        # Insert new
        cursor.execute(
            """
                INSERT INTO seen_events
                (event_id, first_seen_ts, last_seen_ts, seen_count, source, external_id, metadata)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (event_id, now, now, source, external_id, metadata_json),
        )
        conn.commit()
        return True  # First time

    def xǁEventDedupeStoreǁmark_seen__mutmut_14(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.

        If event was already seen, updates last_seen_ts and seen_count.

        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata

        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = format_utc_iso8601(get_current_utc())
        metadata_json = json.dumps(metadata) if metadata else None

        # Check if already exists
        cursor.execute("SELECT seen_count FROM seen_events WHERE event_id = ?", (event_id,))
        row = None

        if row is not None:
            # Update existing
            cursor.execute(
                """
                UPDATE seen_events
                SET last_seen_ts = ?,
                    seen_count = seen_count + 1
                WHERE event_id = ?
            """,
                (now, event_id),
            )
            conn.commit()
            return False  # Duplicate
        # Insert new
        cursor.execute(
            """
                INSERT INTO seen_events
                (event_id, first_seen_ts, last_seen_ts, seen_count, source, external_id, metadata)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (event_id, now, now, source, external_id, metadata_json),
        )
        conn.commit()
        return True  # First time

    def xǁEventDedupeStoreǁmark_seen__mutmut_15(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.

        If event was already seen, updates last_seen_ts and seen_count.

        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata

        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = format_utc_iso8601(get_current_utc())
        metadata_json = json.dumps(metadata) if metadata else None

        # Check if already exists
        cursor.execute("SELECT seen_count FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            # Update existing
            cursor.execute(
                """
                UPDATE seen_events
                SET last_seen_ts = ?,
                    seen_count = seen_count + 1
                WHERE event_id = ?
            """,
                (now, event_id),
            )
            conn.commit()
            return False  # Duplicate
        # Insert new
        cursor.execute(
            """
                INSERT INTO seen_events
                (event_id, first_seen_ts, last_seen_ts, seen_count, source, external_id, metadata)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (event_id, now, now, source, external_id, metadata_json),
        )
        conn.commit()
        return True  # First time

    def xǁEventDedupeStoreǁmark_seen__mutmut_16(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.

        If event was already seen, updates last_seen_ts and seen_count.

        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata

        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = format_utc_iso8601(get_current_utc())
        metadata_json = json.dumps(metadata) if metadata else None

        # Check if already exists
        cursor.execute("SELECT seen_count FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is not None:
            # Update existing
            cursor.execute(
                None,
                (now, event_id),
            )
            conn.commit()
            return False  # Duplicate
        # Insert new
        cursor.execute(
            """
                INSERT INTO seen_events
                (event_id, first_seen_ts, last_seen_ts, seen_count, source, external_id, metadata)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (event_id, now, now, source, external_id, metadata_json),
        )
        conn.commit()
        return True  # First time

    def xǁEventDedupeStoreǁmark_seen__mutmut_17(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.

        If event was already seen, updates last_seen_ts and seen_count.

        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata

        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = format_utc_iso8601(get_current_utc())
        metadata_json = json.dumps(metadata) if metadata else None

        # Check if already exists
        cursor.execute("SELECT seen_count FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is not None:
            # Update existing
            cursor.execute(
                """
                UPDATE seen_events
                SET last_seen_ts = ?,
                    seen_count = seen_count + 1
                WHERE event_id = ?
            """,
                None,
            )
            conn.commit()
            return False  # Duplicate
        # Insert new
        cursor.execute(
            """
                INSERT INTO seen_events
                (event_id, first_seen_ts, last_seen_ts, seen_count, source, external_id, metadata)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (event_id, now, now, source, external_id, metadata_json),
        )
        conn.commit()
        return True  # First time

    def xǁEventDedupeStoreǁmark_seen__mutmut_18(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.

        If event was already seen, updates last_seen_ts and seen_count.

        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata

        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = format_utc_iso8601(get_current_utc())
        metadata_json = json.dumps(metadata) if metadata else None

        # Check if already exists
        cursor.execute("SELECT seen_count FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is not None:
            # Update existing
            cursor.execute(
                (now, event_id),
            )
            conn.commit()
            return False  # Duplicate
        # Insert new
        cursor.execute(
            """
                INSERT INTO seen_events
                (event_id, first_seen_ts, last_seen_ts, seen_count, source, external_id, metadata)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (event_id, now, now, source, external_id, metadata_json),
        )
        conn.commit()
        return True  # First time

    def xǁEventDedupeStoreǁmark_seen__mutmut_19(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.

        If event was already seen, updates last_seen_ts and seen_count.

        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata

        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = format_utc_iso8601(get_current_utc())
        metadata_json = json.dumps(metadata) if metadata else None

        # Check if already exists
        cursor.execute("SELECT seen_count FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is not None:
            # Update existing
            cursor.execute(
                """
                UPDATE seen_events
                SET last_seen_ts = ?,
                    seen_count = seen_count + 1
                WHERE event_id = ?
            """,
                )
            conn.commit()
            return False  # Duplicate
        # Insert new
        cursor.execute(
            """
                INSERT INTO seen_events
                (event_id, first_seen_ts, last_seen_ts, seen_count, source, external_id, metadata)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (event_id, now, now, source, external_id, metadata_json),
        )
        conn.commit()
        return True  # First time

    def xǁEventDedupeStoreǁmark_seen__mutmut_20(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.

        If event was already seen, updates last_seen_ts and seen_count.

        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata

        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = format_utc_iso8601(get_current_utc())
        metadata_json = json.dumps(metadata) if metadata else None

        # Check if already exists
        cursor.execute("SELECT seen_count FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is not None:
            # Update existing
            cursor.execute(
                """
                UPDATE seen_events
                SET last_seen_ts = ?,
                    seen_count = seen_count + 1
                WHERE event_id = ?
            """,
                (now, event_id),
            )
            conn.commit()
            return True  # Duplicate
        # Insert new
        cursor.execute(
            """
                INSERT INTO seen_events
                (event_id, first_seen_ts, last_seen_ts, seen_count, source, external_id, metadata)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (event_id, now, now, source, external_id, metadata_json),
        )
        conn.commit()
        return True  # First time

    def xǁEventDedupeStoreǁmark_seen__mutmut_21(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.

        If event was already seen, updates last_seen_ts and seen_count.

        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata

        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = format_utc_iso8601(get_current_utc())
        metadata_json = json.dumps(metadata) if metadata else None

        # Check if already exists
        cursor.execute("SELECT seen_count FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is not None:
            # Update existing
            cursor.execute(
                """
                UPDATE seen_events
                SET last_seen_ts = ?,
                    seen_count = seen_count + 1
                WHERE event_id = ?
            """,
                (now, event_id),
            )
            conn.commit()
            return False  # Duplicate
        # Insert new
        cursor.execute(
            None,
            (event_id, now, now, source, external_id, metadata_json),
        )
        conn.commit()
        return True  # First time

    def xǁEventDedupeStoreǁmark_seen__mutmut_22(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.

        If event was already seen, updates last_seen_ts and seen_count.

        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata

        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = format_utc_iso8601(get_current_utc())
        metadata_json = json.dumps(metadata) if metadata else None

        # Check if already exists
        cursor.execute("SELECT seen_count FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is not None:
            # Update existing
            cursor.execute(
                """
                UPDATE seen_events
                SET last_seen_ts = ?,
                    seen_count = seen_count + 1
                WHERE event_id = ?
            """,
                (now, event_id),
            )
            conn.commit()
            return False  # Duplicate
        # Insert new
        cursor.execute(
            """
                INSERT INTO seen_events
                (event_id, first_seen_ts, last_seen_ts, seen_count, source, external_id, metadata)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            None,
        )
        conn.commit()
        return True  # First time

    def xǁEventDedupeStoreǁmark_seen__mutmut_23(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.

        If event was already seen, updates last_seen_ts and seen_count.

        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata

        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = format_utc_iso8601(get_current_utc())
        metadata_json = json.dumps(metadata) if metadata else None

        # Check if already exists
        cursor.execute("SELECT seen_count FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is not None:
            # Update existing
            cursor.execute(
                """
                UPDATE seen_events
                SET last_seen_ts = ?,
                    seen_count = seen_count + 1
                WHERE event_id = ?
            """,
                (now, event_id),
            )
            conn.commit()
            return False  # Duplicate
        # Insert new
        cursor.execute(
            (event_id, now, now, source, external_id, metadata_json),
        )
        conn.commit()
        return True  # First time

    def xǁEventDedupeStoreǁmark_seen__mutmut_24(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.

        If event was already seen, updates last_seen_ts and seen_count.

        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata

        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = format_utc_iso8601(get_current_utc())
        metadata_json = json.dumps(metadata) if metadata else None

        # Check if already exists
        cursor.execute("SELECT seen_count FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is not None:
            # Update existing
            cursor.execute(
                """
                UPDATE seen_events
                SET last_seen_ts = ?,
                    seen_count = seen_count + 1
                WHERE event_id = ?
            """,
                (now, event_id),
            )
            conn.commit()
            return False  # Duplicate
        # Insert new
        cursor.execute(
            """
                INSERT INTO seen_events
                (event_id, first_seen_ts, last_seen_ts, seen_count, source, external_id, metadata)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            )
        conn.commit()
        return True  # First time

    def xǁEventDedupeStoreǁmark_seen__mutmut_25(
        self,
        event_id: str,
        *,
        source: str | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark event as seen.

        If event was already seen, updates last_seen_ts and seen_count.

        Parameters
        ----------
        event_id
            Event ID
        source
            Event source
        external_id
            External ID from source
        metadata
            Optional metadata

        Returns
        -------
        bool
            True if this is first time seeing event (not duplicate)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = format_utc_iso8601(get_current_utc())
        metadata_json = json.dumps(metadata) if metadata else None

        # Check if already exists
        cursor.execute("SELECT seen_count FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is not None:
            # Update existing
            cursor.execute(
                """
                UPDATE seen_events
                SET last_seen_ts = ?,
                    seen_count = seen_count + 1
                WHERE event_id = ?
            """,
                (now, event_id),
            )
            conn.commit()
            return False  # Duplicate
        # Insert new
        cursor.execute(
            """
                INSERT INTO seen_events
                (event_id, first_seen_ts, last_seen_ts, seen_count, source, external_id, metadata)
                VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (event_id, now, now, source, external_id, metadata_json),
        )
        conn.commit()
        return False  # First time
    
    xǁEventDedupeStoreǁmark_seen__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁEventDedupeStoreǁmark_seen__mutmut_1': xǁEventDedupeStoreǁmark_seen__mutmut_1, 
        'xǁEventDedupeStoreǁmark_seen__mutmut_2': xǁEventDedupeStoreǁmark_seen__mutmut_2, 
        'xǁEventDedupeStoreǁmark_seen__mutmut_3': xǁEventDedupeStoreǁmark_seen__mutmut_3, 
        'xǁEventDedupeStoreǁmark_seen__mutmut_4': xǁEventDedupeStoreǁmark_seen__mutmut_4, 
        'xǁEventDedupeStoreǁmark_seen__mutmut_5': xǁEventDedupeStoreǁmark_seen__mutmut_5, 
        'xǁEventDedupeStoreǁmark_seen__mutmut_6': xǁEventDedupeStoreǁmark_seen__mutmut_6, 
        'xǁEventDedupeStoreǁmark_seen__mutmut_7': xǁEventDedupeStoreǁmark_seen__mutmut_7, 
        'xǁEventDedupeStoreǁmark_seen__mutmut_8': xǁEventDedupeStoreǁmark_seen__mutmut_8, 
        'xǁEventDedupeStoreǁmark_seen__mutmut_9': xǁEventDedupeStoreǁmark_seen__mutmut_9, 
        'xǁEventDedupeStoreǁmark_seen__mutmut_10': xǁEventDedupeStoreǁmark_seen__mutmut_10, 
        'xǁEventDedupeStoreǁmark_seen__mutmut_11': xǁEventDedupeStoreǁmark_seen__mutmut_11, 
        'xǁEventDedupeStoreǁmark_seen__mutmut_12': xǁEventDedupeStoreǁmark_seen__mutmut_12, 
        'xǁEventDedupeStoreǁmark_seen__mutmut_13': xǁEventDedupeStoreǁmark_seen__mutmut_13, 
        'xǁEventDedupeStoreǁmark_seen__mutmut_14': xǁEventDedupeStoreǁmark_seen__mutmut_14, 
        'xǁEventDedupeStoreǁmark_seen__mutmut_15': xǁEventDedupeStoreǁmark_seen__mutmut_15, 
        'xǁEventDedupeStoreǁmark_seen__mutmut_16': xǁEventDedupeStoreǁmark_seen__mutmut_16, 
        'xǁEventDedupeStoreǁmark_seen__mutmut_17': xǁEventDedupeStoreǁmark_seen__mutmut_17, 
        'xǁEventDedupeStoreǁmark_seen__mutmut_18': xǁEventDedupeStoreǁmark_seen__mutmut_18, 
        'xǁEventDedupeStoreǁmark_seen__mutmut_19': xǁEventDedupeStoreǁmark_seen__mutmut_19, 
        'xǁEventDedupeStoreǁmark_seen__mutmut_20': xǁEventDedupeStoreǁmark_seen__mutmut_20, 
        'xǁEventDedupeStoreǁmark_seen__mutmut_21': xǁEventDedupeStoreǁmark_seen__mutmut_21, 
        'xǁEventDedupeStoreǁmark_seen__mutmut_22': xǁEventDedupeStoreǁmark_seen__mutmut_22, 
        'xǁEventDedupeStoreǁmark_seen__mutmut_23': xǁEventDedupeStoreǁmark_seen__mutmut_23, 
        'xǁEventDedupeStoreǁmark_seen__mutmut_24': xǁEventDedupeStoreǁmark_seen__mutmut_24, 
        'xǁEventDedupeStoreǁmark_seen__mutmut_25': xǁEventDedupeStoreǁmark_seen__mutmut_25
    }
    
    def mark_seen(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁEventDedupeStoreǁmark_seen__mutmut_orig"), object.__getattribute__(self, "xǁEventDedupeStoreǁmark_seen__mutmut_mutants"), args, kwargs, self)
        return result 
    
    mark_seen.__signature__ = _mutmut_signature(xǁEventDedupeStoreǁmark_seen__mutmut_orig)
    xǁEventDedupeStoreǁmark_seen__mutmut_orig.__name__ = 'xǁEventDedupeStoreǁmark_seen'

    def xǁEventDedupeStoreǁget_event_info__mutmut_orig(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_1(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = None
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_2(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = None

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_3(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(None, (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_4(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", None)
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_5(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute((event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_6(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", )
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_7(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("XXSELECT * FROM seen_events WHERE event_id = ?XX", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_8(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("select * from seen_events where event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_9(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM SEEN_EVENTS WHERE EVENT_ID = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_10(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = None

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_11(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is not None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_12(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "XXevent_idXX": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_13(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "EVENT_ID": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_14(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["XXevent_idXX"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_15(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["EVENT_ID"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_16(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "XXfirst_seen_tsXX": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_17(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "FIRST_SEEN_TS": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_18(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["XXfirst_seen_tsXX"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_19(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["FIRST_SEEN_TS"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_20(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "XXlast_seen_tsXX": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_21(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "LAST_SEEN_TS": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_22(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["XXlast_seen_tsXX"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_23(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["LAST_SEEN_TS"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_24(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "XXseen_countXX": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_25(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "SEEN_COUNT": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_26(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["XXseen_countXX"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_27(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["SEEN_COUNT"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_28(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "XXsourceXX": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_29(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "SOURCE": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_30(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["XXsourceXX"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_31(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["SOURCE"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_32(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "XXexternal_idXX": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_33(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "EXTERNAL_ID": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_34(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["XXexternal_idXX"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_35(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["EXTERNAL_ID"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_36(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "XXmetadataXX": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_37(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "METADATA": json.loads(row["metadata"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_38(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(None) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_39(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["XXmetadataXX"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_40(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["METADATA"]) if row["metadata"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_41(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["XXmetadataXX"] else None,
        }

    def xǁEventDedupeStoreǁget_event_info__mutmut_42(self, event_id: str) -> dict[str, Any] | None:
        """Get information about a seen event.

        Parameters
        ----------
        event_id
            Event ID

        Returns
        -------
        dict[str, Any] | None
            Event info or None if not seen
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM seen_events WHERE event_id = ?", (event_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        return {
            "event_id": row["event_id"],
            "first_seen_ts": row["first_seen_ts"],
            "last_seen_ts": row["last_seen_ts"],
            "seen_count": row["seen_count"],
            "source": row["source"],
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]) if row["METADATA"] else None,
        }
    
    xǁEventDedupeStoreǁget_event_info__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁEventDedupeStoreǁget_event_info__mutmut_1': xǁEventDedupeStoreǁget_event_info__mutmut_1, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_2': xǁEventDedupeStoreǁget_event_info__mutmut_2, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_3': xǁEventDedupeStoreǁget_event_info__mutmut_3, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_4': xǁEventDedupeStoreǁget_event_info__mutmut_4, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_5': xǁEventDedupeStoreǁget_event_info__mutmut_5, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_6': xǁEventDedupeStoreǁget_event_info__mutmut_6, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_7': xǁEventDedupeStoreǁget_event_info__mutmut_7, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_8': xǁEventDedupeStoreǁget_event_info__mutmut_8, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_9': xǁEventDedupeStoreǁget_event_info__mutmut_9, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_10': xǁEventDedupeStoreǁget_event_info__mutmut_10, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_11': xǁEventDedupeStoreǁget_event_info__mutmut_11, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_12': xǁEventDedupeStoreǁget_event_info__mutmut_12, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_13': xǁEventDedupeStoreǁget_event_info__mutmut_13, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_14': xǁEventDedupeStoreǁget_event_info__mutmut_14, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_15': xǁEventDedupeStoreǁget_event_info__mutmut_15, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_16': xǁEventDedupeStoreǁget_event_info__mutmut_16, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_17': xǁEventDedupeStoreǁget_event_info__mutmut_17, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_18': xǁEventDedupeStoreǁget_event_info__mutmut_18, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_19': xǁEventDedupeStoreǁget_event_info__mutmut_19, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_20': xǁEventDedupeStoreǁget_event_info__mutmut_20, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_21': xǁEventDedupeStoreǁget_event_info__mutmut_21, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_22': xǁEventDedupeStoreǁget_event_info__mutmut_22, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_23': xǁEventDedupeStoreǁget_event_info__mutmut_23, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_24': xǁEventDedupeStoreǁget_event_info__mutmut_24, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_25': xǁEventDedupeStoreǁget_event_info__mutmut_25, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_26': xǁEventDedupeStoreǁget_event_info__mutmut_26, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_27': xǁEventDedupeStoreǁget_event_info__mutmut_27, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_28': xǁEventDedupeStoreǁget_event_info__mutmut_28, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_29': xǁEventDedupeStoreǁget_event_info__mutmut_29, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_30': xǁEventDedupeStoreǁget_event_info__mutmut_30, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_31': xǁEventDedupeStoreǁget_event_info__mutmut_31, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_32': xǁEventDedupeStoreǁget_event_info__mutmut_32, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_33': xǁEventDedupeStoreǁget_event_info__mutmut_33, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_34': xǁEventDedupeStoreǁget_event_info__mutmut_34, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_35': xǁEventDedupeStoreǁget_event_info__mutmut_35, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_36': xǁEventDedupeStoreǁget_event_info__mutmut_36, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_37': xǁEventDedupeStoreǁget_event_info__mutmut_37, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_38': xǁEventDedupeStoreǁget_event_info__mutmut_38, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_39': xǁEventDedupeStoreǁget_event_info__mutmut_39, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_40': xǁEventDedupeStoreǁget_event_info__mutmut_40, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_41': xǁEventDedupeStoreǁget_event_info__mutmut_41, 
        'xǁEventDedupeStoreǁget_event_info__mutmut_42': xǁEventDedupeStoreǁget_event_info__mutmut_42
    }
    
    def get_event_info(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁEventDedupeStoreǁget_event_info__mutmut_orig"), object.__getattribute__(self, "xǁEventDedupeStoreǁget_event_info__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_event_info.__signature__ = _mutmut_signature(xǁEventDedupeStoreǁget_event_info__mutmut_orig)
    xǁEventDedupeStoreǁget_event_info__mutmut_orig.__name__ = 'xǁEventDedupeStoreǁget_event_info'

    def xǁEventDedupeStoreǁcleanup_old_events__mutmut_orig(self, ttl_days: int = 30) -> int:
        """Clean up events older than TTL (Phase 2, Point 7).

        Parameters
        ----------
        ttl_days
            Time-to-live in days

        Returns
        -------
        int
            Number of events deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Calculate cutoff time
        now = get_current_utc()
        cutoff = now - timedelta(days=ttl_days)
        cutoff_str = format_utc_iso8601(cutoff)

        # Delete old events
        cursor.execute("DELETE FROM seen_events WHERE first_seen_ts < ?", (cutoff_str,))

        deleted_count = cursor.rowcount
        conn.commit()

        return deleted_count

    def xǁEventDedupeStoreǁcleanup_old_events__mutmut_1(self, ttl_days: int = 31) -> int:
        """Clean up events older than TTL (Phase 2, Point 7).

        Parameters
        ----------
        ttl_days
            Time-to-live in days

        Returns
        -------
        int
            Number of events deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Calculate cutoff time
        now = get_current_utc()
        cutoff = now - timedelta(days=ttl_days)
        cutoff_str = format_utc_iso8601(cutoff)

        # Delete old events
        cursor.execute("DELETE FROM seen_events WHERE first_seen_ts < ?", (cutoff_str,))

        deleted_count = cursor.rowcount
        conn.commit()

        return deleted_count

    def xǁEventDedupeStoreǁcleanup_old_events__mutmut_2(self, ttl_days: int = 30) -> int:
        """Clean up events older than TTL (Phase 2, Point 7).

        Parameters
        ----------
        ttl_days
            Time-to-live in days

        Returns
        -------
        int
            Number of events deleted
        """
        conn = None
        cursor = conn.cursor()

        # Calculate cutoff time
        now = get_current_utc()
        cutoff = now - timedelta(days=ttl_days)
        cutoff_str = format_utc_iso8601(cutoff)

        # Delete old events
        cursor.execute("DELETE FROM seen_events WHERE first_seen_ts < ?", (cutoff_str,))

        deleted_count = cursor.rowcount
        conn.commit()

        return deleted_count

    def xǁEventDedupeStoreǁcleanup_old_events__mutmut_3(self, ttl_days: int = 30) -> int:
        """Clean up events older than TTL (Phase 2, Point 7).

        Parameters
        ----------
        ttl_days
            Time-to-live in days

        Returns
        -------
        int
            Number of events deleted
        """
        conn = self._get_connection()
        cursor = None

        # Calculate cutoff time
        now = get_current_utc()
        cutoff = now - timedelta(days=ttl_days)
        cutoff_str = format_utc_iso8601(cutoff)

        # Delete old events
        cursor.execute("DELETE FROM seen_events WHERE first_seen_ts < ?", (cutoff_str,))

        deleted_count = cursor.rowcount
        conn.commit()

        return deleted_count

    def xǁEventDedupeStoreǁcleanup_old_events__mutmut_4(self, ttl_days: int = 30) -> int:
        """Clean up events older than TTL (Phase 2, Point 7).

        Parameters
        ----------
        ttl_days
            Time-to-live in days

        Returns
        -------
        int
            Number of events deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Calculate cutoff time
        now = None
        cutoff = now - timedelta(days=ttl_days)
        cutoff_str = format_utc_iso8601(cutoff)

        # Delete old events
        cursor.execute("DELETE FROM seen_events WHERE first_seen_ts < ?", (cutoff_str,))

        deleted_count = cursor.rowcount
        conn.commit()

        return deleted_count

    def xǁEventDedupeStoreǁcleanup_old_events__mutmut_5(self, ttl_days: int = 30) -> int:
        """Clean up events older than TTL (Phase 2, Point 7).

        Parameters
        ----------
        ttl_days
            Time-to-live in days

        Returns
        -------
        int
            Number of events deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Calculate cutoff time
        now = get_current_utc()
        cutoff = None
        cutoff_str = format_utc_iso8601(cutoff)

        # Delete old events
        cursor.execute("DELETE FROM seen_events WHERE first_seen_ts < ?", (cutoff_str,))

        deleted_count = cursor.rowcount
        conn.commit()

        return deleted_count

    def xǁEventDedupeStoreǁcleanup_old_events__mutmut_6(self, ttl_days: int = 30) -> int:
        """Clean up events older than TTL (Phase 2, Point 7).

        Parameters
        ----------
        ttl_days
            Time-to-live in days

        Returns
        -------
        int
            Number of events deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Calculate cutoff time
        now = get_current_utc()
        cutoff = now + timedelta(days=ttl_days)
        cutoff_str = format_utc_iso8601(cutoff)

        # Delete old events
        cursor.execute("DELETE FROM seen_events WHERE first_seen_ts < ?", (cutoff_str,))

        deleted_count = cursor.rowcount
        conn.commit()

        return deleted_count

    def xǁEventDedupeStoreǁcleanup_old_events__mutmut_7(self, ttl_days: int = 30) -> int:
        """Clean up events older than TTL (Phase 2, Point 7).

        Parameters
        ----------
        ttl_days
            Time-to-live in days

        Returns
        -------
        int
            Number of events deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Calculate cutoff time
        now = get_current_utc()
        cutoff = now - timedelta(days=None)
        cutoff_str = format_utc_iso8601(cutoff)

        # Delete old events
        cursor.execute("DELETE FROM seen_events WHERE first_seen_ts < ?", (cutoff_str,))

        deleted_count = cursor.rowcount
        conn.commit()

        return deleted_count

    def xǁEventDedupeStoreǁcleanup_old_events__mutmut_8(self, ttl_days: int = 30) -> int:
        """Clean up events older than TTL (Phase 2, Point 7).

        Parameters
        ----------
        ttl_days
            Time-to-live in days

        Returns
        -------
        int
            Number of events deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Calculate cutoff time
        now = get_current_utc()
        cutoff = now - timedelta(days=ttl_days)
        cutoff_str = None

        # Delete old events
        cursor.execute("DELETE FROM seen_events WHERE first_seen_ts < ?", (cutoff_str,))

        deleted_count = cursor.rowcount
        conn.commit()

        return deleted_count

    def xǁEventDedupeStoreǁcleanup_old_events__mutmut_9(self, ttl_days: int = 30) -> int:
        """Clean up events older than TTL (Phase 2, Point 7).

        Parameters
        ----------
        ttl_days
            Time-to-live in days

        Returns
        -------
        int
            Number of events deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Calculate cutoff time
        now = get_current_utc()
        cutoff = now - timedelta(days=ttl_days)
        cutoff_str = format_utc_iso8601(None)

        # Delete old events
        cursor.execute("DELETE FROM seen_events WHERE first_seen_ts < ?", (cutoff_str,))

        deleted_count = cursor.rowcount
        conn.commit()

        return deleted_count

    def xǁEventDedupeStoreǁcleanup_old_events__mutmut_10(self, ttl_days: int = 30) -> int:
        """Clean up events older than TTL (Phase 2, Point 7).

        Parameters
        ----------
        ttl_days
            Time-to-live in days

        Returns
        -------
        int
            Number of events deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Calculate cutoff time
        now = get_current_utc()
        cutoff = now - timedelta(days=ttl_days)
        cutoff_str = format_utc_iso8601(cutoff)

        # Delete old events
        cursor.execute(None, (cutoff_str,))

        deleted_count = cursor.rowcount
        conn.commit()

        return deleted_count

    def xǁEventDedupeStoreǁcleanup_old_events__mutmut_11(self, ttl_days: int = 30) -> int:
        """Clean up events older than TTL (Phase 2, Point 7).

        Parameters
        ----------
        ttl_days
            Time-to-live in days

        Returns
        -------
        int
            Number of events deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Calculate cutoff time
        now = get_current_utc()
        cutoff = now - timedelta(days=ttl_days)
        cutoff_str = format_utc_iso8601(cutoff)

        # Delete old events
        cursor.execute("DELETE FROM seen_events WHERE first_seen_ts < ?", None)

        deleted_count = cursor.rowcount
        conn.commit()

        return deleted_count

    def xǁEventDedupeStoreǁcleanup_old_events__mutmut_12(self, ttl_days: int = 30) -> int:
        """Clean up events older than TTL (Phase 2, Point 7).

        Parameters
        ----------
        ttl_days
            Time-to-live in days

        Returns
        -------
        int
            Number of events deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Calculate cutoff time
        now = get_current_utc()
        cutoff = now - timedelta(days=ttl_days)
        cutoff_str = format_utc_iso8601(cutoff)

        # Delete old events
        cursor.execute((cutoff_str,))

        deleted_count = cursor.rowcount
        conn.commit()

        return deleted_count

    def xǁEventDedupeStoreǁcleanup_old_events__mutmut_13(self, ttl_days: int = 30) -> int:
        """Clean up events older than TTL (Phase 2, Point 7).

        Parameters
        ----------
        ttl_days
            Time-to-live in days

        Returns
        -------
        int
            Number of events deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Calculate cutoff time
        now = get_current_utc()
        cutoff = now - timedelta(days=ttl_days)
        cutoff_str = format_utc_iso8601(cutoff)

        # Delete old events
        cursor.execute("DELETE FROM seen_events WHERE first_seen_ts < ?", )

        deleted_count = cursor.rowcount
        conn.commit()

        return deleted_count

    def xǁEventDedupeStoreǁcleanup_old_events__mutmut_14(self, ttl_days: int = 30) -> int:
        """Clean up events older than TTL (Phase 2, Point 7).

        Parameters
        ----------
        ttl_days
            Time-to-live in days

        Returns
        -------
        int
            Number of events deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Calculate cutoff time
        now = get_current_utc()
        cutoff = now - timedelta(days=ttl_days)
        cutoff_str = format_utc_iso8601(cutoff)

        # Delete old events
        cursor.execute("XXDELETE FROM seen_events WHERE first_seen_ts < ?XX", (cutoff_str,))

        deleted_count = cursor.rowcount
        conn.commit()

        return deleted_count

    def xǁEventDedupeStoreǁcleanup_old_events__mutmut_15(self, ttl_days: int = 30) -> int:
        """Clean up events older than TTL (Phase 2, Point 7).

        Parameters
        ----------
        ttl_days
            Time-to-live in days

        Returns
        -------
        int
            Number of events deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Calculate cutoff time
        now = get_current_utc()
        cutoff = now - timedelta(days=ttl_days)
        cutoff_str = format_utc_iso8601(cutoff)

        # Delete old events
        cursor.execute("delete from seen_events where first_seen_ts < ?", (cutoff_str,))

        deleted_count = cursor.rowcount
        conn.commit()

        return deleted_count

    def xǁEventDedupeStoreǁcleanup_old_events__mutmut_16(self, ttl_days: int = 30) -> int:
        """Clean up events older than TTL (Phase 2, Point 7).

        Parameters
        ----------
        ttl_days
            Time-to-live in days

        Returns
        -------
        int
            Number of events deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Calculate cutoff time
        now = get_current_utc()
        cutoff = now - timedelta(days=ttl_days)
        cutoff_str = format_utc_iso8601(cutoff)

        # Delete old events
        cursor.execute("DELETE FROM SEEN_EVENTS WHERE FIRST_SEEN_TS < ?", (cutoff_str,))

        deleted_count = cursor.rowcount
        conn.commit()

        return deleted_count

    def xǁEventDedupeStoreǁcleanup_old_events__mutmut_17(self, ttl_days: int = 30) -> int:
        """Clean up events older than TTL (Phase 2, Point 7).

        Parameters
        ----------
        ttl_days
            Time-to-live in days

        Returns
        -------
        int
            Number of events deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Calculate cutoff time
        now = get_current_utc()
        cutoff = now - timedelta(days=ttl_days)
        cutoff_str = format_utc_iso8601(cutoff)

        # Delete old events
        cursor.execute("DELETE FROM seen_events WHERE first_seen_ts < ?", (cutoff_str,))

        deleted_count = None
        conn.commit()

        return deleted_count
    
    xǁEventDedupeStoreǁcleanup_old_events__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁEventDedupeStoreǁcleanup_old_events__mutmut_1': xǁEventDedupeStoreǁcleanup_old_events__mutmut_1, 
        'xǁEventDedupeStoreǁcleanup_old_events__mutmut_2': xǁEventDedupeStoreǁcleanup_old_events__mutmut_2, 
        'xǁEventDedupeStoreǁcleanup_old_events__mutmut_3': xǁEventDedupeStoreǁcleanup_old_events__mutmut_3, 
        'xǁEventDedupeStoreǁcleanup_old_events__mutmut_4': xǁEventDedupeStoreǁcleanup_old_events__mutmut_4, 
        'xǁEventDedupeStoreǁcleanup_old_events__mutmut_5': xǁEventDedupeStoreǁcleanup_old_events__mutmut_5, 
        'xǁEventDedupeStoreǁcleanup_old_events__mutmut_6': xǁEventDedupeStoreǁcleanup_old_events__mutmut_6, 
        'xǁEventDedupeStoreǁcleanup_old_events__mutmut_7': xǁEventDedupeStoreǁcleanup_old_events__mutmut_7, 
        'xǁEventDedupeStoreǁcleanup_old_events__mutmut_8': xǁEventDedupeStoreǁcleanup_old_events__mutmut_8, 
        'xǁEventDedupeStoreǁcleanup_old_events__mutmut_9': xǁEventDedupeStoreǁcleanup_old_events__mutmut_9, 
        'xǁEventDedupeStoreǁcleanup_old_events__mutmut_10': xǁEventDedupeStoreǁcleanup_old_events__mutmut_10, 
        'xǁEventDedupeStoreǁcleanup_old_events__mutmut_11': xǁEventDedupeStoreǁcleanup_old_events__mutmut_11, 
        'xǁEventDedupeStoreǁcleanup_old_events__mutmut_12': xǁEventDedupeStoreǁcleanup_old_events__mutmut_12, 
        'xǁEventDedupeStoreǁcleanup_old_events__mutmut_13': xǁEventDedupeStoreǁcleanup_old_events__mutmut_13, 
        'xǁEventDedupeStoreǁcleanup_old_events__mutmut_14': xǁEventDedupeStoreǁcleanup_old_events__mutmut_14, 
        'xǁEventDedupeStoreǁcleanup_old_events__mutmut_15': xǁEventDedupeStoreǁcleanup_old_events__mutmut_15, 
        'xǁEventDedupeStoreǁcleanup_old_events__mutmut_16': xǁEventDedupeStoreǁcleanup_old_events__mutmut_16, 
        'xǁEventDedupeStoreǁcleanup_old_events__mutmut_17': xǁEventDedupeStoreǁcleanup_old_events__mutmut_17
    }
    
    def cleanup_old_events(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁEventDedupeStoreǁcleanup_old_events__mutmut_orig"), object.__getattribute__(self, "xǁEventDedupeStoreǁcleanup_old_events__mutmut_mutants"), args, kwargs, self)
        return result 
    
    cleanup_old_events.__signature__ = _mutmut_signature(xǁEventDedupeStoreǁcleanup_old_events__mutmut_orig)
    xǁEventDedupeStoreǁcleanup_old_events__mutmut_orig.__name__ = 'xǁEventDedupeStoreǁcleanup_old_events'

    def xǁEventDedupeStoreǁget_stats__mutmut_orig(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_1(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = None
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_2(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = None

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_3(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute(None)
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_4(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("XXSELECT COUNT(*) FROM seen_eventsXX")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_5(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("select count(*) from seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_6(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM SEEN_EVENTS")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_7(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = None

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_8(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[1]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_9(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute(None)
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_10(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("XXSELECT COUNT(*) FROM seen_events WHERE seen_count > 1XX")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_11(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("select count(*) from seen_events where seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_12(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM SEEN_EVENTS WHERE SEEN_COUNT > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_13(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = None

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_14(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[1]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_15(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute(None)
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_16(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("XXSELECT SUM(seen_count) FROM seen_eventsXX")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_17(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("select sum(seen_count) from seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_18(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(SEEN_COUNT) FROM SEEN_EVENTS")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_19(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = None

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_20(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] and 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_21(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[1] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_22(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 1

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_23(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            None
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_24(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = None

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_25(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["XXsourceXX"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_26(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["SOURCE"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_27(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["XXcountXX"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_28(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["COUNT"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_29(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "XXtotal_unique_eventsXX": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_30(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "TOTAL_UNIQUE_EVENTS": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_31(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "XXevents_with_duplicatesXX": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_32(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "EVENTS_WITH_DUPLICATES": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_33(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "XXtotal_seen_countXX": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_34(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "TOTAL_SEEN_COUNT": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_35(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "XXduplicate_rateXX": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_36(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "DUPLICATE_RATE": duplicates / total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_37(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates * total if total > 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_38(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total >= 0 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_39(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 1 else 0.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_40(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 1.0,
            "by_source": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_41(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "XXby_sourceXX": by_source,
        }

    def xǁEventDedupeStoreǁget_stats__mutmut_42(self) -> dict[str, Any]:
        """Get dedupe store statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including total events, duplicates
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total events
        cursor.execute("SELECT COUNT(*) FROM seen_events")
        total = cursor.fetchone()[0]

        # Events with duplicates
        cursor.execute("SELECT COUNT(*) FROM seen_events WHERE seen_count > 1")
        duplicates = cursor.fetchone()[0]

        # Total seen count
        cursor.execute("SELECT SUM(seen_count) FROM seen_events")
        total_seen = cursor.fetchone()[0] or 0

        # By source
        cursor.execute(
            """
            SELECT source, COUNT(*) as count
            FROM seen_events
            WHERE source IS NOT NULL
            GROUP BY source
        """
        )
        by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

        return {
            "total_unique_events": total,
            "events_with_duplicates": duplicates,
            "total_seen_count": total_seen,
            "duplicate_rate": duplicates / total if total > 0 else 0.0,
            "BY_SOURCE": by_source,
        }
    
    xǁEventDedupeStoreǁget_stats__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁEventDedupeStoreǁget_stats__mutmut_1': xǁEventDedupeStoreǁget_stats__mutmut_1, 
        'xǁEventDedupeStoreǁget_stats__mutmut_2': xǁEventDedupeStoreǁget_stats__mutmut_2, 
        'xǁEventDedupeStoreǁget_stats__mutmut_3': xǁEventDedupeStoreǁget_stats__mutmut_3, 
        'xǁEventDedupeStoreǁget_stats__mutmut_4': xǁEventDedupeStoreǁget_stats__mutmut_4, 
        'xǁEventDedupeStoreǁget_stats__mutmut_5': xǁEventDedupeStoreǁget_stats__mutmut_5, 
        'xǁEventDedupeStoreǁget_stats__mutmut_6': xǁEventDedupeStoreǁget_stats__mutmut_6, 
        'xǁEventDedupeStoreǁget_stats__mutmut_7': xǁEventDedupeStoreǁget_stats__mutmut_7, 
        'xǁEventDedupeStoreǁget_stats__mutmut_8': xǁEventDedupeStoreǁget_stats__mutmut_8, 
        'xǁEventDedupeStoreǁget_stats__mutmut_9': xǁEventDedupeStoreǁget_stats__mutmut_9, 
        'xǁEventDedupeStoreǁget_stats__mutmut_10': xǁEventDedupeStoreǁget_stats__mutmut_10, 
        'xǁEventDedupeStoreǁget_stats__mutmut_11': xǁEventDedupeStoreǁget_stats__mutmut_11, 
        'xǁEventDedupeStoreǁget_stats__mutmut_12': xǁEventDedupeStoreǁget_stats__mutmut_12, 
        'xǁEventDedupeStoreǁget_stats__mutmut_13': xǁEventDedupeStoreǁget_stats__mutmut_13, 
        'xǁEventDedupeStoreǁget_stats__mutmut_14': xǁEventDedupeStoreǁget_stats__mutmut_14, 
        'xǁEventDedupeStoreǁget_stats__mutmut_15': xǁEventDedupeStoreǁget_stats__mutmut_15, 
        'xǁEventDedupeStoreǁget_stats__mutmut_16': xǁEventDedupeStoreǁget_stats__mutmut_16, 
        'xǁEventDedupeStoreǁget_stats__mutmut_17': xǁEventDedupeStoreǁget_stats__mutmut_17, 
        'xǁEventDedupeStoreǁget_stats__mutmut_18': xǁEventDedupeStoreǁget_stats__mutmut_18, 
        'xǁEventDedupeStoreǁget_stats__mutmut_19': xǁEventDedupeStoreǁget_stats__mutmut_19, 
        'xǁEventDedupeStoreǁget_stats__mutmut_20': xǁEventDedupeStoreǁget_stats__mutmut_20, 
        'xǁEventDedupeStoreǁget_stats__mutmut_21': xǁEventDedupeStoreǁget_stats__mutmut_21, 
        'xǁEventDedupeStoreǁget_stats__mutmut_22': xǁEventDedupeStoreǁget_stats__mutmut_22, 
        'xǁEventDedupeStoreǁget_stats__mutmut_23': xǁEventDedupeStoreǁget_stats__mutmut_23, 
        'xǁEventDedupeStoreǁget_stats__mutmut_24': xǁEventDedupeStoreǁget_stats__mutmut_24, 
        'xǁEventDedupeStoreǁget_stats__mutmut_25': xǁEventDedupeStoreǁget_stats__mutmut_25, 
        'xǁEventDedupeStoreǁget_stats__mutmut_26': xǁEventDedupeStoreǁget_stats__mutmut_26, 
        'xǁEventDedupeStoreǁget_stats__mutmut_27': xǁEventDedupeStoreǁget_stats__mutmut_27, 
        'xǁEventDedupeStoreǁget_stats__mutmut_28': xǁEventDedupeStoreǁget_stats__mutmut_28, 
        'xǁEventDedupeStoreǁget_stats__mutmut_29': xǁEventDedupeStoreǁget_stats__mutmut_29, 
        'xǁEventDedupeStoreǁget_stats__mutmut_30': xǁEventDedupeStoreǁget_stats__mutmut_30, 
        'xǁEventDedupeStoreǁget_stats__mutmut_31': xǁEventDedupeStoreǁget_stats__mutmut_31, 
        'xǁEventDedupeStoreǁget_stats__mutmut_32': xǁEventDedupeStoreǁget_stats__mutmut_32, 
        'xǁEventDedupeStoreǁget_stats__mutmut_33': xǁEventDedupeStoreǁget_stats__mutmut_33, 
        'xǁEventDedupeStoreǁget_stats__mutmut_34': xǁEventDedupeStoreǁget_stats__mutmut_34, 
        'xǁEventDedupeStoreǁget_stats__mutmut_35': xǁEventDedupeStoreǁget_stats__mutmut_35, 
        'xǁEventDedupeStoreǁget_stats__mutmut_36': xǁEventDedupeStoreǁget_stats__mutmut_36, 
        'xǁEventDedupeStoreǁget_stats__mutmut_37': xǁEventDedupeStoreǁget_stats__mutmut_37, 
        'xǁEventDedupeStoreǁget_stats__mutmut_38': xǁEventDedupeStoreǁget_stats__mutmut_38, 
        'xǁEventDedupeStoreǁget_stats__mutmut_39': xǁEventDedupeStoreǁget_stats__mutmut_39, 
        'xǁEventDedupeStoreǁget_stats__mutmut_40': xǁEventDedupeStoreǁget_stats__mutmut_40, 
        'xǁEventDedupeStoreǁget_stats__mutmut_41': xǁEventDedupeStoreǁget_stats__mutmut_41, 
        'xǁEventDedupeStoreǁget_stats__mutmut_42': xǁEventDedupeStoreǁget_stats__mutmut_42
    }
    
    def get_stats(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁEventDedupeStoreǁget_stats__mutmut_orig"), object.__getattribute__(self, "xǁEventDedupeStoreǁget_stats__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_stats.__signature__ = _mutmut_signature(xǁEventDedupeStoreǁget_stats__mutmut_orig)
    xǁEventDedupeStoreǁget_stats__mutmut_orig.__name__ = 'xǁEventDedupeStoreǁget_stats'

    def xǁEventDedupeStoreǁclose__mutmut_orig(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def xǁEventDedupeStoreǁclose__mutmut_1(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = ""
    
    xǁEventDedupeStoreǁclose__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁEventDedupeStoreǁclose__mutmut_1': xǁEventDedupeStoreǁclose__mutmut_1
    }
    
    def close(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁEventDedupeStoreǁclose__mutmut_orig"), object.__getattribute__(self, "xǁEventDedupeStoreǁclose__mutmut_mutants"), args, kwargs, self)
        return result 
    
    close.__signature__ = _mutmut_signature(xǁEventDedupeStoreǁclose__mutmut_orig)
    xǁEventDedupeStoreǁclose__mutmut_orig.__name__ = 'xǁEventDedupeStoreǁclose'

    def __enter__(self) -> EventDedupeStore:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()


def x_create_dedupe_store__mutmut_orig(vault_path: Path) -> EventDedupeStore:
    """Create dedupe store for a vault.

    Parameters
    ----------
    vault_path
        Path to vault

    Returns
    -------
    EventDedupeStore
        Configured dedupe store
    """
    db_path = vault_path / "artifacts" / "dedupe.db"
    return EventDedupeStore(db_path)


def x_create_dedupe_store__mutmut_1(vault_path: Path) -> EventDedupeStore:
    """Create dedupe store for a vault.

    Parameters
    ----------
    vault_path
        Path to vault

    Returns
    -------
    EventDedupeStore
        Configured dedupe store
    """
    db_path = None
    return EventDedupeStore(db_path)


def x_create_dedupe_store__mutmut_2(vault_path: Path) -> EventDedupeStore:
    """Create dedupe store for a vault.

    Parameters
    ----------
    vault_path
        Path to vault

    Returns
    -------
    EventDedupeStore
        Configured dedupe store
    """
    db_path = vault_path / "artifacts" * "dedupe.db"
    return EventDedupeStore(db_path)


def x_create_dedupe_store__mutmut_3(vault_path: Path) -> EventDedupeStore:
    """Create dedupe store for a vault.

    Parameters
    ----------
    vault_path
        Path to vault

    Returns
    -------
    EventDedupeStore
        Configured dedupe store
    """
    db_path = vault_path * "artifacts" / "dedupe.db"
    return EventDedupeStore(db_path)


def x_create_dedupe_store__mutmut_4(vault_path: Path) -> EventDedupeStore:
    """Create dedupe store for a vault.

    Parameters
    ----------
    vault_path
        Path to vault

    Returns
    -------
    EventDedupeStore
        Configured dedupe store
    """
    db_path = vault_path / "XXartifactsXX" / "dedupe.db"
    return EventDedupeStore(db_path)


def x_create_dedupe_store__mutmut_5(vault_path: Path) -> EventDedupeStore:
    """Create dedupe store for a vault.

    Parameters
    ----------
    vault_path
        Path to vault

    Returns
    -------
    EventDedupeStore
        Configured dedupe store
    """
    db_path = vault_path / "ARTIFACTS" / "dedupe.db"
    return EventDedupeStore(db_path)


def x_create_dedupe_store__mutmut_6(vault_path: Path) -> EventDedupeStore:
    """Create dedupe store for a vault.

    Parameters
    ----------
    vault_path
        Path to vault

    Returns
    -------
    EventDedupeStore
        Configured dedupe store
    """
    db_path = vault_path / "artifacts" / "XXdedupe.dbXX"
    return EventDedupeStore(db_path)


def x_create_dedupe_store__mutmut_7(vault_path: Path) -> EventDedupeStore:
    """Create dedupe store for a vault.

    Parameters
    ----------
    vault_path
        Path to vault

    Returns
    -------
    EventDedupeStore
        Configured dedupe store
    """
    db_path = vault_path / "artifacts" / "DEDUPE.DB"
    return EventDedupeStore(db_path)


def x_create_dedupe_store__mutmut_8(vault_path: Path) -> EventDedupeStore:
    """Create dedupe store for a vault.

    Parameters
    ----------
    vault_path
        Path to vault

    Returns
    -------
    EventDedupeStore
        Configured dedupe store
    """
    db_path = vault_path / "artifacts" / "dedupe.db"
    return EventDedupeStore(None)

x_create_dedupe_store__mutmut_mutants : ClassVar[MutantDict] = {
'x_create_dedupe_store__mutmut_1': x_create_dedupe_store__mutmut_1, 
    'x_create_dedupe_store__mutmut_2': x_create_dedupe_store__mutmut_2, 
    'x_create_dedupe_store__mutmut_3': x_create_dedupe_store__mutmut_3, 
    'x_create_dedupe_store__mutmut_4': x_create_dedupe_store__mutmut_4, 
    'x_create_dedupe_store__mutmut_5': x_create_dedupe_store__mutmut_5, 
    'x_create_dedupe_store__mutmut_6': x_create_dedupe_store__mutmut_6, 
    'x_create_dedupe_store__mutmut_7': x_create_dedupe_store__mutmut_7, 
    'x_create_dedupe_store__mutmut_8': x_create_dedupe_store__mutmut_8
}

def create_dedupe_store(*args, **kwargs):
    result = _mutmut_trampoline(x_create_dedupe_store__mutmut_orig, x_create_dedupe_store__mutmut_mutants, args, kwargs)
    return result 

create_dedupe_store.__signature__ = _mutmut_signature(x_create_dedupe_store__mutmut_orig)
x_create_dedupe_store__mutmut_orig.__name__ = 'x_create_dedupe_store'
