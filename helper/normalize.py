"""Normalize Herdr snapshot to the documented QML contract."""


class Normalizer:
    VALID_STATUSES = {"working", "blocked", "done", "idle", "unknown"}
    DEFAULT_COUNTS = {"working": 0, "blocked": 0, "done": 0, "idle": 0, "unknown": 0}

    def normalize_snapshot(self, snapshot):
        workspaces = {ws["workspace_id"]: ws for ws in snapshot.get("workspaces", [])}
        tabs = {tab["tab_id"]: tab for tab in snapshot.get("tabs", [])}
        agents = snapshot.get("agents", [])
        normalized = []
        counts = dict(self.DEFAULT_COUNTS)
        for agent in agents:
            normalized_agent = self._normalize_agent(agent, workspaces, tabs)
            if normalized_agent:
                normalized.append(normalized_agent)
                counts[normalized_agent["status"]] += 1
        counts["total"] = len(normalized)
        return {"agents": normalized, "counts": counts}

    def _normalize_agent(self, agent, workspaces, tabs):
        pane_id = agent.get("pane_id")
        if not pane_id:
            return None
        name = agent.get("name")
        agent_name = agent.get("agent")
        identity = name or agent_name
        if not identity:
            return None
        status = agent.get("agent_status", "unknown")
        if status not in self.VALID_STATUSES:
            status = "unknown"
        workspace_id = agent.get("workspace_id")
        tab_id = agent.get("tab_id")
        workspace = workspaces.get(workspace_id) if workspace_id else None
        tab = tabs.get(tab_id) if tab_id else None
        if workspace:
            workspace_num = workspace.get("number", 0)
            workspace_label = workspace.get("label") or workspace.get("workspace_id") or ""
        else:
            workspace_num = 0
            workspace_label = workspace_id or ""
        if tab:
            tab_num = tab.get("number", 0)
            tab_label = tab.get("label") or tab.get("tab_id") or ""
        else:
            tab_num = 0
            tab_label = tab_id or ""
        return {
            "pane_id": pane_id,
            "name": identity,
            "status": status,
            "focused": agent.get("focused", False),
            "workspace": {
                "id": workspace_id or "",
                "label": workspace_label,
                "number": workspace_num,
            },
            "tab": {
                "id": tab_id or "",
                "label": tab_label,
                "number": tab_num,
            },
        }
