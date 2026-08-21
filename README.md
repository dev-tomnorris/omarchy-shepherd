# Shepherd for Omarchy

Shepherd is an Omarchy shell plugin that monitors Herdr agents, focuses agent panes from the status bar, and opens or raises a Shepherd-managed Herdr client after a successful focus.

**Display name:** Shepherd  
**Plugin ID:** `dev.tomnorris.shepherd`  
**Tagline:** Keep watch over your Herdr flock.

> **Status:** Phases 0–2 and managed-client presentation are implemented. Phase 3 / public-release polish is in progress. **v0.1.0 is a release candidate** — usable when installed as an Omarchy plugin, but not yet tagged or released.

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
- System `python3` (stdlib only for the helper; no untested minimum version claimed)
- A Nerd Font for the bar icon glyph

## Install

Plugin lifecycle commands are interactive in a terminal (confirmations and pickers). Use `--yes` only when you need non-interactive add/update/remove.

```bash
omarchy plugin add https://github.com/dev-tomnorris/omarchy-shepherd.git
omarchy plugin enable dev.tomnorris.shepherd
```

Optional: add and enable in one step:

```bash
omarchy plugin add https://github.com/dev-tomnorris/omarchy-shepherd.git --enable
```

Bar section placement belongs to `enable` (`--section left|center|right`, or the positional placement form). `add` has no `--section` flag; interactive `add --enable` may offer a section picker, otherwise enable uses the manifest `defaultSection` (`right`).

```bash
omarchy plugin enable dev.tomnorris.shepherd --section right
```

Update an installed git-managed copy (prefer this over `git pull` inside the installed plugin directory):

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
3. Activate an agent row (mouse click, or keyboard Enter/Space on the selected row) to focus that pane and, when presentation is supported, open or raise Shepherd's managed Herdr client.
4. After a correlated focus success and a successful managed-client presentation (`bar.run` accepted), the Shepherd panel closes. Focus failures, unsupported presentation, and launcher errors leave the panel open with fixed status copy.
5. Escape closes the panel; Tab/Backtab switches panels; vertical scrolling follows normal Omarchy panel behavior.

### Keyboard navigation (in panel)

Once the Shepherd panel is open:

- **Up/Down** or **k/j** — move the agent-row cursor (clamped at the ends)
- **Enter** or **Space** — activate the selected agent (same `Panel.requestFocus` path as mouse)
- **Escape** — close the panel
- **Tab / Backtab** — switch to the next/previous Omarchy panel

### Optional keyboard opening

Shepherd does **not** edit user Hyprland configuration. To open or toggle the panel from the keyboard, add an optional binding in `~/.config/hypr/bindings.lua` (user config; survives Omarchy updates):

```lua
o.bind(
  "SUPER + CTRL + G",
  "Shepherd",
  "omarchy-shell shell toggle dev.tomnorris.shepherd"
)
```

This uses the Omarchy command:

```bash
omarchy-shell shell toggle dev.tomnorris.shepherd
```

Manually verified on Omarchy. Save the file and run `hyprctl reload` if the binding does not become active immediately. Confirm with:

```bash
omarchy menu keybindings --print | rg -i Shepherd
```

Positional `SUPER + CTRL + <number>` panel shortcuts may also work, but they are not stable because they depend on bar-widget order. Tab/Backtab can switch panels once a panel is already open.

### Presentation behavior

