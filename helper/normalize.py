"""Normalize Herdr snapshot to the documented QML contract.

Workspace/tab join from nested snapshot lists is intentionally unchanged here;
that is a later bounded task.
"""

from collections import defaultdict


class Normalizer:
    VALID_STATUSES = {"working", "blocked", "done", "idle", "unknown"}

    def __init__(self):
        self.focused_agent_pane_id = None

    def normalize_snapshot(self, snapshot):
        agents = snapshot.get("agents", [])
        self.focused_agent_pane_id = snapshot.get("focused_pane_id")
        normalized = []
        counts = defaultdict(int)
        for agent in agents:
            normalized_agent = self._normalize_agent(agent)
            if normalized_agent:
                normalized.append(normalized_agent)
                status = normalized_agent["status"]
                if status in self.VALID_STATUSES:
                    counts[status] += 1
        counts["total"] = len(normalized)
        return {"agents": normalized, "counts": dict(counts)}

    def _normalize_agent(self, agent):
        pane_id = agent.get("pane_id")
        if not pane_id:
            return None
        status = agent.get("agent_status", "unknown")
        if status not in self.VALID_STATUSES:
            status = "unknown"
        workspace = agent.get("workspace_id")
        tab_id = agent.get("tab_id")
        tab_number = agent.get("tab_number", 1)
        tab_label = agent.get("tab_label") or str(tab_number)
        return {
            "pane_id": pane_id,
            "name": agent.get("name") or agent.get("agent") or "unknown",
            "status": status,
            "focused": agent.get("focused", False) or (pane_id == self.focused_agent_pane_id),
            "workspace": {
                "id": workspace,
                "label": agent.get("workspace_label") or workspace,
                "number": agent.get("workspace_number", 1),
            },
            "tab": {
                "id": tab_id,
                "label": tab_label,
                "number": tab_number,
            },
        }

    def get_fixture(self):
        return {
            "agents": [
                {
                    "pane_id": "w1:p1",
                    "name": "opencode",
                    "status": "working",
                    "focused": True,
                    "workspace": {"id": "w1", "label": "Project", "number": 1},
                    "tab": {"id": "w1:t1", "label": "1", "number": 1},
                },
                {
                    "pane_id": "w1:p2",
                    "name": "reviewer",
                    "status": "blocked",
                    "focused": False,
                    "workspace": {"id": "w1", "label": "Project", "number": 1},
                    "tab": {"id": "w1:t1", "label": "1", "number": 1},
                },
                {
                    "pane_id": "w1:p3",
                    "name": "builder",
                    "status": "idle",
                    "focused": False,
                    "workspace": {"id": "w1", "label": "Project", "number": 1},
                    "tab": {"id": "w1:t1", "label": "1", "number": 1},
                },
                {
                    "pane_id": "w1:p4",
                    "name": "formatter",
                    "status": "done",
                    "focused": False,
                    "workspace": {"id": "w1", "label": "Project", "number": 1},
                    "tab": {"id": "w1:t1", "label": "1", "number": 1},
                },
                {
                    "pane_id": "w1:p5",
                    "name": "tester",
                    "status": "unknown",
                    "focused": False,
                    "workspace": {"id": "w1", "label": "Project", "number": 1},
                    "tab": {"id": "w1:t1", "label": "1", "number": 1},
                },
            ],
            "counts": {"working": 1, "blocked": 1, "done": 1, "idle": 1, "unknown": 1, "total": 5},
        }
