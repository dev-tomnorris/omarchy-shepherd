# Herdr Contract

## 1. Raw Herdr methods

Shepherd uses these raw Herdr methods (authoritative via Herdr 0.8.0 schema):

- `session.snapshot` — Bootstrap data
- `events.subscribe` — Subscribe to events
- `agent.focus` — Focus an agent by pane_id

**Do not use `herdr api subscribe`** — no such command exists.

## 2. Event strategy (v0.1)

Shepherd's helper uses events as invalidation signals only:

1. On startup: Request `session.snapshot` + establish `events.subscribe`
2. On each relevant event: Debounce ~100ms, then request fresh `session.snapshot`
3. Normalize new snapshot, emit one `state` message to QML
4. Do not apply raw event payloads to cache
5. Do not forward raw events to QML

**Event types (dot-notation, per Herdr 0.8.0 schema):**
- `workspace.created`, `workspace.updated`, `workspace.renamed`, `workspace.closed`, `workspace.focused`
- `tab.created`, `tab.closed`, `tab.renamed`, `tab.moved`, `tab.focused`
- `pane.created`, `pane.updated`, `pane.closed`, `pane.focused`, `pane.moved`, `pane.exited`, `pane.agent_detected`, `pane.agent_status_changed`

No event-order guarantees. No gap detection. No dependency on event payload shape beyond the dotted event type.

## 3. Socket connection

Herdr uses Unix domain socket on Omarchy/Linux.

**Resolution order (XDG_CONFIG_HOME respected):**
- `config_home = XDG_CONFIG_HOME when nonempty, otherwise ~/.config`
- `socket_path = HERDR_SOCKET_PATH when nonempty`
- `socket_path = config_home/herdr/sessions/HERDR_SESSION/herdr.sock when HERDR_SESSION nonempty`
- `socket_path = config_home/herdr/herdr.sock (default)`

No TCP/TLS. No `HERDR_SOCKET`. No `~/.local/state/herdr/socket`.

Python stdlib example:
```python
import socket
import os

config_home = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
socket_path = os.environ.get("HERDR_SOCKET_PATH")

if not socket_path:
    if os.environ.get("HERDR_SESSION"):
        socket_path = os.path.join(config_home, "herdr", "sessions", os.environ.get("HERDR_SESSION"), "herdr.sock")
    else:
        socket_path = os.path.join(config_home, "herdr", "herdr.sock")

sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect(socket_path)
```

## 4. Minimal normalized agent contract

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

**Counts:**
```json
{"working":1,"blocked":0,"done":0,"idle":2,"unknown":0,"total":3}
```

No cwd, terminal IDs, session refs, or revision fields.

## 5. Focus operation

- Helper uses raw `agent.focus` over existing socket
- `herdr agent focus <pane_id>` is a human debugging example only
- QML receives `action_result` (success/failure) or sanitized `error` messages via `request_id`

## 6. Connection behavior

- Cache state in memory only (no persistence)
- Disconnected: retain last agents, `connection="disconnected"`, `stale=true`
- Reconnect: Fresh `session.snapshot`, then new subscription

## 7. Security

- Shepherd does not read pane output or prompts
- No state is persisted or sent externally
- The helper receives Herdr snapshot data locally but emits only normalized fields to QML
- `pane_id` safe to log (opaque identifier)
- `cwd` may contain sensitive paths (redact in logs)
- Helper stderr contains sanitized diagnostics only, never raw snapshots

## 8. Sample data (fake values only)

### Example snapshot (no real data)

```json
{
  "agents": [
    {
      "agent": "opencode",
      "agent_status": "working",
      "pane_id": "w1:p1",
      "tab_id": "w1:t1",
      "workspace_id": "w1"
    }
  ]
}
```

## 9. Known limitations

1. **Agent focus target:** Must use `pane_id` (not `agent_name` alone)
2. **Status unknown:** Herdr reports `unknown` when agent state cannot be determined
3. **Agent detection:** Some panes have no agent (`agent: null`)