- **Default session** and **conventional named sessions** (`HERDR_SESSION`, or a conventional sessions socket path) are supported. Shepherd launches with a dedicated app ID (`org.omarchy.herdr` or `org.omarchy.herdr.session-<12 hex chars>`) so Omarchy can reuse one managed window.
- **Arbitrary `HERDR_SOCKET_PATH` overrides** still focus the pane inside the session, but presentation is unsupported: Shepherd shows `Open Herdr manually for this session.` and does not launch a client.
- Deduplication is by **managed terminal app ID**, not by inspecting which process is running inside the terminal. A **manually launched** Herdr terminal without Shepherd's app ID is outside that reuse set (the first Shepherd presentation may open one additional managed client).
- **Detaching** from Herdr or **closing** the visible managed client does **not** stop the persistent Herdr server or agents.
- If a Shepherd-managed terminal is **detached but still open**, `omarchy-launch-or-focus-tui` still finds that app-ID window and raises its ordinary shell. It cannot tell that the `herdr` client inside has exited, so it does not automatically reattach. **Close** that detached managed window; the next Shepherd focus creates a fresh managed terminal and attaches to the persistent session.
- After a successful presentation launch, the Shepherd panel closes and agent rows stay non-activatable for **three seconds** (cooldown). Reopening during the cooldown shows `Opening Herdr…` and keeps activation disabled. That cooldown is separate from the in-flight `Focusing…` state.

## Troubleshooting

### Herdr not running

Shepherd shows `Helper not running. Start a Herdr 0.8.x session.` Check that Herdr is running with the expected socket path.

### Helper restarting

Transient connection failures trigger a restart with exponential backoff. The panel briefly shows `Helper restarting…` before the connection returns.

### Arbitrary socket override

Manually setting `HERDR_SOCKET_PATH` to an arbitrary path focuses the pane successfully, but automatic presentation is unsupported. Shepherd displays `Open Herdr manually for this session.`

### Managed terminal behavior

- A manually launched Herdr terminal without Shepherd's app ID is outside the managed-window reuse set, so the first Shepherd presentation may open one additional managed client.
- If a Shepherd-managed terminal is detached but still open, `omarchy-launch-or-focus-tui` raises the window without reattaching. Close that detached window to restore automatic launch/attach.

### Fixture mode

If `SHEPHERD_DEV_FIXTURE=1` is set, Shepherd loads test fixtures and does not start the Python helper or contact Herdr. Unset this variable for normal use.

### Update / re-enable recovery

If the plugin becomes unresponsive after an update or enable:

1. `omarchy plugin disable dev.tomnorris.shepherd`
2. `omarchy plugin enable dev.tomnorris.shepherd`

If that fails, remove and re-add. Removal deletes the installed plugin checkout under Omarchy's plugins directory; it does **not** stop or reset Herdr's persistent session or agents.

```bash
omarchy plugin disable dev.tomnorris.shepherd
omarchy plugin remove dev.tomnorris.shepherd
omarchy plugin add https://github.com/dev-tomnorris/omarchy-shepherd.git --enable
```

## Privacy and security

- No prompts, pane output, or transcripts are displayed
- Only normalized agent / workspace / tab / status fields, plus a sanitized presentation descriptor, reach QML
- Presentation never publishes socket paths, cwd, hostnames, or raw environment values
- Terminal launch runs only through Omarchy `bar.run` with `Util.shellQuote` on every token — not from the Python helper
- No external telemetry; state is in-memory only
- Focus uses `pane_id` internally; public docs use fake IDs such as `w1:p1`
- Helper stderr stays sanitized (no raw snapshots or exception bodies)

## Roadmap

### Phase 3 — Public-release polish (in progress)

- Clean-install release gate from public GitHub `main`

Keyboard navigation, optional keyboard opening docs, successful-presentation panel close, and tooltip/hero status copy are implemented.

### Later

- Agent search / filter
- Workspace selector
- Historical status trends

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

### Manifest and entry points

`manifest.json` declares `service` and `bar-widget` kinds. See `Service.qml` and `Panel.qml`.

### Architecture

See [docs/DESIGN.md](docs/DESIGN.md) for the helper/bridge/QML architecture. [docs/HERDR-CONTRACT.md](docs/HERDR-CONTRACT.md) documents the wire protocol between the Python helper and Herdr, and between the helper and QML.

## Contributing

Prefer small, reviewed changes. Keep the helper on Python stdlib, keep QML on the normalized contract, and never target the default Herdr session from automated tests. See [docs/DESIGN.md](docs/DESIGN.md) and [docs/HERDR-CONTRACT.md](docs/HERDR-CONTRACT.md).

## License

MIT

## Author

Tom Norris
