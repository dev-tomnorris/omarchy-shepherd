# Herdr Contract

Shepherd targets **Herdr 0.8.x** (verified on **0.8.0**). This document is the helper↔Herdr and QML↔helper contract. UI layout and Omarchy install steps belong in [README.md](../README.md) and [DESIGN.md](DESIGN.md).

## 1. Socket resolution

Implemented in `helper/socket_path.py`:

1. `HERDR_SOCKET_PATH` when nonempty
2. else `config_home/herdr/sessions/<HERDR_SESSION>/herdr.sock` when `HERDR_SESSION` nonempty
3. else `config_home/herdr/herdr.sock`

Production (`environ is None`) uses nonempty `XDG_CONFIG_HOME`, otherwise `expanduser("~/.config")`.

Injected mappings (tests / `build_helper(environ=…)`) use only that mapping: nonempty `XDG_CONFIG_HOME`, else nonempty `HOME` + `/.config`, else unavailable (raises a fixed `ValueError` when a session/default path is required). No process `HOME` / `expanduser` fallback on the injected path. No TCP/TLS. No `HERDR_SOCKET`.

### Environment ownership

`helper/shepherd_helper.build_helper()` snapshots the process environment (or an injected mapping) **once**, then derives **both** `socket_path` and `presentation` from that snapshot. `Helper` requires both keyword arguments; callers must not pass them into `build_helper`. This prevents ambient-environment mismatch between the socket opened and the descriptor published.

## 2. Transport ownership

| Channel | Owner | Methods / role |
|---------|-------|----------------|
| One-shot RPC | `helper/rpc.py` | Connect → one request → matching response → close. Used for `session.snapshot` and `agent.focus`. Never shares the subscribe socket. |
| Exclusive subscribe | `helper/subscribe.py` | One persistent `events.subscribe` connection and one reader thread. No concurrent reads; no second request on that socket. |

Do **not** use a CLI `herdr api subscribe` path — Shepherd speaks the Unix-socket JSONL API directly.

The Python helper **never** launches a terminal, attaches a client, or invokes Omarchy launchers. Presentation launch is QML-only (`Util.shellQuote` + `bar.run`).

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

`Helper.publish_state` fingerprints normalized agents/counts, `connection`/`stale`, and the sanitized `presentation` descriptor. Identical fingerprints are suppressed. Connection/stale transitions publish even when agents are unchanged. Presentation remains stable across disconnect/reconnect for a given helper process.

Top-level `state` keys are exactly:

`type`, `connection`, `stale`, `agents`, `counts`, `presentation`

## 5. Normalized agent fields

Output of `helper/normalize.py`. Fixture: `tests/fixtures/normalized_state.json`.

Agent keys only: `pane_id`, `name`, `status`, `focused`, `workspace{id,label,number}`, `tab{id,label,number}`.

Counts always include: `working`, `blocked`, `done`, `idle`, `unknown`, `total`.

**Excluded from QML agents/counts:** pane output, prompts, cwd, terminal IDs, session refs, revisions, layouts, scroll info, raw snapshot blobs.

## 6. Presentation descriptor

### Schema

`presentation` keys are exactly:

`kind`, `supported`, `app_id`, `argv`

| Shape | Example |
|-------|---------|
| Default | `{"kind":"default","supported":true,"app_id":"org.omarchy.herdr","argv":["herdr"]}` |
| Named | `{"kind":"named","supported":true,"app_id":"org.omarchy.herdr.session-<12 hex>","argv":["herdr","--session","<name>"]}` |
| Unsupported override | `{"kind":"socket_override","supported":false,"app_id":"","argv":[]}` |

Named app IDs use SHA-256 over the UTF-8 session name; take the first 12 hex characters; prefix `org.omarchy.herdr.session-`.

### Classification precedence (`build_presentation_descriptor`)

1. Nonempty `HERDR_SOCKET_PATH` → classify override (may resolve to default, named, or unsupported)
2. Else nonempty `HERDR_SESSION` → named
3. Else → default

Conventional override classification (absolute config home required):

- Path equals `<config_home>/herdr/herdr.sock` → default
- Path equals `<config_home>/herdr/sessions/<safe-name>/herdr.sock` → named for that session
- Anything else (relative, traversal, arbitrary absolute, unresolvable home, etc.) → unsupported

