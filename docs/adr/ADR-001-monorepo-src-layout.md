---
type: decision
id: ADR-001
title: Monorepo with src-layout and co-located built-in plugins
date: 2025-09-19
status: accepted
owners: [werserk]
related: [ADR-002, ADR-003, ADR-004, ADR-009, ADR-015, ADR-016]
drivers: [iteration speed, unified CI, stable SDK contracts, simplified onboarding, plugin isolation, reproducible builds]
---

## Context

We need a productive plugin platform (built-in + external) focused on rapid feature delivery, strict SDK contracts, and reproducible releases. At the MVP stage it is critical to:

- Reduce coordination and release overhead (single CI/CD, unified code standards, unified API/SDK versioning).
- Simplify onboarding and plugin authoring (clear structure, predictable paths, ready-to-use templates).
- Preserve strict architectural boundaries between `core` and `plugins`, preventing dependency leakage and tight coupling.
- Enable future extraction of plugins to external repositories once the SDK stabilizes (see ADR-002, ADR-003).

Conclusion: multi-repo is premature; we adopt a monorepo with src-layout and co-located built-in plugins, reinforced by engineering guardrails that enforce boundaries from day one.

## Decision

Adopt a monorepo with `src`-layout where `core` and built-in plugins co-exist but are separated by layer boundaries and import policies.

- Directory structure (current minimum):

```
src/kira/
  core/                 # core: events, scheduler, sandbox, host API, policy, etc.
  plugin_sdk/           # stable SDK contracts (see ADR-002)
  adapters/             # integrations (e.g., telegram, gcal, filesystem)
  pipelines/            # thin orchestration (see ADR-009)
  cli/                  # canonical CLI "kira ..."
  plugins/              # built-in plugins (co-located)
    inbox/
      kira-plugin.json  # manifest (see ADR-003)
      src/kira_plugin_inbox/
        plugin.py
    calendar/
      kira-plugin.json  
      src/kira_plugin_calendar/
        plugin.py
    deadlines/
      ...
docs/
tests/
  unit/
  integration/
logs/
dist/
```

- Dependency policy (Dependency Rule):
  - `core` never imports from `plugins/*`.
  - `plugins/*` may import only `plugin_sdk` and `core` public facades (contractual entry points, not private modules).
  - Plugins do not import each other directly; they communicate via events/bus/contracts.

- Contract boundaries:
  - `plugin_sdk` is the single stable layer for plugins. Violations are caught by tests/linters/graph checks.
  - Plugin manifests are validated against a shared JSON Schema (see ADR-003). Schema is generated/synchronized via `scripts/gen_manifest_schema.py`.

- Distribution and packaging:
  - For MVP, plugins are shipped from the monorepo as part of the app. Once the SDK stabilizes, we may publish wheels from `plugins/*/` or move plugins out without breaking runtime contracts.
  - Unified CI builds, lints, types, and tests the entire tree, with path-based caching.

- Engineering guardrails:
  - Static import analysis to prevent cross-plugin imports and imports from private `core` modules.
  - Shared pre-commit hooks: formatting (Black), quality (Ruff), types (mypy), security where possible.
  - Test harness: unit + integration, mandatory for each built-in plugin and key adapters.

## Alternatives

- Multi-repo from day one. Cons: fragmented CI, complex SDK sync, higher barrier to entry, slower MVP. Rejected until SDK stabilizes.
- Flat `src` without a dedicated `plugins/`. Cons: boundary erosion, unauthorized imports, worse readability.
- Namespace packages per plugin within the monorepo. Pros: closer to future wheel publishing. Cons: more build complexity now; defer until stable.
- Git submodules for plugins. Cons: complex update flows, poor DX, additional overhead.

## Implementation/Migration

1) Structure and templates
   - Finalize directories as in Decision. Provide a plugin template (cookiecutter or `kira cli` command) that creates `kira-plugin.json`, `src/kira_plugin_<name>/plugin.py`, and test files.

2) Import policies and checks
   - Enforce import rules in CI (script/linter): forbid `plugins/* -> plugins/*`, forbid `plugins/* -> core/<private>`.
   - Configure Ruff rules (e.g., `I`, `F`, `PL`) and custom forbids via `per-file-ignores` if needed.

3) Quality and types
   - Enable pre-commit with Black, Ruff, mypy. Keep configs in the repo root (`pyproject.toml`).
   - Add type hints for `plugin_sdk` and core public facades. Tests verify SDK signatures.

4) Manifests and schemas
   - Generate and validate JSON Schema for manifests (see ADR-003). Validate all `kira-plugin.json` files in CI.

5) Tests
   - Unit: SDK boundaries and core facades. Integration: real pipelines and adapters (see `tests/integration`).
   - Add an import graph and boundary test.

6) Build/publish
   - For MVP, produce a single app artifact. Prepare for future wheels: keep plugin code isolated under `src/kira_plugin_<name>/` and provide a manifest.

## Risks

- Monorepo growth, longer build times — mitigated via caching, path-based test selection, parallelism, periodic artifact pruning.
- Hidden coupling between plugins — mitigated by import rules, graph tests, and reviews.
- Temporary dependencies leaking into core — mitigated by strict core public facades and private import bans.
- Future migration to multi-repo — eased by plugin folder isolation, stable SDK, and manifests.

## Metrics/DoD

Acceptance criteria (Definition of Done):

- Lint/Type/Test are green:
  - `ruff`, `black --check`, `mypy` pass across the tree.
  - `pytest -q` passes, including integration tests: `tests/integration/test_inbox_pipeline.py`, `tests/integration/test_calendar_sync.py`, `tests/integration/test_telegram_adapter.py`.

- SDK contract:
  - “SDK surface is stable” test: public objects from `plugin_sdk` are enumerated and tested for existence and signatures.

- Manifest validity:
  - CI script validates each `kira-plugin.json` against the shared schema. Violations fail the build.

- Import boundaries:
  - “No cross-plugin imports” test: static AST/import analysis confirms `src/kira/plugins/*` do not import each other nor private core parts. Violations fail tests.

- Plugin structural isolation:
  - Each built-in plugin contains `src/kira_plugin_<name>/` and a minimal test suite. Plugins can be imported independently in tests.

- Packaging readiness:
  - For MVP, “dry” build (e.g., `python -m build`) is not mandatory per plugin, but structure must be compatible with future wheels without API refactors.

Test plan (minimum):

- `tests/unit/test_sdk_surface.py` — sanity checks of `plugin_sdk` public API (presence, signatures, types).
- `tests/unit/test_manifest_validation.py` — validate all `kira-plugin.json` against schema.
- `tests/unit/test_import_boundaries.py` — import graph checks: forbid cross-plugin and private `core` imports.
- Integration tests for pipelines and adapters remain green.

Metrics:

- CI time < N minutes (target), coverage ≥ P% for `plugin_sdk` and core public facades.
- 0 import boundary violations, 0 invalid manifests.

## Consequences

Positive:

- Faster iteration and a single source of truth for contracts and schemas.
- Lower onboarding and local development overhead.
- Clear boundaries reduce architectural erosion.

Negative/Trade-offs:

- Build times will grow with the repository.
- Higher engineering discipline required (linters/tests are mandatory).

Impact:

- On CI/CD: unified matrix and caching, mandatory import and manifest checks.
- On releases: shared root CHANGELOG + notes per affected plugin, unified SDK versioning.

Long-term:

- Transition to publishing plugins as separate wheels or moving them to separate repositories without changing SDK contracts.
