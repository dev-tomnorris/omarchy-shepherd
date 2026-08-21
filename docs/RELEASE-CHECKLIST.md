# Release checklist

This checklist separates generic local gates from Omarchy-machine-only gates and final release gates.

Generic runners are expected to run only the generic section. They are **not** expected to run Omarchy, Wayland, or live Herdr gates.

## Generic automated/local gates

Execute on any Linux machine with `python3` (no project-claimed minimum version):

- [ ] `python -m compileall -q helper tests` — no compile errors
- [ ] `python -m unittest discover -s tests -v` — all tests pass (live Herdr suite stays skipped without the opt-in env)
- [ ] `git diff --check` — no whitespace issues
- [ ] `gitleaks dir --no-banner --redact .` — no detected secrets/leaks
- [ ] No tracked `__pycache__` or `.pyc` files (`git ls-files '*__pycache__*' '*.pyc'`)

Do **not** expect GitHub Actions (or any generic runner) to exercise Omarchy plugin install, Wayland presentation, or live Herdr. No CI workflow is claimed yet.

## Omarchy-machine gates

Execute on an Omarchy machine. Plugin install/update/disable/remove steps below are for release verification; prefer a disposable install path when possible.

### Validation

- [ ] `omarchy plugin validate .` — plugin folder validates successfully
- [ ] Plugin identity matches `dev.tomnorris.shepherd`
- [ ] Plugin version matches CHANGELOG / manifest `0.1.0`

### Installation and recovery

Lifecycle commands are interactive by default. Use `--yes` only for non-interactive verification.

- [ ] Clean public GitHub install from `main` **after Phase 3 merge**:
  `omarchy plugin add https://github.com/dev-tomnorris/omarchy-shepherd.git --enable`
- [ ] Panel connects and shows initial state
- [ ] Exactly one Shepherd helper process runs after enable
- [ ] Update preserves one helper: `omarchy plugin update dev.tomnorris.shepherd`
- [ ] Disable/enable recovery reconnects without double helpers:
  `omarchy plugin disable dev.tomnorris.shepherd` then
  `omarchy plugin enable dev.tomnorris.shepherd`
- [ ] Remove/re-add restores a clean installed copy:
  `omarchy plugin remove dev.tomnorris.shepherd` then re-add/enable.
  Removal is destructive to the installed plugin checkout only; it does **not** stop or reset Herdr's persistent session or agents.

### Functional

- [ ] Panel shows connected/offline/empty/error states correctly
- [ ] Mouse focus on agent row triggers pane focus
- [ ] Managed Herdr client opens/raises after correlated focus success
- [ ] Panel closes only after successful presentation; focus/presentation failures leave fixed status visible
- [ ] Cooldown shows `Opening Herdr…` when the panel is reopened during the three-second window
- [ ] Arbitrary socket override (`HERDR_SOCKET_PATH`) fails closed (no presentation)
- [x] Keyboard activation — Up/Down or k/j move, Enter/Space activate, Escape close, Tab/Backtab panel switch (implemented; confirmed on Wayland)
- [x] Optional `SUPER + CTRL + G` opening via user `~/.config/hypr/bindings.lua` — documented; manually verified; plugin does not edit Hyprland config
- [x] Tooltip/hero status copy — agent counts and fixed connection/cooldown messages (implemented; confirmed on Wayland)
- [x] Keyboard navigation/accessibility and Task C interaction polish (close-on-success, cooldown feedback, count-aware status) — **complete**
- [ ] Clean public install/recovery test from GitHub `main` after merge — **pending**
- [ ] v0.1.0 date / tag / GitHub Release — **pending** (after clean-install success)

### Live Herdr (opt-in only)

Run only when intentionally opted in. Never against the default Herdr session.

- [ ] Opt-in disposable live Herdr suite:
  `SHEPHERD_RUN_LIVE_HERDR=1 python -m unittest tests.integration.test_herdr_live -v`
- [ ] Manual Wayland logs contain no Shepherd/QML errors

## Final release gates

Execute **after** Omarchy-machine gates pass, and **only after** clean public install from `main` succeeds:

### Documentation and metadata

- [ ] Phase 3 implementation merged to `main`
- [ ] Clean public installation from GitHub `main` succeeded
- [ ] manifest / CHANGELOG / intended tag version consistency (`0.1.0`)
- [ ] Known limitations reviewed and consistent with README
- [ ] CHANGELOG release-candidate notes reviewed; date filled when tagging
- [ ] README status, requirements, and lifecycle commands reviewed

### Tag and release

- [ ] Tag created **only after** clean-install success
- [ ] GitHub Release body derived from CHANGELOG `[0.1.0]` section
- [ ] Release tag pushed to GitHub

---

### Notes on execution environment

These gates **cannot** run on a generic GitHub runner:

- `omarchy plugin validate .` and `add|enable|disable|update|remove`
- Mouse focus and managed-client presentation (Hyprland/Wayland session)
- Arbitrary socket-override fail-closed checks (Herdr 0.8.x)
- Opt-in disposable live Herdr suite (`SHEPHERD_RUN_LIVE_HERDR=1`)
- Manual Wayland log inspection
