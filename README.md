# Shepherd for Omarchy

**Shepherd** is an Omarchy shell plugin that monitors Herdr agents and focuses agent panes from the status bar.

**Display name:** Shepherd  
**Plugin ID:** `dev.tomnorris.shepherd`  
**Tagline:** Keep watch over your Herdr flock.

> **Status:** Phase 0 (architecture) and Phase 1 (Python helper) are complete. Phase 2 (QML service, panel, and focus controls) is complete and has been live-tested in Omarchy. Phase 3 / public-release polish is in progress. Shepherd is usable when installed as an Omarchy plugin; it is not a generally released product yet.

## Capabilities

- Monitor Herdr agents (`working`, `blocked`, `done`, `idle`, `unknown`)
- Show connection, stale, and helper-restart states
- Group agents by workspace and tab
- Show status counts and a scrollable agent hierarchy
- Focus a running agent pane via Herdr `agent.focus`
- Recover from helper disconnects and crashes (restart with backoff)

Shepherd is **not** a token-usage widget and does not duplicate Herdr notification delivery.

## Requirements

- Omarchy shell with plugin support (`omarchy plugin …`)
- Herdr **0.8.x** (verified against 0.8.0)
- Python 3 (stdlib only for the helper)
- A Nerd Font for the bar icon glyph

## Install / update / enable

Commands below match the Omarchy CLI help (`omarchy plugin add|update|enable|validate`). Do not `git pull` inside the watched installed plugin directory; use `omarchy plugin update` for git-managed installs.

Add from a git URL (alias: `omarchy plugin install`):

```bash
omarchy plugin add <git-url>
omarchy plugin enable dev.tomnorris.shepherd
```

Optional: add and enable in one step, or place the bar widget:

```bash
omarchy plugin add <git-url> --enable
omarchy plugin enable dev.tomnorris.shepherd --section right
```

Update an installed git-managed copy:

```bash
omarchy plugin update dev.tomnorris.shepherd
```

Validate a plugin folder before install:

```bash
omarchy plugin validate .
```

## Usage

1. Ensure a Herdr 0.8.x session is running for the socket Shepherd resolves (default or `HERDR_SESSION` / `HERDR_SOCKET_PATH`).
2. Open the Shepherd bar widget to view agents and connection state.
3. Click an agent row to request focus on that pane inside the Herdr session.
4. Escape closes the panel; panel switching and scrolling follow normal Omarchy panel behavior.

**Known limitation:** `agent.focus` updates focus inside the persistent Herdr session. If no Herdr client is attached in a visible terminal, the request can succeed without bringing a pane on-screen. For v0.1, launch or attach to Herdr separately (`herdr` / `herdr session attach <name>`). This is not data loss and not a helper failure.

## Development

Default unit and fake-server suite (live Herdr tests skipped):

```bash
python -m unittest discover -s tests -v
```

Opt-in live integration against a disposable `shepherd-it-*` session only (never the default session):

```bash
SHEPHERD_RUN_LIVE_HERDR=1 \
  python -m unittest tests.integration.test_herdr_live -v
```

Plugin structure validation:

```bash
omarchy plugin validate .
```

### Fixture mode (development only)

Set `SHEPHERD_DEV_FIXTURE=1` so the service loads `tests/fixtures/normalized_state.json` through `FixtureBridge` and **does not** start the Python helper or contact Herdr. Leave this unset for normal use.

## Privacy and security

- No prompts, pane output, or transcripts are displayed
- Only normalized agent / workspace / tab / status fields reach QML
- No external telemetry; state is in-memory only
- Focus uses `pane_id` internally; public docs use fake IDs such as `w1:p1`
- Helper stderr stays sanitized (no raw snapshots or exception bodies)

## Roadmap

### Phase 0 — Discovery and architecture ✅
- [x] Omarchy plugin contract and Herdr 0.8.x data model
- [x] Architecture and transport documentation

### Phase 1 — Core helper ✅
- [x] Python stdlib helper (RPC + exclusive subscribe)
- [x] Normalization, debounce, reconnect, focus/refresh IPC
- [x] Unit tests and opt-in disposable live integration

### Phase 2 — QML widget and panel ✅
- [x] Manifest `service` + `bar-widget` entry points
- [x] Singleton service, helper bridge, fixture bridge
- [x] Grouped panel UI and agent-row focus activation
- [x] Live Omarchy install, update, and focus verification

### Phase 3 — Public-release polish (in progress)
- [ ] Packaging / discovery polish for general install
- [ ] Broader end-to-end regression in release environments
- [ ] Documentation and UX finish work for a public release

### Later
- [ ] Launch or attach a visible Herdr client when activating an agent and no client is currently available (requires design for detecting a visible client, selecting the named/default session, using Omarchy’s supported terminal-launch path, avoiding duplicate windows, ordering attach vs pane focus, and safe behavior from panels without a TTY)
- [ ] Agent search / filter
- [ ] Workspace selector
- [ ] Historical status trends

## Contributing

Prefer small, reviewed changes. Keep the helper on Python stdlib, keep QML on the normalized contract, and never target the default Herdr session from automated tests. See [docs/DESIGN.md](docs/DESIGN.md) and [docs/HERDR-CONTRACT.md](docs/HERDR-CONTRACT.md).

## License

MIT

## Author

Tom Norris
