# Herdr Contract

Shepherd targets **Herdr 0.8.0**. This document describes the protocol boundary between Shepherd's helper and Herdr. The QML IPC contract is summarized here; see [DESIGN.md](DESIGN.md) for helper architecture.

## 1. Raw Herdr methods

Shepherd uses these socket RPC methods:

- `session.snapshot` — bootstrap and refresh data
- `events.subscribe` — persistent invalidation stream
- `agent.focus` — focus an agent by pane_id

**Do not use `herdr api subscribe`** — no such command exists.

## 2. Transport envelopes

Herdr traffic on the Unix socket uses newline-delimited JSON. Shepherd distinguishes:

| Envelope | Direction | Purpose |
|----------|-----------|---------|
| One-shot RPC | request/response | `session.snapshot`, `agent.focus` — connect, one request, matching response, close |
| Subscribe ack | response | `result.type == subscription_started` after `events.subscribe` |
| Lifecycle push | server → client | `"event": "workspace_created"` (snake_case) with `"data"` payload |
| Scoped status push | server → client | `"event": "pane.agent_status_changed"` (dotted) with `"data"` payload |
| `events.wait` | RPC response | `result.type == wait_matched` — **Shepherd does not use `events.wait`** |

Lifecycle and scoped pushes are invalidation signals only. Shepherd never applies push payloads to its cache.

## 3. Event strategy

1. On startup: `session.snapshot` + `events.subscribe`
2. On each invalidation push: trailing-edge debounce ~100 ms, then fresh `session.snapshot`
3. Normalize, emit one `state` message to QML
4. Do not forward raw events to QML

No event-order guarantees. No gap detection.

### Subscribed event types

**Unscoped lifecycle** (subscription `type` uses dotted form; push `event` uses snake_case):

- `workspace.created`, `workspace.updated`, `workspace.renamed`, `workspace.moved`, `workspace.reordered`, `workspace.closed`, `workspace.focused`
- `tab.created`, `tab.closed`, `tab.renamed`, `tab.moved`, `tab.focused`
- `pane.created`, `pane.updated`, `pane.closed`, `pane.focused`, `pane.moved`, `pane.exited`, `pane.agent_detected`

**Scoped per pane** (subscription and push both use dotted form):

- `pane.agent_status_changed` with `pane_id`

### Why per-pane status subscriptions

Herdr emits `pane.agent_status_changed` only for subscribed pane IDs. Agent status changes do not reliably arrive via `pane.updated`. Shepherd therefore subscribes once per pane in the current snapshot and rebuilds the subscribe stream when pane membership changes.

## 4. Socket connection

**Resolution order (XDG_CONFIG_HOME respected):**
- `config_home = XDG_CONFIG_HOME when nonempty, otherwise ~/.config`
- `socket_path = HERDR_SOCKET_PATH when nonempty`
- `socket_path = config_home/herdr/sessions/HERDR_SESSION/herdr.sock when HERDR_SESSION nonempty`
- `socket_path = config_home/herdr/herdr.sock (default)`

No TCP/TLS.

## 5. Normalized state contract

Output of `helper/normalize.py`. Stable fake fixture: `tests/fixtures/normalized_state.json`.

**Agent record:**

```json
{
  "pane_id": "w1:p1",
  "name": "dev-agent",
  "status": "working",
  "focused": true,
  "workspace": {"id": "w1", "label": "Development", "number": 1},
  "tab": {"id": "w1:t1", "label": "src", "number": 1}
}
```

**Counts** (all six keys always present):

```json
{"working":1,"blocked":0,"done":0,"idle":1,"unknown":0,"total":2}
```

**State message:**

```json
{"type":"state","connection":"connected","stale":false,"agents":[...],"counts":{...}}
```

Excluded from QML: cwd, terminal IDs, session refs, revision fields, pane output, prompts, raw snapshots.

## 6. QML IPC commands

**Focus:**

```json
{"type":"focus","request_id":"req-1","pane_id":"w1:p1"}
```

**Refresh** (triggers one-shot `session.snapshot`):

```json
{"type":"refresh","request_id":"req-2"}
```

Both require `request_id` as a string with at least one non-whitespace character. Focus requires the same for `pane_id`.

## 7. QML IPC responses

**Success:**

```json
{"type":"action_result","request_id":"req-1","ok":true}
```

**Sanitized handler failure:**

```json
{"type":"action_result","request_id":"req-1","ok":false,"message":"Unable to focus pane."}
{"type":"action_result","request_id":"req-2","ok":false,"message":"Unable to refresh state."}
```

**Validation error:**

```json
{"type":"error","request_id":null,"code":"invalid_json","message":"Malformed JSON"}
{"type":"error","request_id":"req-1","code":"missing_param","message":"Missing pane_id"}
```

Validation codes: `invalid_json`, `invalid_message`, `missing_param`, `invalid_param`, `unknown_command`.

**Connection loss:**

```json
{"type":"error","request_id":"req-1","code":"connection_lost","message":"Herdr socket closed"}
```

IPC input lines are limited to 65,536 bytes.

## 8. Connection behavior

- In-memory cache only
- Disconnected: retain last agents, `connection="disconnected"`, `stale=true`
- Reconnect: fresh `session.snapshot`, then new `events.subscribe`

## 9. Security and privacy

Shepherd must not expose to QML:

- Pane output or prompts
- cwd or path fields from snapshots
- Raw Herdr snapshots or backend JSON
- Backend exception bodies, tracebacks, or socket paths
- User session data from live integration runs

Helper stderr may contain sanitized one-line diagnostics (e.g. `Helper: focus failed`) but never raw snapshots.

## 10. Live integration safety

Opt-in tests under `tests/integration/` run only when `SHEPHERD_RUN_LIVE_HERDR=1`. They:

- Create exactly one disposable `shepherd-it-*` named session
- Reject the default session name and default socket
- Route every mutating Herdr command through `--session <name>`
- Stop, delete the named session, and remove the temp project directory on exit
- Skip entirely (no Herdr commands, no temp dirs) when the env var is unset

## 11. Known limitations

1. **Focus target:** must use `pane_id` (not agent name alone)
2. **Status unknown:** Herdr reports `unknown` when agent state cannot be determined
3. **Agent detection:** some panes have no agent
