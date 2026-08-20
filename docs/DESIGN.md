# Shepherd Design

## 1. Omarchy manifest and entry-point contract (planned)

Shepherd will declare as a `bar-widget` plugin:

```json
{
  "schemaVersion": 1,
  "id": "dev.tomnorris.shepherd",
  "name": "Shepherd",
  "version": "0.1.0",
  "author": "Tom Norris",
  "description": "Monitor and control Herdr agents",
  "kinds": ["bar-widget"],
  "entryPoints": { "barWidget": "Shepherd.qml" },
  "barWidget": {
    "displayName": "Shepherd",
    "category": "Agents",
    "allowMultiple": false,
    "defaultSection": "right"
  }
}
```

**QML does not exist yet.** `Shepherd.qml`, `Panel.qml`, and `manifest.json` are Phase 2 work.

### Planned plugin lifecycle

1. Shell loads manifest, validates schema
2. Shell creates QML instance
3. QML loads helper process: `python3 <plugin-dir>/helper/shepherd_helper.py`
4. Helper connects to Herdr socket, sends initial state to QML

## 2. Socket resolution

Implemented in `helper/socket_path.py`.

**Resolution order (XDG_CONFIG_HOME respected):**
- `config_home = XDG_CONFIG_HOME when nonempty, otherwise ~/.config`
- `socket_path = HERDR_SOCKET_PATH when nonempty`
- `socket_path = config_home/herdr/sessions/HERDR_SESSION/herdr.sock when HERDR_SESSION nonempty`
- `socket_path = config_home/herdr/herdr.sock (default)`

No TCP/TLS. No `HERDR_SOCKET`. No `~/.local/state/herdr/socket`.

## 3. Helper module layout (implemented)

```
helper/
├── socket_path.py      # Resolve Herdr Unix socket path
├── protocol.py         # JSONL framing and envelope classification
├── rpc.py              # One-shot RPC client (connect → request → response → close)
├── subscribe.py        # Exclusive persistent events.subscribe connection
├── events.py           # Subscription set and pane membership tracking
├── normalize.py        # Snapshot → minimal QML contract
├── ipc.py              # QML ↔ helper JSONL reader/writer
├── runtime.py          # Session loop, debounce, reconnect, thread ownership
└── shepherd_helper.py  # Entry point
```

### Transport model

- **One-shot RPC** (`helper/rpc.py`): each `session.snapshot` and `agent.focus` opens a new Unix socket, sends one request, reads the matching response, then closes. Focus never reuses the subscribe socket.
- **Persistent subscribe** (`helper/subscribe.py`): one exclusive `events.subscribe` connection per session. A single reader thread owns this socket; no concurrent reads.
- **IPC** (`helper/ipc.py`): separate stdin reader thread for QML commands; stdout emits normalized state and command results under a send lock.

### Event strategy

Shepherd uses events as invalidation signals only:

1. On startup: `session.snapshot` bootstrap + `events.subscribe`
2. On each invalidation push: trailing-edge debounce ~100 ms, then fresh `session.snapshot`
3. Normalize snapshot, emit one `state` message to QML
4. Do not apply raw event payloads to cache or forward raw events to QML

**Subscription set** (`helper/events.py`):

- Unscoped lifecycle types (see [HERDR-CONTRACT.md](HERDR-CONTRACT.md) for the full list)
- One `pane.agent_status_changed` subscription per pane in the current snapshot, scoped by `pane_id`

When pane membership changes after a debounced refresh, Shepherd closes the subscribe socket, rebuilds the subscription list, and opens a new `events.subscribe` stream.

**Push envelope shapes:**

- Lifecycle pushes arrive with **snake_case** `event` values (e.g. `workspace_created`, `tab_renamed`)
- Scoped status pushes arrive with **dotted** `event` values (e.g. `pane.agent_status_changed`)

Both are treated as invalidation signals. `events.wait` / `wait_matched` responses are never treated as subscription pushes.

### Reconnect

On session failure: retain last-known normalized state, emit `connection="disconnected"` / `stale=true`, exponential backoff, then fresh `session.snapshot` and new `events.subscribe`.

