# Herdr Contract

Shepherd targets **Herdr 0.8.x** (verified on **0.8.0**). This document is the helper↔Herdr and QML↔helper contract. UI layout and Omarchy install steps belong in [README.md](../README.md) and [DESIGN.md](DESIGN.md).

## 1. Socket resolution

Implemented in `helper/socket_path.py` (`XDG_CONFIG_HOME` respected):

1. `HERDR_SOCKET_PATH` when nonempty
2. else `config_home/herdr/sessions/<HERDR_SESSION>/herdr.sock` when `HERDR_SESSION` nonempty
3. else `config_home/herdr/herdr.sock`

`config_home` is nonempty `XDG_CONFIG_HOME`, otherwise `~/.config`. No TCP/TLS. No `HERDR_SOCKET`.

## 2. Transport ownership

| Channel | Owner | Methods / role |
|---------|-------|----------------|
| One-shot RPC | `helper/rpc.py` | Connect → one request → matching response → close. Used for `session.snapshot` and `agent.focus`. Never shares the subscribe socket. |
| Exclusive subscribe | `helper/subscribe.py` | One persistent `events.subscribe` connection and one reader thread. No concurrent reads; no second request on that socket. |

Do **not** use a CLI `herdr api subscribe` path — Shepherd speaks the Unix-socket JSONL API directly.

## 3. Invalidation and refresh

On startup: `session.snapshot`, then `events.subscribe`.

On each invalidation push: trailing-edge debounce (~100 ms), then a fresh `session.snapshot`. Pushes are never applied to cache and never forwarded to QML.

**Unscoped lifecycle subscriptions** (subscribe `type` dotted; push `event` often snake_case):

- `workspace.created|updated|renamed|moved|reordered|closed|focused`
- `tab.created|closed|renamed|moved|focused`
- `pane.created|updated|closed|focused|moved|exited|agent_detected`

**Per-pane status:** one `pane.agent_status_changed` subscription per snapshot `pane_id`. Status changes are not reliable via `pane.updated` alone. When pane membership changes after refresh, Shepherd closes the subscribe socket and opens a new stream.

`events.wait` / `wait_matched` responses are never treated as subscription pushes. No event-order or gap guarantees.

## 4. State publication

`Helper.publish_state` fingerprints normalized agents/counts plus `connection`/`stale`. Identical fingerprints are suppressed. Connection/stale transitions publish even when agents are unchanged.

## 5. Normalized state fields

Output of `helper/normalize.py`. Fixture: `tests/fixtures/normalized_state.json`.

Agent keys only: `pane_id`, `name`, `status`, `focused`, `workspace{id,label,number}`, `tab{id,label,number}`.

Counts always include: `working`, `blocked`, `done`, `idle`, `unknown`, `total`.

**Excluded from QML:** pane output, prompts, cwd, terminal IDs, session refs, revisions, layouts, scroll info, raw snapshot blobs.

Example (fake IDs only):

```json
{
  "type": "state",
  "connection": "connected",
  "stale": false,
  "agents": [{
    "pane_id": "w1:p1",
    "name": "dev-agent",
    "status": "working",
    "focused": true,
    "workspace": {"id": "w1", "label": "Development", "number": 1},
    "tab": {"id": "w1:t1", "label": "src", "number": 1}
  }],
  "counts": {"working": 1, "blocked": 0, "done": 0, "idle": 0, "unknown": 0, "total": 1}
}
```

## 6. QML ↔ helper IPC

Commands (stdin JSONL). `request_id` must be a nonempty string. Focus also requires nonempty string `pane_id`:

```json
{"type":"focus","request_id":"req-1","pane_id":"w1:p1"}
{"type":"refresh","request_id":"req-2"}
```

Each input line is capped at **65,536** bytes. Oversized/unterminated lines yield `invalid_json` / `Line too long` without hanging the reader.

Responses:

```json
{"type":"action_result","request_id":"req-1","ok":true}
{"type":"action_result","request_id":"req-1","ok":false,"message":"Unable to focus pane."}
{"type":"action_result","request_id":"req-2","ok":false,"message":"Unable to refresh state."}
{"type":"error","request_id":null,"code":"invalid_json","message":"Malformed JSON"}
{"type":"error","request_id":"req-1","code":"connection_lost","message":"Herdr socket closed"}
```

Validation codes: `invalid_json`, `invalid_message`, `missing_param`, `invalid_param`, `unknown_command`.

Handler failures never copy backend exception text, tracebacks, socket paths, or raw snapshots to stdout. Fixed failure messages only for focus/refresh `action_result` failures.

QML correlates `request_id` for pending focus/refresh. Duplicate focus while `pendingFocus` is set is rejected by the bridge.

## 7. Focus semantics (`agent.focus`)

Helper issues one-shot RPC `agent.focus` with an `AgentTarget` (Shepherd always passes `pane_id`).

**Does:**

- Change the focused pane inside the persistent Herdr **session**
- Can mark agent presentation state as seen (Herdr-side), when the server accepts the request

**Does not guarantee:**

- Opening a terminal
- Attaching a Herdr client
- Raising an existing client window
- That a detached user will see the pane

If no visible client is attached, a successful focus can still leave the user without an on-screen pane. See the detached-client limitation in [DESIGN.md](DESIGN.md).

## 8. Disconnect / stale / reconnect

- In-memory cache only
- On session failure: keep last agents, publish `connection="disconnected"`, `stale=true`
- Backoff (exponential, capped), then fresh `session.snapshot` and a new `events.subscribe`
- Helper stdin EOF stops the helper cleanly (QML Process close)

## 9. Live integration safety

Opt-in only when `SHEPHERD_RUN_LIVE_HERDR=1` (`tests/integration/`). Guards:

- Create exactly one disposable `shepherd-it-*` named session
- Reject session name `default` and the default socket path
- Route mutating CLI through `herdr --session <name> …`
- Stop/delete the named session and remove the temp project on exit
- Skip entirely (no Herdr commands) when the env var is unset

## 10. Other known limitations

1. Focus target must be `pane_id` (not agent name alone) in Shepherd’s IPC
2. Herdr may report `unknown` status when classification is uncertain
3. Some panes have no agent and never appear in normalized output
