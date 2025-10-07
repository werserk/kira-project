# Plugin Manifest Schema (kira-plugin.json)

**JSON Schema Version:** http://json-schema.org/draft-07/schema#  
**Related ADRs:** ADR-003  
**Status:** Stable

## Overview

Every Kira plugin must include a `kira-plugin.json` manifest file at its root. This manifest declares the plugin's identity, capabilities, permissions, and entry point.

## Required Fields

### `name` (string)

**Description:** Unique plugin identifier in kebab-case.

**Pattern:** `^[a-z0-9][a-z0-9-]*[a-z0-9]$`

**Example:**

```json
"name": "kira-inbox"
```

---

### `version` (string)

**Description:** Semantic version of the plugin.

**Pattern:** `^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?$`

**Example:**

```json
"version": "1.0.0"
```

---

### `displayName` (string)

**Description:** Human friendly display name.

**Example:**

```json
"displayName": "Inbox Normalizer"
```

---

### `description` (string)

**Description:** Short summary of the plugin capabilities.

**Example:**

```json
"description": "Normalizes incoming messages into typed entities"
```

---

### `publisher` (string)

**Description:** Name of the publishing organisation or author.

**Pattern:** `^[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]$`

**Example:**

```json
"publisher": "kira-core"
```

---

### `engines` (object)

**Description:** No description

**Properties:**

- `kira`: Required host engine version expressed as SemVer.

**Example:**

```json
"engines": {
  "kira": "^1.0.0"
}
```

---

### `permissions` (array)

**Description:** Permissions requested by the plugin.

**Item type:** string

**Allowed item values:**
- `calendar.read`
- `calendar.write`
- `vault.read`
- `vault.write`
- `fs.read`
- `fs.write`
- `net`
- `secrets.read`
- `secrets.write`
- `events.publish`
- `events.subscribe`
- `scheduler.create`
- `scheduler.cancel`
- `sandbox.execute`

**Example:**

```json
"permissions": [
  "events.subscribe",
  "events.publish"
]
```

---

### `entry` (string)

**Description:** Entry point in ``module:function`` format.

**Pattern:** `^[a-zA-Z0-9_.]+:[a-zA-Z0-9_]+$`

**Example:**

```json
"entry": "kira_plugin_inbox.plugin:activate"
```

---

### `capabilities` (array)

**Description:** Capabilities implemented by the plugin.

**Item type:** string

**Allowed item values:**
- `pull`
- `push`
- `timebox`
- `notify`
- `schedule`
- `transform`
- `validate`
- `sync`
- `normalize`

**Example:**

```json
"capabilities": ["pull", "normalize"]
```

---

### `contributes` (object)

**Description:** Contribution points used by the plugin.

**Properties:**

- `events`: Events the plugin subscribes to.
- `commands`: Commands exposed to end-users.
- `adapters`: First-party adapters the plugin integrates with.

**Example:**

```json
"contributes": {
  "events": ["inbox.normalized"],
  "commands": []
}
```

---

## Optional Fields

### `configSchema` (object, optional)

Configuration schema understood by the host UI.

### `sandbox` (object, optional)

Sandbox configuration requested by the plugin.

### `dependencies` (object, optional)

Runtime dependencies required by the plugin.

### `keywords` (array, optional)

Keywords to improve marketplace search.

### `homepage` (string, optional)

Homepage URL for the plugin.

### `repository` (object, optional)

Source control repository information.

### `bugs` (object, optional)

Bug tracker or support contact details.

### `license` (string, optional)

License identifier for the plugin distribution.

## Complete Example

```json
{
  "name": "kira-inbox",
  "version": "1.0.0",
  "displayName": "Inbox Normalizer",
  "description": "Normalizes incoming messages into typed entities based on schemas",
  "publisher": "kira-core",
  "engines": {
    "kira": "^1.0.0"
  },
  "entry": "kira_plugin_inbox.plugin:activate",
  "permissions": [
    "events.subscribe",
    "events.publish",
    "vault.write"
  ],
  "capabilities": ["pull", "normalize"],
  "contributes": {
    "events": ["inbox.normalized"],
    "commands": []
  },
  "configSchema": {
    "type": "object",
    "properties": {
      "confidence_threshold": {
        "type": "number",
        "minimum": 0,
        "maximum": 1,
        "default": 0.8
      }
    }
  },
  "sandbox": {
    "strategy": "subprocess",
    "timeoutMs": 30000,
    "memoryLimitMb": 512,
    "networkAccess": false,
    "fsAccess": {
      "readPaths": [],
      "writePaths": []
    }
  }
}
```

## Permission Reference

### Core Permissions

- `events.subscribe` - Subscribe to event bus events
- `events.publish` - Publish events to event bus
- `scheduler.create` - Create scheduled jobs
- `scheduler.cancel` - Cancel scheduled jobs
- `net` - Network access (HTTP/HTTPS)
- `secrets.read` - Read secrets from secret manager
- `secrets.write` - Write secrets to secret manager

### Vault Permissions

- `vault.read` - Read entities from Vault
- `vault.write` - Create/update entities in Vault
- `calendar.read` - Read calendar events
- `calendar.write` - Create/update calendar events

### Filesystem Permissions

- `fs.read` - Read files from filesystem (with path restrictions)
- `fs.write` - Write files to filesystem (with path restrictions)
- `sandbox.execute` - Execute external processes (restricted)

## Capability Reference

Capabilities declare what the plugin can do:

- `pull` - Can pull data from external sources
- `push` - Can push data to external sources
- `normalize` - Can normalize/transform data
- `timebox` - Can create timeboxes/calendar blocks
- `search` - Provides search functionality
- `analyze` - Performs analysis on data

## Validation

Use the CLI to validate manifests:

```bash
# Validate specific manifest
python -m kira.cli validate --manifest path/to/kira-plugin.json

# Validate all manifests in project
make validate
```

Or programmatically:

```python
from kira.plugin_sdk.manifest import validate_plugin_manifest

with open("kira-plugin.json") as f:
    manifest = json.load(f)

result = validate_plugin_manifest(manifest)
if not result["valid"]:
    print("Errors:", result["errors"])
```

## See Also

- [Plugin SDK Documentation](../sdk.md)
- [ADR-003: Plugin Manifest JSON Schema](../adr/ADR-003-plugin-manifest-json-schema.md)
- [Permissions Documentation](../permissions.md)

---

**Last Updated:** 2025-10-07  
**Schema Version:** 1.0.0