### Sanitization

Python (`sanitize_presentation_descriptor`) and QML (`Presentation.sanitize`) both:

- Require exact key sets and string `argv` elements
- Require boolean singletons for `supported` (not `0`/`1`)
- Copy `argv` into a new list / object
- Downgrade malformed or inconsistent input to unsupported
- Bind named `app_id` to the session name in Python (QML checks format + argv shape)

**Deliberately excluded from presentation:** socket paths, config homes, hostnames, cwd, raw env dumps, private helper fields, extra dictionary keys.

### Full state example (fake IDs only)

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
  "counts": {"working": 1, "blocked": 0, "done": 0, "idle": 0, "unknown": 0, "total": 1},
  "presentation": {
    "kind": "default",
    "supported": true,
    "app_id": "org.omarchy.herdr",
    "argv": ["herdr"]
  }
}
```

## 7. QML ↔ helper IPC

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

Handler failures never copy backend exception text, tracebacks, socket paths, or raw snapshots to stdout. Fixed failure messages only for focus/refresh `action_result` failures. Action/error messages never include a presentation descriptor.

QML correlates `request_id` for pending focus/refresh. Duplicate focus while `pendingFocus` is set is rejected by the bridge.

## 8. Focus success and presentation correlation

Helper focus success is a normal `action_result` with `ok: true` for the pending focus `request_id`. That does **not** launch a terminal by itself.

`HelperBridge` then publishes a property (not a custom signal):

```text
lastFocusSuccess = { requestId: <string>, paneId: <trimmed string> }
```

Panel rules:

- Store `expectedFocusRequestId` from the `shepherd.focus()` return value when the Panel initiates focus
- On `lastFocusSuccess` change, launch only if `requestId` equals that expectation
- Ignore records that already existed at Panel bind / service swap (`ignoredFocusSuccess`)
- Consume the expectation **before** calling presentation
- Fixture mode, failures, errors, disconnect/crash, and unmatched/duplicate completions must not launch

Refresh completions never set `lastFocusSuccess`.

## 9. Focus semantics (`agent.focus`)

Helper issues one-shot RPC `agent.focus` with an `AgentTarget` (Shepherd always passes `pane_id`).

**Does:**

- Change the focused pane inside the persistent Herdr **session**
- Can mark agent presentation state as seen (Herdr-side), when the server accepts the request

**Presentation (QML, after correlated success):**

- For supported descriptors, Omarchy `omarchy-launch-or-focus-tui` opens or raises a dedicated client window keyed by Shepherd’s app ID (not by introspecting the process inside the terminal)
- Detaching or closing that window does not stop the Herdr server or destroy agents
- A detached-but-still-open managed window is raised as-is (no automatic reattach); closing it restores launch/attach on the next focus

**Unsupported socket overrides:**

- Focus still applies inside the session
- No automatic client launch; user opens Herdr manually

## 10. Disconnect / stale / reconnect

- In-memory cache only
- On session failure: keep last agents, publish `connection="disconnected"`, `stale=true`, same process presentation descriptor
- Backoff (exponential, capped), then fresh `session.snapshot` and a new `events.subscribe`
- Helper stdin EOF stops the helper cleanly (QML Process close)

## 11. Live integration safety

Opt-in only when `SHEPHERD_RUN_LIVE_HERDR=1` (`tests/integration/`). Guards:

- Create exactly one disposable `shepherd-it-*` named session
- Reject session name `default` and the default socket path
- Route mutating CLI through `herdr --session <name> …`
- Stop/delete the named session and remove the temp project on exit
- Skip entirely (no Herdr commands) when the env var is unset

## 12. Other known limitations

1. Focus target must be `pane_id` (not agent name alone) in Shepherd’s IPC
2. Herdr may report `unknown` status when classification is uncertain
3. Some panes have no agent and never appear in normalized output
4. A Herdr terminal launched without Shepherd’s dedicated app ID is outside Omarchy’s managed-window reuse for Shepherd
5. A detached-but-still-open Shepherd-managed terminal is raised by app ID without reattach; close that window to restore automatic launch/attach
6. Herdr panes may lack compositor session variables; launch ownership stays with Omarchy `bar.run` in the graphical shell
