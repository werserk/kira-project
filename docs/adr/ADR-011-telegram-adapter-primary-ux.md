---
type: decision
id: ADR-011
title: Telegram adapter as primary UX (capture, confirm, review)
date: 2025-09-19
status: accepted
owners: [kira-adapters]
related: [ADR-001, ADR-002, ADR-003, ADR-004, ADR-005, ADR-015]
drivers: [maximum UX, continuous capture, low friction, observability]
---

## Context

Telegram offers low-friction capture and lightweight review flows. We will use a Telegram adapter as the primary user-facing channel for capturing items (text/files), confirming extractions, and sending daily/weekly briefings.

## Decision

Adopt a Telegram adapter that:

- Listens for updates and publishes normalized events to the bus (ADR-005):
  - `message.received` with payload: `chat_id`, `user_id`, `text`, `attachments`, `message_id`, `timestamp`.
  - `file.dropped` with payload: `file_id`, `mime`, `size`, `chat_id`, `message_id`, `timestamp`.

- Provides inline confirmation flows for uncertain extractions (inline buttons) that call plugin commands via SDK/CLI bridge.

- Sends daily briefings and candidate summaries to configured chats.

## Alternatives

- CLI-only commands — higher friction, lower capture rates. Rejected.
- Other messengers first — increases complexity; Telegram has best API maturity for MVP. Rejected for now.

## Implementation/Migration

1) Modes and configuration
   - Support `bot` (Bot API) initially; consider `userbot` later if needed.
   - Whitelist chats/users; ignore others. Store update offsets for exactly-once processing where possible.

2) Normalization and events
   - Normalize text and files; enrich with correlation IDs; publish to bus.
   - Large files handled via streaming/temp storage with sandbox policies (ADR-004).

3) Confirmations and commands
   - Inline buttons trigger callbacks that map to plugin commands (ADR-002/003). Protect with CSRF-like tokens.

4) Briefings
   - Scheduled daily/weekly briefings via scheduler (ADR-005) pulling from Vault summaries or plugin outputs.

5) Observability and reliability
   - JSONL logs for updates, publishes, confirmations, briefings with correlation IDs (ADR-015).
   - Idempotency keys based on `chat_id:message_id`; dedupe repeated deliveries.

6) Privacy and security
   - Limit logs to metadata; redact PII where possible. Configurable retention; secrets via host (ADR-004).

## Risks

- Privacy/security — mitigate via chat whitelists, minimal logs, and clear data retention settings.
- Rate limits/downtime — exponential backoff and resume from stored offsets.

## Metrics/DoD

Acceptance criteria (Definition of Done):

- Capture quality:
  - ≥85% correct actionable extractions on a sampled set; false positives are correctable via inline confirmation.

- Reliability:
  - No duplicate event emission for the same `chat_id:message_id` under normal operation; successful resume after temporary network failures.

- Briefings:
  - Daily/weekly briefings are delivered on schedule to configured chats; failures are logged with context and retried.

- Observability and privacy:
  - JSONL logs with correlation IDs; PII redaction enabled; configurable chat whitelist enforced.
