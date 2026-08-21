# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project does not strictly adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
until a stable 1.0.0 release is tagged.

## [Unreleased]

## [0.1.0] - 2026-08-21

Shepherd v0.1.0 implements Phases 0–3 (monitor, focus, managed-client presentation, and public-release polish). Application behavior was verified at merged main commit `e55ee38`.

### Added

- Omarchy `service` and `bar-widget` entry points
- Herdr 0.8.x monitoring via exclusive subscribe
- Normalized workspace, tab, and agent state (`pane_id`, name, status, focused, workspace, tab)
- Status counts (working, blocked, done, idle, unknown, total)
- Agent hierarchy grouped by workspace then tab
- Mouse and keyboard focus activation on agent rows via Herdr `agent.focus`
- Keyboard agent-row navigation (Up/Down or k/j, Enter/Space, Escape close, Tab/Backtab panel switch)
- Optional documented `SUPER + CTRL + G` binding via `omarchy-shell shell toggle dev.tomnorris.shepherd` (user Hyprland config; plugin does not edit it)
- Managed Herdr client open/raise after correlated focus success
- Panel closes only after successful managed-client presentation (`bar.run` accepted); failures leave fixed status visible
- Three-second presentation cooldown with `Opening Herdr…` feedback when the panel is reopened during cooldown
- Concise bar tooltip and PanelHero status (agent counts, connection/helper/cooldown fixed copy)
- Default and conventional named-session presentation descriptors
- Fail-closed presentation for arbitrary `HERDR_SOCKET_PATH` overrides
- Developer fixture mode (`SHEPHERD_DEV_FIXTURE=1`)
- Helper reconnect and state-dedup logic
- Unit, fake-server, and opt-in disposable-live Herdr test suites

## Known limitations

- Focus targets `pane_id` (not agent name alone) in Shepherd's IPC
- Herdr may report `unknown` when classification is uncertain
- Some panes have no agent and never appear in normalized output
- A Herdr terminal launched without Shepherd's dedicated app ID is outside Omarchy's managed-window reuse for Shepherd
- A detached-but-still-open Shepherd-managed terminal is raised by app ID without reattach; close that window to restore automatic launch/attach
- Herdr panes may lack compositor session variables; launch ownership stays with Omarchy `bar.run` in the graphical shell
- Positional `SUPER + CTRL + <number>` panel shortcuts depend on bar-widget order and are not a stable Shepherd binding

[Unreleased]: https://github.com/dev-tomnorris/omarchy-shepherd/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/dev-tomnorris/omarchy-shepherd/releases/tag/v0.1.0
