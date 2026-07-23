# Phase 3: Feishu card-first resource operations

## Goal

Make Feishu the primary channel for common resource operations. Deterministic actions
use platform-rendered cards; LLM output can select data but cannot construct actions or
bypass platform authorization.

## Delivered tracer

- `/help` returns a role-aware operation home card.
- `/machines` and `/machines free` return machine cards with availability and occupier.
- Free machines expose a deterministic occupy action.
- `/my-leases` returns lease cards with extend and release actions.
- Occupy, extend, and release require an explicit confirmation card.
- Every confirmed action reuses the existing lease module for ownership, availability,
  pool status, and lease-state validation.
- Feishu card callbacks return updated result cards.
- Card action event IDs are persisted and deduplicated.
- LLM `search_machines` tool results are rendered as platform-owned machine cards.

## Safety rules

- Card payloads contain identifiers and requested parameters, never credentials.
- The current Feishu identity is resolved to a platform user before every action.
- Buttons do not grant authority; the lease module rechecks authorization and state.
- LLM responses cannot directly execute occupy, extend, release, or force release.
- A repeated Feishu callback event returns the stored result without repeating the write.

## Follow-up slices

- Machine detail card with connectivity, pool, tags, and role-aware credential access.
- Connectivity test result card and credential-view audit path for single chats.
- ADMIN/TSE cards for maintenance state, force release, and resource-pool operations.
- Pagination and filters for larger machine inventories.
- Persisted LLM operation drafts for natural-language write requests.
- Group-chat policy: read-only cards in groups; writes and credentials in single chats.
