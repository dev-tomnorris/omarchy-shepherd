"""Shepherd event-subscription set and pane membership tracking.

Status-event emission (Herdr 0.8.0 server, herdrdev/herdr ``src/app/api.rs``):

``emit_pane_state_update`` emits ``EventKind::PaneAgentStatusChanged`` when
semantic ``agent_status`` or presentation changes. It emits
``EventKind::PaneUpdated`` only when ``update.agent_name_changed`` is true.

Therefore ``pane.updated`` is **not** guaranteed for agent-status changes.
``pane.agent_status_changed`` requires ``pane_id`` (schema Subscription oneOf).
Shepherd subscribes to that type once per pane in the current snapshot and
rebuilds the subscribe stream when the pane-id set changes.
"""

UNSCOPED_SUBSCRIPTIONS = (
    {"type": "workspace.created"},
    {"type": "workspace.updated"},
    {"type": "workspace.renamed"},
    {"type": "workspace.moved"},
    {"type": "workspace.reordered"},
    {"type": "workspace.closed"},
    {"type": "workspace.focused"},
    {"type": "tab.created"},
    {"type": "tab.closed"},
    {"type": "tab.renamed"},
    {"type": "tab.moved"},
    {"type": "tab.focused"},
    {"type": "pane.created"},
    {"type": "pane.updated"},
    {"type": "pane.closed"},
    {"type": "pane.focused"},
    {"type": "pane.moved"},
    {"type": "pane.exited"},
    {"type": "pane.agent_detected"},
)


def pane_ids_from_snapshot(snapshot):
    """Public pane ids present on the snapshot (panes list, else agents)."""
    if not isinstance(snapshot, dict):
        return ()
    panes = snapshot.get("panes")
    if isinstance(panes, list) and panes:
        ids = tuple(p.get("pane_id") for p in panes if isinstance(p, dict) and p.get("pane_id"))
        return tuple(dict.fromkeys(ids))
    agents = snapshot.get("agents") or []
    ids = tuple(a.get("pane_id") for a in agents if isinstance(a, dict) and a.get("pane_id"))
    return tuple(dict.fromkeys(ids))


def build_subscriptions(pane_ids):
    subscriptions = [dict(item) for item in UNSCOPED_SUBSCRIPTIONS]
    for pane_id in pane_ids:
        subscriptions.append({"type": "pane.agent_status_changed", "pane_id": pane_id})
    return subscriptions
