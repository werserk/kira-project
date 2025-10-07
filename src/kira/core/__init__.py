"""Core components of Kira system (ADR-004, ADR-005)."""

from .canonical_events import CANONICAL_EVENTS, EventDefinition, get_event_definition, is_canonical_event
from .config import load_config, save_config
from .events import Event, EventBus, EventHandler, RetryPolicy, create_event_bus
from .plugin_loader import PluginLoader, PluginLoadError, PluginVersionError
from .policy import PermissionDeniedError, Policy, PolicyViolation, check_fs_access, check_permission
from .policy import SandboxConfig as PolicySandboxConfig
from .sandbox import PluginProcess, Sandbox, SandboxConfig, SandboxError, create_sandbox
from .scheduler import Job, JobStatus, Scheduler, Trigger, TriggerType, create_scheduler

__all__ = [
    # Config
    "load_config",
    "save_config",
    # Events (ADR-005)
    "Event",
    "EventBus",
    "EventHandler",
    "RetryPolicy",
    "create_event_bus",
    # Scheduler (ADR-005)
    "Job",
    "JobStatus",
    "Scheduler",
    "Trigger",
    "TriggerType",
    "create_scheduler",
    # Canonical Events (ADR-005)
    "CANONICAL_EVENTS",
    "EventDefinition",
    "get_event_definition",
    "is_canonical_event",
    # Policy (ADR-004)
    "PermissionDeniedError",
    "Policy",
    "PolicyViolation",
    "PolicySandboxConfig",
    "check_fs_access",
    "check_permission",
    # Sandbox (ADR-004)
    "PluginProcess",
    "Sandbox",
    "SandboxConfig",
    "SandboxError",
    "create_sandbox",
    # Plugin Loader
    "PluginLoadError",
    "PluginLoader",
    "PluginVersionError",
]

