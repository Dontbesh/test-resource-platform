# Phase 3 LLM Assistant Tracer Plan

Status: active

## Goal

Deliver the first production-shaped LLM assistant path shared by Web and Feishu:
deterministic commands remain first, unmatched natural-language requests use an
OpenAI-compatible model with tool calling, and the first tool performs an
authorized read-only machine search.

## Scope

- Automatically restore saved Feishu WebSocket workers when the API starts and
  stop them when the API shuts down.
- Automatically start a newly saved Feishu application.
- Remove manual worker start/stop controls from the Web page while retaining
  read-only connection state and errors.
- Configure one OpenAI-compatible model through server environment variables.
- Add one authenticated assistant interface shared by Web and Feishu.
- Add a white-listed `search_machines` read tool using current inventory fields.
- Route Feishu text that misses deterministic commands into the shared assistant.
- Provide a minimal Web assistant view for end-to-end verification.
- Fall back cleanly when the LLM is disabled, misconfigured, unavailable, or
  returns invalid tool arguments.

## Non-goals

- No model-generated or model-executed SQL.
- No direct database access from the model or channel adapter.
- No lease, release, or extension write tools in this tracer.
- No operation draft persistence in this tracer.
- No hardware schema expansion for CPU vendor, NIC speed, or disk media.
- No multi-model routing, vector database, or long-term conversation storage.

## Confirmed decisions

- Deterministic commands and cards run before the LLM.
- The model must support native tool/function calling.
- Tool definitions use JSON Schema and platform-owned validation.
- The assistant invokes existing domain modules; it does not duplicate their rules.
- The API key is supplied through server configuration and is never returned to clients.
- A failed Feishu auto-connect must not prevent the API from serving Web requests.
- Worker status remains visible for diagnosis even though manual controls are removed.

## Public behavior and acceptance scenarios

1. Starting the API restores every saved Feishu app worker when credential
   encryption is configured; shutdown stops all workers.
2. Saving a new Feishu app starts its worker without a manual Web action.
3. An authenticated Web user can send free text to the assistant interface.
4. The model can call `search_machines` with supported filters and receive only
   platform-produced, non-secret machine data.
5. The assistant returns the model's final answer after feeding the tool result
   back to the model.
6. A Feishu message that matches a deterministic command keeps the existing path;
   unmatched free text uses the same assistant interface as Web.
7. Missing configuration, network failure, invalid tool names, and invalid tool
   arguments return a stable error without breaking deterministic commands.

## Task checklist

- [x] Task 1: Feishu worker startup/shutdown restoration and read-only Web status.
- [x] Task 2: LLM settings and OpenAI-compatible tool-calling adapter.
- [x] Task 3: Shared assistant interface and `search_machines` tool.
- [x] Task 4: Authenticated Web assistant tracer.
- [x] Task 5: Feishu unmatched-text routing and regression coverage.
- [ ] Task 6: Documentation, full verification, and audit preparation.

## Verification

From `test-resource-platform/backend`:

```text
pytest
ruff check .
```

From `test-resource-platform/frontend`:

```text
npm run build
```

Acceptance verification on the server:

```text
docker-compose up --build -d
docker-compose logs --tail=200 api
```

- The saved Feishu application connects without pressing a start button.
- `/machines free` still follows the deterministic command path.
- A natural-language machine query causes a model tool call and returns a final answer.
- Removing or invalidating `LLM_API_KEY` produces a controlled assistant error while
  ordinary Web inventory and Feishu commands remain usable.

## Progress and discoveries

- Existing Feishu binding, deterministic commands, cards, and lease modules are reusable.
- The current worker manager is process-local and currently starts only through a manual API.
- The current machine model supports pool, type, architecture, OS, tags, administrative,
  connectivity, and occupancy data; detailed NIC and disk search needs a later schema change.
- Existing unrelated weekly report, learning document, and `cc-connect` working-tree changes
  must remain untouched.
- Local verification on 2026-07-23: backend `pytest` 69 passed, Ruff passed, and the
  frontend production build passed with only the existing chunk-size warning.
- Real model and Feishu auto-connect acceptance remain to be run on the Linux server after
  `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL` are configured.
