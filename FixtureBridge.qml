import QtQuick
import Quickshell.Io

QtObject {
  id: root

  property string fixturePath: ""

  property Presentation presentationUtil: Presentation {}

  property string connection: "disconnected"
  property bool stale: true
  property var agents: []
  property var counts: ({
    working: 0,
    blocked: 0,
    done: 0,
    idle: 0,
    unknown: 0,
    total: 0
  })
  // Fixture mode never requests terminal presentation.
  property var presentation: presentationUtil.unsupportedDescriptor()
  property bool helperRunning: false
  property bool helperCrashed: false
  property var pendingFocus: null
  property var lastActionError: null
  property var lastProtocolError: null
  // Fixture never produces focus-success completions.
  property var lastFocusSuccess: null

  property int requestSeq: 0
  property bool loadPending: false

  readonly property string fixedFixtureErrorMessage: "Unable to load fixture."
  readonly property string fixedFocusErrorMessage: "Unable to focus pane."
  readonly property string fixedRefreshErrorMessage: "Unable to refresh state."

  function emptyAgents() {
    return []
  }

  function emptyCounts() {
    return {
      working: 0,
      blocked: 0,
      done: 0,
      idle: 0,
      unknown: 0,
      total: 0
    }
  }

  function nonemptyString(value) {
    return typeof value === "string" && value.trim() !== ""
  }

  function nextRequestId() {
    root.requestSeq += 1
    return "req-" + Date.now() + "-" + root.requestSeq
  }

  function sanitizeCounts(value) {
    var out = emptyCounts()
    if (!value || typeof value !== "object" || Array.isArray(value)) return out
    var keys = ["working", "blocked", "done", "idle", "unknown", "total"]
    for (var i = 0; i < keys.length; i++) {
      var n = Number(value[keys[i]])
      if (isFinite(n) && n >= 0) out[keys[i]] = Math.floor(n)
    }
    return out
  }

  function sanitizeAgents(value) {
    if (!Array.isArray(value)) return emptyAgents()
    return value.slice()
  }

  function setDisconnected() {
    root.connection = "disconnected"
    root.stale = true
    root.agents = emptyAgents()
    root.counts = emptyCounts()
    root.presentation = presentationUtil.unsupportedDescriptor()
    root.pendingFocus = null
    root.lastActionError = null
    root.lastProtocolError = {
      code: "invalid_fixture",
      message: root.fixedFixtureErrorMessage
    }
  }

  function setConnected(agents, counts) {
    root.agents = sanitizeAgents(agents)
    root.counts = sanitizeCounts(counts)
    root.connection = "connected"
    root.stale = false
    root.lastProtocolError = null
  }

  function applyFixtureText(raw) {
    var data
    try {
      data = JSON.parse(String(raw || ""))
    } catch (e) {
      setDisconnected()
      return false
    }

    if (!data || typeof data !== "object" || Array.isArray(data)) {
      setDisconnected()
      return false
    }
    if (!Array.isArray(data.agents)) {
      setDisconnected()
      return false
    }
    if (!data.counts || typeof data.counts !== "object" || Array.isArray(data.counts)) {
      setDisconnected()
      return false
    }

    setConnected(data.agents, data.counts)
    return true
  }

  function focus(paneId) {
    if (!nonemptyString(paneId)) return ""
    if (root.connection !== "connected") {
      root.lastActionError = {
        requestId: null,
        message: root.fixedFocusErrorMessage
      }
      return ""
    }
    var requestId = nextRequestId()
    root.pendingFocus = null
    root.lastActionError = null
    return requestId
  }

  function refresh() {
    if (root.fixturePath === "") {
      setDisconnected()
      root.lastActionError = {
        requestId: null,
        message: root.fixedRefreshErrorMessage
      }
      return ""
    }
    var requestId = nextRequestId()
    root.loadPending = true
    fixtureFile.reload()
    return requestId
  }

  onFixturePathChanged: {
    if (root.fixturePath === "") {
      setDisconnected()
      return
    }
    // Path assignment triggers FileView load; onLoaded/onLoadFailed handle result.
  }

  property FileView fixtureFile: FileView {
    path: root.fixturePath
    watchChanges: false
    printErrors: false
    onLoaded: {
      var ok = root.applyFixtureText(text())
      if (root.loadPending) {
        root.loadPending = false
        if (ok) root.lastActionError = null
        else root.lastActionError = {
          requestId: null,
          message: root.fixedRefreshErrorMessage
        }
      }
    }
    onLoadFailed: {
      root.setDisconnected()
      if (root.loadPending) {
        root.loadPending = false
        root.lastActionError = {
          requestId: null,
          message: root.fixedRefreshErrorMessage
        }
      }
    }
  }
}
