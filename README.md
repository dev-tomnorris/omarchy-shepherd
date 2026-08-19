# Shepherd for Omarchy

**Shepherd** is an Omarchy plugin that monitors and manages Herdr agents across workspaces.

**Display name:** Shepherd  
**Plugin ID:** `dev.tomnorris.shepherd`  
**Tagline:** Keep watch over your Herdr flock.

> **Status:** Phase 0 — Discovery and architecture only. No implementation yet.

## Overview

Shepherd displays live Herdr agents with their `working`, `blocked`, `done`, `idle`, and `unknown` states. It focuses on visibility and control of agent state.

Shepherd is **not** a token-usage widget and will not duplicate Herdr's notification delivery.

## Architecture

Shepherd consists of:
- A QML bar-widget plugin
- A popup panel for detailed agent overview
- A Python helper process connecting to Herdr's Unix socket

## Data flow

1. On startup: `session.snapshot` bootstrap
2. Event subscription: `events.subscribe` for relevant events
3. After reconnecting: Request a fresh `session.snapshot`, then establish a new `events.subscribe` subscription
4. Offline handling: Cache last known agents, show disconnected state

## Phased roadmap

### Phase 0 — Discovery and architecture (you are here)
- [x] Understand Omarchy plugin contract
- [x] Understand Herdr API and data model
- [x] Document data flow and communication patterns
- [x] Rewrite documentation for correctness and brevity

### Phase 1 — Core implementation
- [ ] Helper process connecting to Herdr socket
- [ ] Snapshot bootstrap and event subscription
- [ ] QML widget displaying agent states
- [ ] Socket path resolution (XDG_CONFIG_HOME, HERDR_SESSION, fallback)

### Phase 2 — Panel and focus operations
- [ ] Popup panel showing full agent list
- [ ] Focus agents via `agent.focus`
- [ ] Integration with Herdr focus behavior

### Phase 3 — Robustness
- [ ] Reconnection and re-snapshot
- [ ] Offline handling and caching
- [ ] Error states and user feedback

### Phase 4 — Polish and release
- [ ] Tests and documentation
- [ ] Public release

## Installation

```bash
omarchy plugin add <repository-url>
omarchy plugin enable dev.tomnorris.shepherd
```

## Permissions required

Shepherd requires:
- Read/write access to the local Herdr socket

## Security

- Does not read pane output or prompts
- Does not persist state or send it externally
- The helper receives Herdr snapshot data locally and emits only normalized fields to QML
- Helper stderr contains sanitized diagnostics only, never raw snapshots

## License

MIT

## Author

Tom Norris
