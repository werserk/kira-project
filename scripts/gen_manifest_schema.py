#!/usr/bin/env python3
"""Generate manifest schema files from SDK definition.

Generates:
- manifest-schema.json: JSON Schema file for external validators
- MANIFEST_SCHEMA.md: Human-readable schema documentation

Related: ADR-003
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from kira.plugin_sdk.manifest import PLUGIN_MANIFEST_SCHEMA


def generate_json_schema(output_path: Path) -> None:
    """Generate manifest-schema.json file.
    
    Parameters
    ----------
    output_path
        Path to write JSON schema file
    """
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(PLUGIN_MANIFEST_SCHEMA, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Generated: {output_path}")


def generate_markdown_docs(output_path: Path) -> None:
    """Generate MANIFEST_SCHEMA.md documentation.
    
    Parameters
    ----------
    output_path
        Path to write Markdown documentation
    """
    schema = PLUGIN_MANIFEST_SCHEMA
    
    markdown = f"""# Plugin Manifest Schema (kira-plugin.json)

**JSON Schema Version:** {schema.get('$schema', 'Draft-07')}  
**Related ADRs:** ADR-003  
**Status:** Stable

## Overview

Every Kira plugin must include a `kira-plugin.json` manifest file at its root. This manifest declares the plugin's identity, capabilities, permissions, and entry point.

## Required Fields

"""
    
    # Add required fields
    required_fields = schema.get("required", [])
    properties = schema.get("properties", {})
    
    for field in required_fields:
        field_schema = properties.get(field, {})
        field_type = field_schema.get("type", "unknown")
        description = field_schema.get("description", "No description")
        
        markdown += f"### `{field}` ({field_type})\n\n"
        markdown += f"**Description:** {description}\n\n"
        
        # Add pattern if exists
        if "pattern" in field_schema:
            markdown += f"**Pattern:** `{field_schema['pattern']}`\n\n"
        
        # Add enum if exists
        if "enum" in field_schema:
            markdown += "**Allowed values:**\n"
            for value in field_schema["enum"]:
                markdown += f"- `{value}`\n"
            markdown += "\n"
        
        # Add nested properties for objects
        if field_type == "object" and "properties" in field_schema:
            markdown += "**Properties:**\n\n"
            for prop_name, prop_schema in field_schema["properties"].items():
                prop_desc = prop_schema.get("description", "")
                markdown += f"- `{prop_name}`: {prop_desc}\n"
            markdown += "\n"
        
        # Add item type for arrays
        if field_type == "array" and "items" in field_schema:
            items_schema = field_schema["items"]
            item_type = items_schema.get("type", "unknown")
            markdown += f"**Item type:** {item_type}\n\n"
            
            if "enum" in items_schema:
                markdown += "**Allowed item values:**\n"
                for value in items_schema["enum"]:
                    markdown += f"- `{value}`\n"
                markdown += "\n"
        
        # Add example
        markdown += "**Example:**\n\n"
        markdown += "```json\n"
        
        if field == "name":
            markdown += '"name": "kira-inbox"\n'
        elif field == "version":
            markdown += '"version": "1.0.0"\n'
        elif field == "displayName":
            markdown += '"displayName": "Inbox Normalizer"\n'
        elif field == "description":
            markdown += '"description": "Normalizes incoming messages into typed entities"\n'
        elif field == "publisher":
            markdown += '"publisher": "kira-core"\n'
        elif field == "engines":
            markdown += '"engines": {\n  "kira": "^1.0.0"\n}\n'
        elif field == "permissions":
            markdown += '"permissions": [\n  "events.subscribe",\n  "events.publish"\n]\n'
        elif field == "entry":
            markdown += '"entry": "kira_plugin_inbox.plugin:activate"\n'
        elif field == "capabilities":
            markdown += '"capabilities": ["pull", "normalize"]\n'
        elif field == "contributes":
            markdown += '"contributes": {\n  "events": ["inbox.normalized"],\n  "commands": []\n}\n'
        
        markdown += "```\n\n"
        markdown += "---\n\n"
    
    # Add optional fields section
    markdown += "## Optional Fields\n\n"
    
    optional_fields = [f for f in properties.keys() if f not in required_fields]
    
    for field in optional_fields:
        field_schema = properties.get(field, {})
        field_type = field_schema.get("type", "unknown")
        description = field_schema.get("description", "No description")
        
        markdown += f"### `{field}` ({field_type}, optional)\n\n"
        markdown += f"{description}\n\n"
    
    # Add complete example
    markdown += """## Complete Example

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
"""
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown)
    
    print(f"✅ Generated: {output_path}")


def main() -> None:
    """Main entry point."""
    # Output paths
    schema_json_path = PROJECT_ROOT / "src" / "kira" / "plugin_sdk" / "manifest-schema.json"
    schema_md_path = PROJECT_ROOT / "docs" / "MANIFEST_SCHEMA.md"
    
    print("🔧 Generating manifest schema files...")
    print()
    
    # Generate files
    generate_json_schema(schema_json_path)
    generate_markdown_docs(schema_md_path)
    
    print()
    print("✅ Schema generation complete!")
    print()
    print("Files generated:")
    print(f"  - {schema_json_path.relative_to(PROJECT_ROOT)}")
    print(f"  - {schema_md_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