## 4. Helper/QML boundary (IPC implemented, QML pending)

### Helper responsibilities (implemented)

- Connect to Herdr socket (Python stdlib)
- Bootstrap, subscribe, debounce, normalize, reconnect
- Handle `focus` and `refresh` over JSONL stdin

### QML responsibilities (not yet implemented)

- Display agent states via normalized contract
- Send `focus` and `refresh` requests to helper
- Render panel when triggered

### JSON Lines interface

**QML → Helper:**

```json
{"type":"focus","request_id":"req-1","pane_id":"w1:p1"}
{"type":"refresh","request_id":"req-2"}
```

Both commands require `request_id` as a nonempty string (at least one non-whitespace character). Focus additionally requires `pane_id` as a nonempty string.

**Helper → QML:**

```json
{"type":"state","connection":"connected","stale":false,"agents":[],"counts":{"working":1,"blocked":0,"done":0,"idle":2,"unknown":0,"total":3}}
{"type":"action_result","request_id":"req-1","ok":true}
{"type":"action_result","request_id":"req-1","ok":false,"message":"Unable to focus pane."}
{"type":"error","request_id":"req-2","code":"connection_lost","message":"Herdr socket closed"}
```

Validation errors use `type: error` with codes `invalid_json`, `invalid_message`, `missing_param`, `invalid_param`, or `unknown_command`. See [HERDR-CONTRACT.md](HERDR-CONTRACT.md) for details.

Handler failures (`RpcError` or unexpected exceptions) emit sanitized `action_result` with fixed messages only:

- Focus: `"Unable to focus pane."`
- Refresh: `"Unable to refresh state."`

Backend exception text, tracebacks, socket paths, and raw snapshots are never copied to protocol stdout.

**IPC reader limits:** each JSONL command line is capped at 65,536 bytes. Oversized or unterminated lines emit `invalid_json` / `"Line too long"` and do not hang the reader.

## 5. Minimal normalized agent contract

Implemented in `helper/normalize.py`. Stable fake fixture: `tests/fixtures/normalized_state.json`.

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

**Counts object:**

```json
{"working":1,"blocked":0,"done":0,"idle":1,"unknown":0,"total":2}
```

**Excluded from QML output:** cwd, terminal IDs, session refs, revision fields, layouts, scroll information, raw snapshot fields.

**State response:**

```json
{"type":"state","connection":"connected","stale":false,"agents":[...],"counts":{...}}
{"type":"state","connection":"disconnected","stale":true,"agents":[...],"counts":{...}}
```

## 6. Focus limitation

- **Canonical target:** `pane_id` (always unique)
- **Action:** one-shot `agent.focus` RPC
- **Future:** launch/raise Herdr client (not in Phase 1)

## 7. Connection behavior

- In-memory cache only (no persistence)
- Disconnected: retain last-known agents, `connection="disconnected"`, `stale=true`
- Reconnect: fresh `session.snapshot`, then new subscription

## 8. Current repository layout

```
omarchy-shepherd/
├── helper/                 # Phase 1 Python helper (implemented)
├── tests/                  # Unit, fake-server, and opt-in live integration tests
│   ├── fixtures/
│   │   └── normalized_state.json
│   └── integration/        # Opt-in live Herdr tests (shepherd-it-* sessions)
├── docs/
│   ├── DESIGN.md
│   └── HERDR-CONTRACT.md
└── README.md
```

Phase 2 will add `manifest.json`, `Shepherd.qml`, and `Panel.qml`.

## Design decisions

### 1. Helper process (required)
Separate Python process for persistent subscribe connection and reconnection logic.

### 2. Python stdlib only
No build/install hook; Omarchy only clones/validates.

### 3. One helper per instance
Planned `allowMultiple: false` — one helper, one subscribe reader.

### 4. Normalization in helper
QML receives only the minimal contract.

### 5. Focus via pane_id
`pane_id` is the canonical focus target.

## Remaining work (Phase 2+)

1. QML bar widget, panel, and manifest
2. Safe QML resolution of plugin directory for launching `helper/shepherd_helper.py`
3. Whether focusing a pane can also launch/raise an attached Herdr client
