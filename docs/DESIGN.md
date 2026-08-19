# Shepherd Design

## 1. Omarchy manifest and entry-point contract

Shepherd declares as a `bar-widget` plugin:

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

### Entry point contract

- `Shepherd.qml` is the main QML component (bar widget)
- `Panel.qml` is the popup panel
- Manifest declares `barWidget` entry point
- Shell instantiates plugin and manages lifecycle

### Plugin lifecycle

1. Shell loads manifest, validates schema
2. Shell creates QML instance
3. QML loads helper process: `python3 <plugin-dir>/helper/shepherd_helper.py`
4. Helper connects to Herdr socket, sends initial state to QML

## 2. Socket resolution

Herdr uses a Unix domain socket.

**Resolution order (XDG_CONFIG_HOME respected):**
- `config_home = XDG_CONFIG_HOME when nonempty, otherwise ~/.config`
- `socket_path = HERDR_SOCKET_PATH when nonempty`
- `socket_path = config_home/herdr/sessions/HERDR_SESSION/herdr.sock when HERDR_SESSION nonempty`
- `socket_path = config_home/herdr/herdr.sock (default)`

No TCP/TLS. No `HERDR_SOCKET`. No `~/.local/state/herdr/socket`.

## 3. Raw Herdr methods (authoritative via Herdr 0.8.0 schema)

Core raw methods Shepherd uses:

- `session.snapshot` — Bootstrap data
- `events.subscribe` — Subscribe to events
- `agent.focus` — Focus an agent by pane_id

**Do not use `herdr api subscribe`** — there is no such command.

## 4. Event strategy (v0.1)

Shepherd's helper uses events as invalidation signals only:

1. On startup: Request `session.snapshot` + establish `events.subscribe`
2. On each relevant event: Debounce ~100ms, then request fresh `session.snapshot`
3. Normalize new snapshot, emit one `state` message to QML
4. Do not apply raw event payloads to cache
5. Do not forward raw events to QML

**Rationale:** This trades minor latency for simpler and more reliable state handling.

**Event types (dot-notation, per Herdr 0.8.0 schema):**
- `workspace.created`, `workspace.updated`, `workspace.renamed`, `workspace.closed`, `workspace.focused`
- `tab.created`, `tab.closed`, `tab.renamed`, `tab.moved`, `tab.focused`
- `pane.created`, `pane.updated`, `pane.closed`, `pane.focused`, `pane.moved`, `pane.exited`, `pane.agent_detected`, `pane.agent_status_changed`

No event-order guarantees. No gap detection.

## 5. Helper/QML boundary

### Helper responsibilities

- Connect to Herdr socket (Python stdlib socket + JSON)
- `session.snapshot` bootstrap
- Subscribe only to relevant event types; treat every received event as an invalidation signal
- Reconnection with exponential backoff
- After debounce: Request fresh `session.snapshot`, normalize, emit state to QML
- Handle `agent.focus` requests over existing socket

### QML responsibilities

- Display agent states via normalized contract
- Send `focus` and `refresh` requests to helper
- Render panel when triggered

### Interface: JSON Lines (newline-delimited)

**QML → Helper:**
```json
{"type":"focus","request_id":"req-1","pane_id":"w1:p1"}
{"type":"refresh","request_id":"req-2"}
```

**Helper → QML:**
```json
{"type":"state","connection":"connected","stale":false,"agents":[],"counts":{"working":1,"blocked":0,"done":0,"idle":2,"unknown":0,"total":3}}
{"type":"action_result","request_id":"req-1","ok":true}
{"type":"error","request_id":"req-2","code":"connection_lost","message":"Herdr socket closed"}
```

### Helper implementation (v0.1 decision)

- Language: Python 3 standard library (no third-party dependencies)
- File: `helper/shepherd_helper.py`
- One helper per plugin instance (manifest `allowMultiple: false`)
- No build/installation hook needed (Omarchy only clones/validates)

**Conceptual invocation:**
```bash
python3 <plugin-directory>/helper/shepherd_helper.py
```

**Exact QML resolution of `<plugin-directory>` is a Phase 1 spike:**

- Omarchy plugin manifests are loaded from `~/.config/omarchy/plugins/<id>/`
- `Qt.resolvedUrl()` explicitly described as a Phase 1 candidate to verify
- Exact method verified in Phase 1

## 6. Minimal normalized agent contract

**Agent record:**
```json
{
  "pane_id": "w1:p1",
  "name": "opencode",
  "status": "working",
  "focused": true,
  "workspace": {"id": "w1", "label": "Project", "number": 1},
  "tab": {"id": "w1:t1", "label": "1", "number": 1}
}
```

**Counts object:**
```json
{"working":1,"blocked":0,"done":0,"idle":2,"unknown":0,"total":3}
```

**Do not include:**
- cwd or foreground_cwd
- terminal IDs or terminal titles
- session references
- raw revision/state sequence fields
- duplicate agent_id/pane_id fields
- layouts or scroll information

**State response:**
```json
{"type":"state","connection":"connected","stale":false,"agents":[...],"counts":{...}}
{"type":"state","connection":"disconnected","stale":true,"agents":[...],"counts":{...}}
```

## 7. Focus limitation

- **Canonical target:** `pane_id` (always unique)
- **Action:** `agent.focus` changes Herdr's selected pane
- **Phase 2 spike:** Launch/raise Herdr client (not in v0.1)

## 8. Connection behavior

- Cache state in memory only (no persistence)
- Disconnected: retain last-known agents, `connection="disconnected"`, `stale=true`
- Reconnect: Fresh `session.snapshot`, then new subscription
- No unsupported event ordering or gap detection

## 9. File tree

```
omarchy-shepherd/
├── Shepherd.qml              # Bar widget (entry point)
├── Panel.qml                 # Popup panel
├── helper/
│   └── shepherd_helper.py    # Python 3 helper (stdlib only)
├── manifest.json
└── README.md
```

## Design decisions

### 1. Helper process (required)
- **Decision:** Separate Python process for socket connection
- **Rationale:** Events require persistent connection; reconnection logic complex

### 2. Python stdlib (not Rust/Go)
- **Decision:** Python standard library only
- **Rationale:** No build/install hook; Omarchy only clones/validates

### 3. One helper per instance
- **Decision:** `allowMultiple: false`, one helper per plugin
- **Rationale:** Simpler state management, no shared socket

### 4. Normalization in helper
- **Decision:** Helper normalizes to minimal contract
- **Rationale:** QML only receives clean data, no Herdr internals

### 5. Focus via pane_id
- **Decision:** `pane_id` is canonical focus target
- **Rationale:** pane_id guaranteed unique; agent names may collide

## Focus operation

- Helper uses raw `agent.focus` over existing socket
- `herdr agent focus <pane_id>` is a human debugging example only
- QML receives `action_result` (success/failure) or sanitized `error` messages

## Remaining uncertainties

1. Exact safe QML resolution of plugin directory for launching `helper/shepherd_helper.py`
2. Whether focusing a pane can also launch/raise an attached Herdr client

## Future enhancements

- [ ] Agent search/filter
- [ ] Workspace selector
- [ ] Historical agent status (trend)
