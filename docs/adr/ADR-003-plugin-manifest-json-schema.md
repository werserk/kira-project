---
type: decision
id: ADR-003
title: Plugin manifest (kira-plugin.json) with JSON Schema validation
date: 2025-09-19
status: accepted
owners: [kira-core]
related: [ADR-001, ADR-002, ADR-004, ADR-009]
drivers: [contract clarity, auto-loading, safe permissions, tooling, compatibility]
---

## Context

Plugins must declare a clear, self-documenting contract understood by both the host and tooling. We need a single manifest file that captures identity, engine compatibility, permissions, entry point, capabilities, contributions, configuration schema, and sandboxing preferences. This enables static validation, safer loading, and better UX for authors.

## Decision

Adopt `kira-plugin.json` as the canonical plugin manifest and validate it with a shared JSON Schema at development and load time.

- Canonical fields (minimum set):
  - `name`, `version`, `displayName`, `description`, `publisher`
  - `engines.kira` (SemVer compatibility with the host)
  - `permissions` — explicit permission list
  - `entry` — `module:function`
  - `capabilities` — declared capabilities (e.g., `pull`, `push`, `timebox`, `normalize`)
  - `contributes.events`, `contributes.commands`, `contributes.adapters`
  - `configSchema` — plugin-specific config schema (JSON Schema subset)
  - `sandbox` — isolation strategy and limits

- JSON Schema enforcement:
  - Schema lives in code (`kira.plugin_sdk.manifest`), can be generated to a file via `scripts/gen_manifest_schema.py`.
  - CI validates all manifests in `src/kira/plugins/*/kira-plugin.json` and fails with readable errors.

- Backwards compatibility:
  - Schema evolves with SemVer; breaking schema changes require a new major. The loader may support targeted backward shims, but only for a limited deprecation window.

## Alternatives

- Python entry points only (no manifest) — loses explicit permissions, engine gating, and static validation. Rejected.
- Multiple manifest files (split concerns) — increases drift risk and complexity. Rejected.

## Implementation/Migration

1) Schema authority
   - Keep the authoritative schema in `kira.plugin_sdk.manifest.PLUGIN_MANIFEST_SCHEMA` with a programmatic accessor `get_manifest_schema()`.
   - Provide `PluginManifestValidator` with `validate_manifest()` and `validate_manifest_file()`.

2) Tooling integration
   - `scripts/gen_manifest_schema.py` writes `manifest-schema.json` and `MANIFEST_SCHEMA.md` to the SDK folder for external validators (e.g., `ajv`).
   - The CLI can expose `kira plugins validate` to validate manifests locally.

3) CI checks
   - Validate every `kira-plugin.json` in the repo against the shared schema. Fail fast with field-level paths.
   - Example manifests in `plugins/calendar` and `plugins/inbox` must pass.

4) Loader behavior
   - On plugin load, validate manifest first; if invalid, reject with actionable messages.
   - Enforce `engines.kira` SemVer gating and map `permissions` to sandbox capabilities (see ADR-004).

## Risks

- Schema creep and overfitting — mitigate by keeping core fields minimal and providing `configSchema` for plugin-specific concerns.
- Divergence between code and schema file — mitigate by generating the file from code and testing both.
- Strictness blocking innovation — mitigate via minor-version extensions and clear deprecation policy.

## Metrics/DoD

Acceptance criteria (Definition of Done):

- All built-in plugins include a valid `kira-plugin.json` that passes CI validation.
- Field-level error reporting is present (path included) on invalid manifests.
- The schema can be generated via `scripts/gen_manifest_schema.py`, producing both `manifest-schema.json` and `MANIFEST_SCHEMA.md`.
- Loader enforces `engines.kira` compatibility and denies incompatible plugins with clear errors.
- Documentation in `docs/sdk.md` contains a canonical manifest example and field explanations.
