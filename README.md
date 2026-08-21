# Shepherd for Omarchy

**Shepherd** is an Omarchy shell plugin that monitors Herdr agents, focuses agent panes from the status bar, and opens or raises a Shepherd-managed Herdr client after a successful focus.

**Display name:** Shepherd  
**Plugin ID:** `dev.tomnorris.shepherd`  
**Tagline:** Keep watch over your Herdr flock.

> **Status:** Phases 0–2 and client-attach presentation are implemented on `feat/herdr-client-attach` and have been live-tested in Omarchy. Phase 3 / public-release polish remains. Shepherd is usable when installed as an Omarchy plugin; it is not a generally released product yet.

## Capabilities

- Monitor Herdr agents (`working`, `blocked`, `done`, `idle`, `unknown`)
- Show connection, stale, and helper-restart states
- Group agents by workspace and tab
- Show status counts and a scrollable agent hierarchy
- Focus a running agent pane via Herdr `agent.focus`
- After a correlated focus success, open or raise a dedicated Herdr client via Omarchy (`omarchy-launch-or-focus-tui`)
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
3. Click an agent row to focus that pane and, when presentation is supported, open or raise Shepherd’s managed Herdr client.
4. Escape closes the panel; panel switching and scrolling follow normal Omarchy panel behavior.

### Presentation behavior

- **Default session** and **conventional named sessions** (`HERDR_SESSION`, or a conventional sessions socket path) are supported. Shepherd launches with a dedicated app ID (`org.omarchy.herdr` or `org.omarchy.herdr.session-<12 hex chars>`) so Omarchy can reuse one managed window.
- **Arbitrary `HERDR_SOCKET_PATH` overrides** still focus the pane inside the session, but presentation is unsupported: Shepherd shows `Open Herdr manually for this session.` and does not launch a client.
- Deduplication is by **managed terminal app ID**, not by inspecting which process is running inside the terminal. A **manually launched** Herdr terminal without Shepherd’s app ID is outside that reuse set (the first Shepherd presentation may open one additional managed client).
- **Detaching** from Herdr or **closing** the visible managed client does **not** stop the persistent Herdr server or agents.
- If a Shepherd-managed terminal is **detached but still open**, `omarchy-launch-or-focus-tui` still finds that app-ID window and raises its ordinary shell. It cannot tell that the `herdr` client inside has exited, so it does not automatically reattach. **Close** that detached managed window; the next Shepherd focus creates a fresh managed terminal and attaches to the persistent session.
- After a successful presentation launch, agent rows stay non-activatable for **three seconds** (cooldown). That cooldown is separate from the in-flight `Focusing…` state.

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

Set `SHEPHERD_DEV_FIXTURE=1` so the service loads `tests/fixtures/normalized_state.json` through `FixtureBridge` and **does not** start the Python helper, contact Herdr, or present a terminal. Leave this unset for normal use.

## Privacy and security

- No prompts, pane output, or transcripts are displayed
- Only normalized agent / workspace / tab / status fields, plus a sanitized presentation descriptor, reach QML
- Presentation never publishes socket paths, cwd, hostnames, or raw environment values
- Terminal launch runs only through Omarchy `bar.run` with `Util.shellQuote` on every token — not from the Python helper
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

### Client attach / presentation ✅
- [x] Presentation descriptors (default, named, unsupported override)
- [x] State-envelope publication and QML trust-boundary sanitize
- [x] Correlated focus success → Omarchy launch-or-focus for a dedicated Herdr client
- [x] Managed-window reuse, cooldown, and fail-closed unsupported paths

### Phase 3 — Public-release polish (in progress)
- [ ] Packaging / discovery polish for general install
- [ ] Broader end-to-end regression in release environments
- [ ] Documentation and UX finish work for a public release

### Later
- [ ] Agent search / filter
- [ ] Workspace selector
- [ ] Historical status trends

## Contributing

Prefer small, reviewed changes. Keep the helper on Python stdlib, keep QML on the normalized contract, and never target the default Herdr session from automated tests. See [docs/DESIGN.md](docs/DESIGN.md) and [docs/HERDR-CONTRACT.md](docs/HERDR-CONTRACT.md).

## License

MIT

## Author

Tom Norris
