"""Helpers and schema definitions for ``kira-plugin.json`` manifests."""

from __future__ import annotations

import copy
import json
from typing import Any

from jsonschema import Draft7Validator

PLUGIN_MANIFEST_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "name",
        "version",
        "displayName",
        "description",
        "publisher",
        "engines",
        "permissions",
        "entry",
        "capabilities",
        "contributes",
    ],
    "properties": {
        "name": {
            "type": "string",
            "pattern": "^[a-z0-9][a-z0-9-]*[a-z0-9]$",
            "minLength": 3,
            "maxLength": 50,
            "description": "Unique plugin identifier in kebab-case.",
        },
        "version": {
            "type": "string",
            "pattern": "^\\d+\\.\\d+\\.\\d+(-[a-zA-Z0-9.-]+)?$",
            "description": "Semantic version of the plugin.",
        },
        "displayName": {
            "type": "string",
            "minLength": 1,
            "maxLength": 100,
            "description": "Human friendly display name.",
        },
        "description": {
            "type": "string",
            "minLength": 10,
            "maxLength": 500,
            "description": "Short summary of the plugin capabilities.",
        },
        "publisher": {
            "type": "string",
            "pattern": "^[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]$",
            "minLength": 2,
            "maxLength": 30,
            "description": "Name of the publishing organisation or author.",
        },
        "engines": {
            "type": "object",
            "required": ["kira"],
            "properties": {
                "kira": {
                    "type": "string",
                    "pattern": "^\\^?\\d+\\.\\d+\\.\\d+$",
                    "description": "Required host engine version expressed as SemVer.",
                }
            },
            "additionalProperties": False,
        },
        "permissions": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    "calendar.read",
                    "calendar.write",
                    "vault.read",
                    "vault.write",
                    "fs.read",
                    "fs.write",
                    "net",
                    "secrets.read",
                    "secrets.write",
                    "events.publish",
                    "events.subscribe",
                    "scheduler.create",
                    "scheduler.cancel",
                    "sandbox.execute",
                ],
            },
            "uniqueItems": True,
            "description": "Permissions requested by the plugin.",
        },
        "entry": {
            "type": "string",
            "pattern": "^[a-zA-Z0-9_.]+:[a-zA-Z0-9_]+$",
            "description": "Entry point in ``module:function`` format.",
        },
        "capabilities": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    "pull",
                    "push",
                    "timebox",
                    "notify",
                    "schedule",
                    "transform",
                    "validate",
                    "sync",
                    "normalize",
                ],
            },
            "uniqueItems": True,
            "description": "Capabilities implemented by the plugin.",
        },
        "configSchema": {
            "type": "object",
            "patternProperties": {
                "^[a-zA-Z0-9_.]+$": {
                    "type": "object",
                    "required": ["type"],
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": [
                                "string",
                                "integer",
                                "number",
                                "boolean",
                                "array",
                                "object",
                            ],
                        },
                        "default": {"description": "Default value."},
                        "description": {"type": "string", "maxLength": 200},
                        "required": {"type": "boolean"},
                        "enum": {"type": "array", "minItems": 1},
                        "minimum": {"type": "number"},
                        "maximum": {"type": "number"},
                        "minLength": {"type": "integer", "minimum": 0},
                        "maxLength": {"type": "integer", "minimum": 1},
                    },
                    "additionalProperties": False,
                }
            },
            "additionalProperties": False,
            "description": "Configuration schema understood by the host UI.",
        },
        "contributes": {
            "type": "object",
            "properties": {
                "events": {
                    "type": "array",
                    "items": {"type": "string", "pattern": "^[a-zA-Z0-9_.]+$"},
                    "uniqueItems": True,
                    "description": "Events the plugin subscribes to.",
                },
                "commands": {
                    "type": "array",
                    "items": {"type": "string", "pattern": "^[a-zA-Z0-9_.]+$"},
                    "uniqueItems": True,
                    "description": "Commands exposed to end-users.",
                },
                "adapters": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["telegram", "gcal", "filesystem", "email", "webhook"],
                    },
                    "uniqueItems": True,
                    "description": "First-party adapters the plugin integrates with.",
                },
            },
            "additionalProperties": False,
            "description": "Contribution points used by the plugin.",
        },
        "sandbox": {
            "type": "object",
            "properties": {
                "strategy": {
                    "type": "string",
                    "enum": ["subprocess", "thread", "inline"],
                    "default": "subprocess",
                    "description": "Sandbox strategy selected by the plugin.",
                },
                "timeoutMs": {
                    "type": "integer",
                    "minimum": 1000,
                    "maximum": 300000,
                    "default": 30000,
                    "description": "Execution timeout in milliseconds.",
                },
                "memoryLimit": {
                    "type": "integer",
                    "minimum": 64,
                    "maximum": 1024,
                    "description": "Optional memory limit in megabytes.",
                },
                "networkAccess": {"type": "boolean", "default": False},
                "fsAccess": {
                    "type": "object",
                    "properties": {
                        "read": {"type": "array", "items": {"type": "string"}},
                        "write": {"type": "array", "items": {"type": "string"}},
                    },
                    "additionalProperties": False,
                    "description": "Allowed filesystem paths for sandbox access.",
                },
            },
            "additionalProperties": False,
            "description": "Sandbox configuration requested by the plugin.",
        },
        "dependencies": {
            "type": "object",
            "patternProperties": {
                "^[a-zA-Z0-9_.-]+$": {
                    "type": "string",
                    "pattern": "^[~^]?\\d+\\.\\d+\\.\\d+$",
                }
            },
            "description": "Runtime dependencies required by the plugin.",
        },
        "keywords": {
            "type": "array",
            "items": {"type": "string", "maxLength": 30},
            "maxItems": 10,
            "uniqueItems": True,
            "description": "Keywords to improve marketplace search.",
        },
        "homepage": {
            "type": "string",
            "format": "uri",
            "description": "Homepage URL for the plugin.",
        },
        "repository": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["git", "hg", "svn"]},
                "url": {"type": "string", "format": "uri"},
            },
            "required": ["type", "url"],
            "additionalProperties": False,
            "description": "Source control repository information.",
        },
        "bugs": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "format": "uri"},
                "email": {"type": "string", "format": "email"},
            },
            "additionalProperties": False,
            "description": "Bug tracker or support contact details.",
        },
        "license": {
            "type": "string",
            "enum": [
                "MIT",
                "Apache-2.0",
                "GPL-3.0",
                "BSD-3-Clause",
                "ISC",
                "Unlicense",
                "Proprietary",
            ],
            "description": "License identifier for the plugin distribution.",
        },
    },
    "additionalProperties": False,
}


