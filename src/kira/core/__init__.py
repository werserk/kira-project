"""Core components of Kira system (ADR-004, ADR-005)."""

from .canonical_events import CANONICAL_EVENTS, EventDefinition, get_event_definition, is_canonical_event
from .config import load_config, save_config
from .events import Event, EventBus, EventHandler, RetryPolicy, create_event_bus
from .host import Entity, EntityNotFoundError, HostAPI, VaultError, create_host_api
from .ids import (
    AliasTracker,
    CollisionDetector,
    EntityId,
    generate_entity_id,
    get_known_entity_types,
    is_valid_entity_id,
    parse_entity_id,
    register_entity_type,
    sanitize_filename,
    validate_entity_id,
)
from .links import Link, LinkGraph, LinkType, extract_links_from_content, extract_links_from_frontmatter
from .md_io import MarkdownDocument, MarkdownIOError, parse_markdown, read_markdown, write_markdown
from .plugin_loader import PluginLoader, PluginLoadError, PluginVersionError
from .policy import PermissionDeniedError, Policy, PolicyViolation, check_fs_access, check_permission
from .policy import SandboxConfig as PolicySandboxConfig
from .sandbox import PluginProcess, Sandbox, SandboxConfig, SandboxError, create_sandbox
from .scheduler import Job, JobStatus, Scheduler, Trigger, TriggerType, create_scheduler
from .time import (
    TimeConfig,
    convert_timezone,
    ensure_timezone,
    format_datetime_for_id,
    get_current_time,
    get_default_timezone,
    load_timezone_from_config,
    set_default_timezone,
)
from .vault_facade import VaultFacade, create_vault_facade
from .vault_init import VaultInitError, get_vault_info, init_vault, verify_vault_structure
from .vault_rpc_handlers import VaultRPCHandlers, register_vault_rpc_handlers

__all__ = [
    # Canonical Events (ADR-005)
    "CANONICAL_EVENTS",
    # IDs (ADR-008)
    "AliasTracker",
    "CollisionDetector",
    # Host API (ADR-006)
    "Entity",
    "EntityId",
    "EntityNotFoundError",
    # Events (ADR-005)
    "Event",
    "EventBus",
    "EventDefinition",
    "EventHandler",
    "HostAPI",
    # Scheduler (ADR-005)
    "Job",
    "JobStatus",
    # Links (ADR-016)
    "Link",
    "LinkGraph",
    "LinkType",
    # Markdown I/O
    "MarkdownDocument",
    "MarkdownIOError",
    # Policy (ADR-004)
    "PermissionDeniedError",
    # Plugin Loader
    "PluginLoadError",
    "PluginLoader",
    # Sandbox (ADR-004)
    "PluginProcess",
    "PluginVersionError",
    "Policy",
    "PolicySandboxConfig",
    "PolicyViolation",
    "RetryPolicy",
    "Sandbox",
    "SandboxConfig",
    "SandboxError",
    "Scheduler",
    # Time (ADR-008)
    "TimeConfig",
    "Trigger",
    "TriggerType",
    "VaultError",
    # Vault Facade (ADR-006)
    "VaultFacade",
    # Vault Init (ADR-007)
    "VaultInitError",
    # Vault RPC Handlers (ADR-006)
    "VaultRPCHandlers",
    "check_fs_access",
    "check_permission",
    "convert_timezone",
    "create_event_bus",
    "create_host_api",
    "create_sandbox",
    "create_scheduler",
    "create_vault_facade",
    "ensure_timezone",
    "extract_links_from_content",
    "extract_links_from_frontmatter",
    "format_datetime_for_id",
    "generate_entity_id",
    "get_current_time",
    "get_default_timezone",
    "get_event_definition",
    "get_known_entity_types",
    "get_vault_info",
    "init_vault",
    "is_canonical_event",
    "is_valid_entity_id",
    # Config
    "load_config",
    "load_timezone_from_config",
    "parse_entity_id",
    "parse_markdown",
    "read_markdown",
    "register_entity_type",
    "register_vault_rpc_handlers",
    "sanitize_filename",
    "save_config",
    "set_default_timezone",
    "validate_entity_id",
    "verify_vault_structure",
    "write_markdown",
]
