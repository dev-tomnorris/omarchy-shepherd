import QtQuick

QtObject {
  id: root

  property var agents: []

  readonly property var grouped: computeGrouped()

  function normalizeNumber(value) {
    var n = Number(value)
    return isFinite(n) ? n : 0
  }

  function normalizeWorkspace(ws) {
    if (!ws || typeof ws !== "object") return null
    var id = ws.id
    if (!id || typeof id !== "string") return null
    return {
      id: id,
      label: (ws.label && typeof ws.label === "string" && ws.label.trim() !== "") ? ws.label : id,
      number: normalizeNumber(ws.number)
    }
  }

  function normalizeTab(tab) {
    if (!tab || typeof tab !== "object") return null
    var id = tab.id
    if (!id || typeof id !== "string") return null
    return {
      id: id,
      label: (tab.label && typeof tab.label === "string" && tab.label.trim() !== "") ? tab.label : id,
      number: normalizeNumber(tab.number)
    }
  }

  function isValidAgent(agent) {
    if (!agent || typeof agent !== "object") return false
    if (!agent.pane_id || typeof agent.pane_id !== "string") return false
    if (!normalizeWorkspace(agent.workspace)) return false
    if (!normalizeTab(agent.tab)) return false
    return true
  }

  function computeGrouped() {
    if (!Array.isArray(agents) || agents.length === 0) return []

    var normalized = []
    for (var i = 0; i < agents.length; i++) {
      var agent = agents[i]
      if (!isValidAgent(agent)) continue

      var ws = normalizeWorkspace(agent.workspace)
      var tab = normalizeTab(agent.tab)

      normalized.push({
        pane_id: agent.pane_id,
        name: agent.name || "",
        workspace: ws,
        tab: tab,
        record: agent
      })
    }

    if (normalized.length === 0) return []

    var workspaceMap = new Map()

    for (var j = 0; j < normalized.length; j++) {
      var item = normalized[j]
      var wsKey = item.workspace.id

      if (!workspaceMap.has(wsKey)) {
        workspaceMap.set(wsKey, {
          workspace: item.workspace,
          tabs: new Map()
        })
      }

      var wsEntry = workspaceMap.get(wsKey)
      var tabKey = item.tab.id

      if (!wsEntry.tabs.has(tabKey)) {
        wsEntry.tabs.set(tabKey, {
          tab: item.tab,
          agents: []
        })
      }

      wsEntry.tabs.get(tabKey).agents.push(item)
    }

    var result = []
    var workspaceEntries = Array.from(workspaceMap.entries())
    workspaceEntries.sort(function(a, b) {
      var wsA = a[1].workspace
      var wsB = b[1].workspace

      if (wsA.number !== wsB.number) return wsA.number - wsB.number
      if (wsA.label !== wsB.label) return wsA.label.localeCompare(wsB.label)
      return wsA.id.localeCompare(wsB.id)
    })

    for (var k = 0; k < workspaceEntries.length; k++) {
      var wsEntry = workspaceEntries[k][1]
      var tabEntries = Array.from(wsEntry.tabs.entries())
      tabEntries.sort(function(a, b) {
        var tabA = a[1].tab
        var tabB = b[1].tab

        if (tabA.number !== tabB.number) return tabA.number - tabB.number
        if (tabA.label !== tabB.label) return tabA.label.localeCompare(tabB.label)
        return tabA.id.localeCompare(tabB.id)
      })

      var tabs = []
      for (var m = 0; m < tabEntries.length; m++) {
        var tabEntry = tabEntries[m][1]
        tabEntry.agents.sort(function(x, y) {
          var nameX = (x.name || "").toLowerCase()
          var nameY = (y.name || "").toLowerCase()

          if (nameX !== nameY) return nameX.localeCompare(nameY)
          return x.pane_id.localeCompare(y.pane_id)
        })

        var tabGroup = {
          tab: tabEntry.tab,
          agents: tabEntry.agents.map(function(agent) { return agent.record })
        }
        tabs.push(tabGroup)
      }

      var wsGroup = {
        workspace: wsEntry.workspace,
        tabs: tabs
      }
      result.push(wsGroup)
    }

    return result
  }
}
