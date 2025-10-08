---
type: decision
id: ADR-004
title: Sandbox & Permissions (subprocess + JSON-RPC)
date: 2025-09-19
status: accepted
owners: [kira-core]
related: [ADR-001, ADR-002, ADR-003, ADR-015]
drivers: [security, resilience, isolation, compatibility, observability]
---

## Context

Plugins are potentially untrusted/unstable. We must isolate execution, enforce explicit permissions, and ensure the host remains resilient to plugin faults. The sandbox must be compatible with our SDK contracts (ADR-002), manifest permissions (ADR-003), and logging/trace strategy (ADR-015).

## Decision

Adopt a subprocess-based sandbox as the default execution strategy for plugins, with JSON-RPC 2.0 over stdio for IPC, explicit permission checks at the host boundary, timeouts, watchdog restarts, and OS-backed resource limits where available.

- Execution strategy:
  - Default: `subprocess` per plugin runtime, launched by the host with sanitized environment and working directory.
  - Alternatives: `thread` and `inline` exist for development/testing, but are disabled for production by default.

- IPC protocol:
  - JSON-RPC 2.0 over stdio using Content-Length framing for robustness.
  - All requests/responses include correlation IDs for tracing; logs emitted as structured JSON lines (ADR-015).

- Permission model (from manifest `permissions`):
  - Core set includes: `net`, `secrets.read`, `secrets.write`, `fs.read`, `fs.write`, `events.publish`, `events.subscribe`, `scheduler.create`, `scheduler.cancel`, `calendar.read`, `calendar.write`, `sandbox.execute`.
  - Permissions are enforced at host side via policy checks before fulfilling SDK calls. No direct OS/syscall exposure from plugins.
  - File system access is subject to allowlists (read/write path prefixes) when enabled by `sandbox.fsAccess`.

- Resource controls and reliability:
  - Per-call timeouts (configurable via SDK, see decorators `timeout`) and global watchdog timeouts for idle/crashed processes.
  - Restart policy with jitter and backoff; cap restarts to N attempts per M minutes to avoid thrash.
  - OS-level limits where available: memory (address space/RSS), file descriptors, CPU time quotas.
  - Network disabled by default; enabled only with `net` permission (and possibly adapter-specific allowlists).

- Secrets and configuration:
  - Secrets are brokered by the host; plugins never read host env directly. Access requires `secrets.read`/`secrets.write` and is logged.
  - Plugin config is validated against the manifest `configSchema` and injected via the SDK context.

- Lifecycle:
  - Activation via manifest `entry` (module:function) within the sandboxed process.
  - Graceful shutdown on host signal; forced termination after grace period if unresponsive.
  - Cancellation tokens for long-running RPCs (best-effort in plugin code, hard timeout in host).

## Alternatives

- In-process plugins: simplest, but a plugin crash or leak threatens host stability; complicates permission enforcement. Rejected.
- Separate container/runtime per plugin (e.g., micro-VMs/containers): strongest isolation, but heavy operational overhead for MVP. May be considered later.
- Threads with limited guards: improves context switching cost, but isolation is weak; acceptable only for tests/dev. Rejected for production.

## Implementation/Migration

1) Sandbox launcher and RPC
   - Implement `core/sandbox.py` to spawn plugin subprocesses, set env/working dir, and wire stdio JSON-RPC with Content-Length framing.
   - Define a minimal RPC method set for SDK calls (events, scheduler, kv, secrets), with typed payloads.

2) Policy enforcement
   - Implement `core/policy.py` to map manifest permissions and sandbox options to allow/deny decisions for RPC calls.
   - Deny by default; allow only when the permission is present and optional path/host allowlists match.

3) SDK integration
   - `plugin_sdk/permissions.py`: centralize permission constants, helper checks, and documentation strings.
   - Decorators: `timeout`, `retry`, `permission` annotate call behavior; the host treats them as hints and enforces hard limits.

4) Resource limits and watchdog
   - Add configurable limits (memory, CPU time, fds) using OS facilities where available.
   - Implement per-call and per-process timeouts with a watchdog to terminate hung processes.

5) Observability
   - All sandbox lifecycle events and RPC calls are logged as JSON lines with correlation IDs (ADR-015), including denials and terminations.

6) Safety defaults
   - Default `sandbox.strategy` is `subprocess` with network off, no fs write, minimal fs read; explicit opt-in via manifest is required.

## Risks

- IPC overhead and latency — acceptable tradeoff for safety; mitigate via batching and streaming where appropriate.
- False positives in permission checks — mitigate with clear error messages and developer tooling (`kira plugins validate`).
- OS-level limit portability — provide best-effort implementations and document platform-specific behavior.
- Runaway restart loops — mitigate with capped backoff and circuit breakers.

## Metrics/DoD

Acceptance criteria (Definition of Done):

- Crash isolation:
  - An integration test triggers a plugin crash; the host remains alive, logs the incident, and restarts the plugin per policy.

- Permission enforcement:
  - A test plugin attempts a forbidden action (e.g., `net` without permission or writing outside allowlist); the action is denied and logged with reason and path.
  - FS allowlist respected: reads/writes allowed only within configured prefixes.

- Timeouts and watchdog:
  - A long-running call exceeds the configured timeout and is terminated by the host; the plugin receives cancellation or is killed after grace period.

- Network default-off:
  - A test HTTP request fails without `net` and succeeds when `net` is granted.

- Manifest gating:
  - Plugins lacking required permissions in their manifest cannot perform corresponding SDK calls; loader enforces `sandbox.strategy = subprocess` by default for production.

- Observability:
  - All above outcomes produce JSONL logs with correlation IDs and structured fields compatible with ADR-015 collectors.