class PluginManifestValidator:
    """Validate plugin manifests against :data:`PLUGIN_MANIFEST_SCHEMA`.

    Example:
        >>> from kira.plugin_sdk.manifest import PluginManifestValidator
        >>> validator = PluginManifestValidator()
        >>> validator.validate_manifest({"name": "demo", "version": "1.0.0"})
        ['[required] 'displayName' is a required property (path: <root>)']
    """

    def __init__(self) -> None:
        self.validator = Draft7Validator(PLUGIN_MANIFEST_SCHEMA)

    def validate_manifest(self, manifest_data: dict[str, Any]) -> list[str]:
        """Return a list of human readable validation errors."""

        collected: list[str] = []

        try:
            for error in sorted(
                self.validator.iter_errors(manifest_data),
                key=lambda err: list(err.absolute_path),
            ):
                location = " -> ".join(str(part) for part in error.absolute_path) or "<root>"
                collected.append(f"[{error.validator}] {error.message} (path: {location})")
        except Exception as exc:  # pragma: no cover - defensive path
            collected.append(f"Unexpected validation error: {exc}")

        return collected

    def validate_manifest_file(self, file_path: str) -> list[str]:
        """Load ``file_path`` and validate its manifest contents."""

        try:
            with open(file_path, encoding="utf-8") as file:
                manifest_data = json.load(file)
        except FileNotFoundError:
            return [f"Manifest file not found: {file_path}"]
        except json.JSONDecodeError as exc:
            return [f"Invalid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})"]
        except Exception as exc:  # pragma: no cover - defensive path
            return [f"Unable to read manifest: {exc}"]

        return self.validate_manifest(manifest_data)


def validate_plugin_manifest(manifest_data: dict[str, Any]) -> bool:
    """Return ``True`` when ``manifest_data`` passes schema validation."""

    validator = PluginManifestValidator()
    errors = validator.validate_manifest(manifest_data)
    return not errors


def get_manifest_schema() -> dict[str, Any]:
    """Return a deep copy of :data:`PLUGIN_MANIFEST_SCHEMA`."""

    return copy.deepcopy(PLUGIN_MANIFEST_SCHEMA)


__all__ = [
    "PLUGIN_MANIFEST_SCHEMA",
    "PluginManifestValidator",
    "get_manifest_schema",
    "validate_plugin_manifest",
]
