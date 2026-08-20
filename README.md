# Shepherd for Omarchy

**Shepherd** is an Omarchy plugin that monitors and manages Herdr agents across workspaces.

**Display name:** Shepherd  
**Plugin ID:** `dev.tomnorris.shepherd`  
**Tagline:** Keep watch over your Herdr flock.

> **Status:** Phase 0 (architecture) and Phase 1 (Python helper) are complete. Phase 2 QML/Omarchy integration is pending. Shepherd is **not installable or usable as an Omarchy plugin yet** — `manifest.json`, `Shepherd.qml`, and `Panel.qml` do not exist.

## Overview

Shepherd displays live Herdr agents with their `working`, `blocked`, `done`, `idle`, and `unknown` states. It focuses on visibility and control of agent state.

Shepherd is **not** a token-usage widget and will not duplicate Herdr's notification delivery.

## What works today

The Phase 1 Python helper (`helper/`) is implemented and covered by unit tests. It has been verified against a disposable Herdr 0.8.0 named session (`shepherd-it-*`) via opt-in live integration tests.

Currently working:

- Unix socket path resolution (`XDG_CONFIG_HOME`, `HERDR_SOCKET_PATH`, `HERDR_SESSION`)
- Snapshot normalization to the minimal QML contract
- `events.subscribe` with pane-scoped `pane.agent_status_changed` subscriptions
- Trailing-edge ~100 ms debounced refresh on invalidation pushes
- JSONL IPC for `focus` and `refresh` commands
- One-shot RPC for `session.snapshot` and `agent.focus`
- Reconnect with exponential backoff, fresh snapshot, and resubscribe
- Sanitized IPC errors and fixed failure messages (no backend exception bodies on stdout)
- Clean shutdown when helper stdin closes

## Architecture

Shepherd will consist of:

- A QML bar-widget plugin *(not yet implemented)*
- A popup panel for detailed agent overview *(not yet implemented)*
- A Python helper process connecting to Herdr's Unix socket *(implemented)*

See [docs/DESIGN.md](docs/DESIGN.md) for module layout and [docs/HERDR-CONTRACT.md](docs/HERDR-CONTRACT.md) for the Herdr protocol boundary.

## Development tests

Run the default unit and fake-server suite (live integration is skipped):

```bash
python -m unittest discover -s tests -v
```

Run opt-in live Herdr integration against a disposable named session only:

```bash
SHEPHERD_RUN_LIVE_HERDR=1 \
  python -m unittest tests.integration.test_herdr_live -v
```

Live integration requires `SHEPHERD_RUN_LIVE_HERDR=1`. It creates and destroys exactly one `shepherd-it-*` session, never touches the default Herdr session, and skips entirely when the variable is unset.

## Phased roadmap

### Phase 0 — Discovery and architecture ✅
- [x] Omarchy plugin contract research
- [x] Herdr 0.8.0 API and data model
- [x] Data flow and communication patterns documented

### Phase 1 — Core helper ✅
- [x] Python helper connecting to Herdr socket
- [x] Snapshot bootstrap, normalization, and event subscription
- [x] Debounced refresh, reconnect, focus/refresh IPC
- [x] Unit tests and opt-in live integration against Herdr 0.8.0

### Phase 2 — QML widget and panel
- [ ] `manifest.json`, `Shepherd.qml`, `Panel.qml`
- [ ] QML ↔ helper JSONL wiring
- [ ] Bar widget and popup panel UI

### Phase 3 — Omarchy installation and usability
- [ ] Install and enable via Omarchy plugin commands
- [ ] End-to-end testing in Omarchy shell

### Later — Optional enhancements
- [ ] Agent search/filter
- [ ] Workspace selector
- [ ] Historical agent status trends

## Installation

Shepherd cannot be installed yet. When Phase 2–3 are complete, installation will look like:

```bash
omarchy plugin add <repository-url>
omarchy plugin enable dev.tomnorris.shepherd
```

## Permissions required

Shepherd will require read/write access to the local Herdr socket.

## Security

- Does not read pane output or prompts
- Does not persist state or send it externally
- The helper receives Herdr snapshot data locally and emits only normalized fields to QML
- Helper stderr contains sanitized diagnostics only, never raw snapshots or backend exception bodies

## License

MIT

## Author

Tom Norris
