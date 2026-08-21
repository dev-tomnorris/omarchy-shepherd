# Release checklist

This checklist separates generic local gates from Omarchy-machine-only gates and final release gates.

Generic runners are expected to run only the generic section. They are **not** expected to run Omarchy, Wayland, or live Herdr gates.

**Release context:** Application behavior for v0.1.0 was verified at merged public `main` commit `e55ee38`. This branch (`chore/v0.1.0-release`) contains documentation-only release finalization and does not change application code.

## Generic automated/local gates

Execute on any Linux machine with `python3` (no project-claimed minimum version):

- [x] `python -m compileall -q helper tests` — no compile errors
- [x] `python -m unittest discover -s tests -v` — all tests pass (203 tests; live Herdr suite skipped without the opt-in env)
- [x] Opt-in disposable live Herdr suite passed (10/10) against `shepherd-it-*` sessions only; default Herdr server running state unchanged
- [x] `git diff --check` — no whitespace issues
- [x] `gitleaks dir --no-banner --redact .` — no detected secrets/leaks
- [x] No tracked `__pycache__` or `.pyc` files (`git ls-files '*__pycache__*' '*.pyc'`)

Do **not** expect GitHub Actions (or any generic runner) to exercise Omarchy plugin install, Wayland presentation, or live Herdr. No CI workflow is claimed yet.

## Omarchy-machine gates

Execute on an Omarchy machine. Plugin install/update/disable/remove steps below are for release verification; prefer a disposable install path when possible.

### Validation

- [x] `omarchy plugin validate .` — plugin folder validates successfully
- [x] Plugin identity matches `dev.tomnorris.shepherd`
- [x] Plugin version matches CHANGELOG / manifest `0.1.0`

### Installation and recovery

Lifecycle commands are interactive by default. Use `--yes` only for non-interactive verification.

Verified against public GitHub `main` at `e55ee38` (clean install, update, disable/enable, enabled removal, public reinstall/recovery). Herdr 0.8.0 remained running throughout; final state was a clean public-main installation, enabled, exactly one helper, no errors.

- [x] Clean public GitHub install from `main`:
  `omarchy plugin add https://github.com/dev-tomnorris/omarchy-shepherd.git --enable`
- [x] Installed commit matched public `origin/main`; installed origin was the public GitHub URL
- [x] Panel connects and shows initial state
- [x] Exactly one Shepherd helper process runs after enable
- [x] Update preserves one helper and reports current: `omarchy plugin update dev.tomnorris.shepherd`
- [x] Disable/enable recovery reconnects without double helpers:
  `omarchy plugin disable dev.tomnorris.shepherd` then
  `omarchy plugin enable dev.tomnorris.shepherd`
- [x] Enabled removal unloads the plugin and stops the helper; plugin directory is removed.
  Herdr remains running with Shepherd absent.
- [x] Public reinstall/recovery restores the exact public commit:
  `omarchy plugin add https://github.com/dev-tomnorris/omarchy-shepherd.git --enable`
  Removal is destructive to the installed plugin checkout only; it does **not** stop or reset Herdr's persistent session or agents.
- [x] Herdr persistence confirmed across remove/reinstall
- [x] One-helper / no-error final state confirmed

### Functional

Manual Wayland/accessibility/presentation verification at `e55ee38` covered keyboard, presentation, cooldown, and managed-client items below. Connection-state, mouse-focus, and arbitrary-socket gates were completed earlier via offscreen harness, Phase 2 manual verification, and automated contract/harness tests (not re-run as live v0.1.0 Wayland mutations).

- [x] Panel shows connected/offline/empty/error states correctly — offscreen Quickshell harness (six states: connected with agents, connected empty, disconnected empty, stale with agents, helper crashed, null service); later Task C harnesses covered count-aware/cooldown copy
- [x] Mouse focus on agent row triggers pane focus — Phase 2 focus harness plus manual verification against a real Herdr session (single request, pending guard, success/failure copy, activation guards)
- [x] Managed Herdr client opens/raises after correlated focus success
- [x] Panel closes only after successful presentation; focus/presentation failures leave fixed status visible
- [x] Cooldown shows `Opening Herdr…` when the panel is reopened during the three-second window
- [x] Arbitrary socket override (`HERDR_SOCKET_PATH`) fails closed (no presentation) — Python presentation/socket contract tests plus disposable QML presentation harness (`socket_override`, no `bar.run`, fixed manual-open copy); not a live arbitrary-socket Wayland mutation
- [x] Keyboard activation — Up/Down or k/j move, Enter/Space activate, Escape close, Tab/Backtab panel switch (confirmed on Wayland)
- [x] Optional `SUPER + CTRL + G` opening via user `~/.config/hypr/bindings.lua` — documented; manually verified; plugin does not edit Hyprland config
- [x] Tooltip/hero status copy — agent counts and fixed connection/cooldown messages (confirmed on Wayland)
- [x] Keyboard navigation/accessibility and presentation interaction polish (close-on-success, cooldown feedback, count-aware status) — **complete**
- [x] Clean public install/recovery test from GitHub `main` after merge — **complete** at `e55ee38`

### Live Herdr (opt-in only)

Run only when intentionally opted in. Never against the default Herdr session.

- [x] Opt-in disposable live Herdr suite:
  `SHEPHERD_RUN_LIVE_HERDR=1 python -m unittest tests.integration.test_herdr_live -v`
- [x] Manual Wayland logs contain no Shepherd/QML errors

## Final release gates

Pre-tag verification above is complete for application behavior at `e55ee38`. Documentation-only release finalization is on this branch. The following remain pending:

### Documentation and metadata

- [x] Phase 3 implementation merged to `main` (`e55ee38`)
- [x] Clean public installation from GitHub `main` succeeded
- [x] Generic validation complete
- [x] Omarchy plugin validation complete
- [x] Manual keyboard/accessibility/presentation verification complete
- [x] Update / disable/enable / enabled removal / public reinstall/recovery complete
- [x] Herdr persistence and one-helper/no-error final state confirmed
- [x] manifest / CHANGELOG / intended tag version consistency (`0.1.0`)
- [x] Known limitations reviewed and consistent with README
- [x] CHANGELOG dated `[0.1.0] - 2026-08-21` (tag/release not published yet)
- [x] README status, requirements, and lifecycle commands reviewed
- [ ] Merge this release-finalization documentation

### Tag and release

- [ ] Create and push annotated `v0.1.0` tag
- [ ] Publish the GitHub Release (body derived from CHANGELOG `[0.1.0]` section)
- [ ] Verify the published tag/release page

---

### Notes on execution environment

These gates **cannot** run on a generic GitHub runner:

- `omarchy plugin validate .` and `add|enable|disable|update|remove`
- Mouse focus and managed-client presentation (Hyprland/Wayland session)
- Arbitrary socket-override fail-closed checks (Herdr 0.8.x)
- Opt-in disposable live Herdr suite (`SHEPHERD_RUN_LIVE_HERDR=1`)
- Manual Wayland log inspection
