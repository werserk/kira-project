---
type: decision
id: ADR-002
title: Stable Plugin SDK (context, decorators, types)
date: 2025-09-19
status: accepted
owners: [kira-core]
related: [ADR-001, ADR-003, ADR-004, ADR-009, ADR-015, ADR-016]
drivers: [extensibility, compatibility, safety, developer experience, testability]
---

## Context

We need a stable, well-documented Plugin SDK that enables plugins to evolve independently from the core, while preserving safety, compatibility, and a great developer experience. Direct imports into core internals create tight coupling, hinder upgrades, and weaken sandbox and permission boundaries (see ADR-004). The SDK must be the single, stable surface for plugin authors.

## Decision

Adopt a dedicated `kira.plugin_sdk` package as the only supported import surface for plugins. The SDK provides typed, documented facades to core capabilities and defines decorators, types, and manifest/schema helpers. We commit to semantic versioning and strict compatibility guarantees for this surface.

- Package and modules (minimum set):
  - `kira.plugin_sdk.context` — runtime execution context and facades: `events`, `logger`, `scheduler`, `kv`, `secrets` (and future: `vault`, `fs`, etc.).
  - `kira.plugin_sdk.decorators` — `on_event(event_name)`, `command(name)`, `permission(perm)`, `timeout(seconds)`, `retry(max_attempts, delay)`.
  - `kira.plugin_sdk.types` — public types and protocol interfaces for plugin authors. Stable and typed.
  - `kira.plugin_sdk.permissions` — permission names, helpers, and guidance.
  - `kira.plugin_sdk.manifest` — manifest schema accessor/validation helpers used by tooling/CI (see ADR-003).
  - `kira.plugin_sdk.rpc` — optional thin RPC abstractions for safe host interactions (as needed).

- Supported imports (canonical):
  - `from kira.plugin_sdk import context, decorators, types, permissions, manifest, rpc`
  - or specific: `from kira.plugin_sdk.decorators import on_event, command`

- Compatibility guarantees:
  - SDK follows SemVer. Within `1.x`, public names, call signatures, and behavioral contracts remain compatible.
  - Deprecations are announced, flagged via `DeprecationWarning` for ≥2 minor versions, and removed only in the next major.
  - Plugins declare required engine via manifest `engines.kira` (SemVer). The host rejects incompatible plugins at load time.

- Forbidden patterns:
  - Plugins must not import from `kira.core.*` or other internal modules; only `kira.plugin_sdk.*` is allowed.
  - Plugins must not import other plugins directly; interaction is via events/contracts (see ADR-001, ADR-009).

- Documentation and typing:
  - All SDK docstrings are in English and fully type-annotated. Public API coverage is enforced by `mypy` and contract tests.
  - Example snippets and guidelines are published in `docs/sdk.md` and inline docstrings.

## Alternatives

- Direct core imports in plugins — fast initially but brittle and unsafe; breaks boundaries and hampers upgrades. Rejected.
- Reflection/dynamic attribute access — obscures contracts, harms type-checking and DX. Rejected.
- Per-plugin shims vendoring core pieces — duplicates logic and increases drift risk. Rejected.

## Implementation/Migration

1) Define and freeze the SDK surface
   - Establish `__all__` in `kira/plugin_sdk/__init__.py` exporting only supported modules/symbols.
   - Move or wrap any accidental core-leaking helpers behind explicit facades.

2) Strong typing and docs
   - Add precise type hints to all public functions/classes; enable `mypy --strict` for `plugin_sdk/`.
   - Ensure all docstrings are English, consistent, and example-backed.

3) Import boundary enforcement
   - AST/rg-based CI check: forbid `from kira.core` or `import kira.core` in `src/kira/plugins/*`.
   - Allow only `kira.plugin_sdk.*` imports from plugins.

4) Manifest and SemVer gating
   - Validate all `kira-plugin.json` manifests against the shared JSON Schema (ADR-003) in CI.
   - Host loader checks `engines.kira` compatibility at load time and rejects mismatches with actionable errors.

5) Contract tests
   - Introduce `tests/unit/test_sdk_surface.py` to enumerate public symbols and check signatures and behavior contracts.
   - Add `tests/unit/test_import_boundaries.py` to ensure plugins only import SDK and not core internals.

6) Documentation and examples
   - Provide a minimal example plugin using only `kira.plugin_sdk` in `examples/` and reference it in `docs/sdk.md`.

## Risks

- SDK bloat over time — mitigate via modularization, periodic pruning, and strict review of new surface.
- Leaky abstractions — mitigate by focusing on use-case-driven facades and contract tests.
- Version skew between host and plugins — mitigate with manifest gating and clear migration guides.
- Over-constraining the SDK — mitigate by adding extension points (events, capabilities) rather than deep APIs.

## Metrics/DoD

Acceptance criteria (Definition of Done):

- Public API lock:
  - `tests/unit/test_sdk_surface.py` enumerates and asserts public symbols (`__all__`) for `context`, `decorators`, `types`, `permissions`, `manifest`, `rpc`.
  - `mypy --strict` passes for `src/kira/plugin_sdk/`.

- Import boundaries:
  - `tests/unit/test_import_boundaries.py` fails on any plugin importing `kira.core.*` or any non-SDK module from core.

- Manifest and engine gating:
  - CI validates all `kira-plugin.json`. A negative test with incompatible `engines.kira` is rejected by the host loader.

- Documentation quality:
  - All public SDK docstrings are in English and have at least one example snippet.
  - `docs/sdk.md` includes a quickstart using only SDK imports.

- DX signals:
  - A sample plugin compiles and runs using only `kira.plugin_sdk.*` imports with no private core imports detected.

Metrics:

- 0 violations of import boundary checks per CI run.
- 100% of public SDK symbols covered by contract tests.
- CI time impact < N minutes; SDK unit tests complete in < M seconds.
