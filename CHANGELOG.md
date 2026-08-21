# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project does not strictly adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
until a stable 1.0.0 release is tagged.

When v0.1.0 is tagged, replace `Release candidate` below with the tag date (`YYYY-MM-DD`).

## [Unreleased]

Pending Phase 3 work before the v0.1.0 tag:

- Small UX polish
- Clean-install release gate from public GitHub `main`
- Keyboard accessibility

## [0.1.0] - Release candidate

Release-candidate summary of capabilities already merged and verified. Not tagged or released yet.

### Added

- Omarchy `service` and `bar-widget` entry points
- Herdr 0.8.x monitoring via exclusive subscribe
- Normalized workspace, tab, and agent state (`pane_id`, name, status, focused, workspace, tab)
- Status counts (working, blocked, done, idle, unknown, total)
- Agent hierarchy grouped by workspace then tab
- Mouse focus activation on agent rows via Herdr `agent.focus`
- Managed Herdr client open/raise after correlated focus success
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
- Keyboard activation of agent rows is not implemented yet
