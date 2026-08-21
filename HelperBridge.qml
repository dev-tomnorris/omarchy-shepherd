import QtQuick
import Quickshell
import Quickshell.Io

QtObject {
  id: root

  // Plugin root directory (manifest.__sourceDir). Process runs
  //   python3 -m helper.shepherd_helper
  // with workingDirectory set to this path.
  property string pluginRoot: ""

  // Retained for Service/public API compatibility: path to the helper module file.
  readonly property string helperPath: nonemptyString(pluginRoot)
    ? (pluginRoot.replace(/\/+$/, "") + "/helper/shepherd_helper.py")
    : ""

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
  property bool helperCrashed: false
  property var pendingFocus: null
  property var lastActionError: null
  property var lastProtocolError: null

  readonly property bool helperRunning: helperProc.running

  readonly property int maxCommandBytes: 65536
  property int requestSeq: 0
  property int restartDelayMs: 1000
  property bool expectedStop: false
  property var pendingRefresh: null

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

  function utf8ByteLength(text) {
    var encoded = encodeURIComponent(String(text || ""))
    var bytes = 0
    for (var i = 0; i < encoded.length; i++) {
      if (encoded.charAt(i) === "%") {
        bytes += 1
        i += 2
      } else {
        bytes += 1
      }
    }
    return bytes
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
    if (!value || typeof value !== "object") return out
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

  function setProtocolError(code, message, requestId) {
    var err = {
      code: nonemptyString(code) ? code : "invalid_message",
      message: nonemptyString(message) ? message : "Invalid helper message"
    }
    if (requestId !== undefined) err.request_id = requestId
    root.lastProtocolError = err
  }

  function failPending(focusMessage, refreshMessage) {
    if (root.pendingFocus) {
      root.lastActionError = {
        requestId: root.pendingFocus.requestId,
        message: focusMessage
      }
      root.pendingFocus = null
    }
    if (root.pendingRefresh) {
      root.lastActionError = {
        requestId: root.pendingRefresh.requestId,
        message: refreshMessage
      }
      root.pendingRefresh = null
    }
  }

  function clearPending() {
    root.pendingFocus = null
    root.pendingRefresh = null
  }

  function writeCommand(obj) {
    if (!helperProc.running) return ""
    var serialized
    try {
      serialized = JSON.stringify(obj)
    } catch (e) {
      return ""
    }
    if (utf8ByteLength(serialized) >= root.maxCommandBytes) return ""
    helperProc.write(serialized + "\n")
    return obj.request_id
  }

  function start() {
    if (!nonemptyString(root.pluginRoot)) return
    if (helperProc.running) return
    if (restartTimer.running) return
    // Quickshell.Io.Process: argv list + workingDirectory (no shell).
    helperProc.workingDirectory = root.pluginRoot.replace(/\/+$/, "")
    helperProc.command = ["python3", "-m", "helper.shepherd_helper"]
    helperProc.running = true
  }

  function stop() {
    restartTimer.stop()
    if (helperProc.running) root.expectedStop = true
    if (helperProc.running) helperProc.running = false
    root.helperCrashed = false
    root.connection = "disconnected"
    root.stale = true
    clearPending()
  }

  function focus(paneId) {
    if (!nonemptyString(paneId)) return ""
    if (!helperProc.running) return ""
    if (root.pendingFocus) return ""
    var requestId = nextRequestId()
    var written = writeCommand({
      type: "focus",
      request_id: requestId,
      pane_id: paneId
    })
    if (written === "") return ""
    // Clear prior action error when a new focus request is accepted (request-start).
    root.lastActionError = null
    root.pendingFocus = { requestId: requestId, paneId: paneId }
    return requestId
  }

  function refresh() {
    if (!helperProc.running) return ""
    if (root.pendingRefresh) return ""
    var requestId = nextRequestId()
    var written = writeCommand({
      type: "refresh",
      request_id: requestId
    })
    if (written === "") return ""
    root.pendingRefresh = { requestId: requestId }
    return requestId
  }

  function applyState(msg) {
    var nextConnection = msg.connection === "connected" ? "connected" : "disconnected"
    var nextStale = msg.stale === true ? true : (msg.stale === false ? false : nextConnection !== "connected")
    root.connection = nextConnection
    root.stale = nextStale
    root.agents = sanitizeAgents(msg.agents)
    root.counts = sanitizeCounts(msg.counts)
    root.helperCrashed = false
    root.restartDelayMs = 1000
  }

  function applyActionResult(msg) {
    var requestId = msg.request_id
    var ok = msg.ok === true
    if (root.pendingFocus && root.pendingFocus.requestId === requestId) {
      if (!ok) {
        root.lastActionError = {
          requestId: requestId,
          message: nonemptyString(msg.message) ? msg.message : "Unable to focus pane."
        }
      } else if (root.lastActionError && root.lastActionError.requestId === requestId) {
        root.lastActionError = null
      }
      root.pendingFocus = null
      return
    }
    if (root.pendingRefresh && root.pendingRefresh.requestId === requestId) {
      if (!ok) {
        root.lastActionError = {
          requestId: requestId,
          message: nonemptyString(msg.message) ? msg.message : "Unable to refresh state."
        }
      } else if (root.lastActionError && root.lastActionError.requestId === requestId) {
        root.lastActionError = null
      }
      root.pendingRefresh = null
    }
  }

  function applyError(msg) {
    var requestId = msg.request_id
    setProtocolError(msg.code, nonemptyString(msg.message) ? msg.message : "Helper error", requestId)
    if (root.pendingFocus && root.pendingFocus.requestId === requestId) {
      // Fixed copy only — never surface protocol/helper message text to the panel.
      root.lastActionError = {
        requestId: requestId,
        message: "Unable to focus pane."
      }
      root.pendingFocus = null
    }
    if (root.pendingRefresh && root.pendingRefresh.requestId === requestId)
      root.pendingRefresh = null
  }

  function handleStdoutLine(line) {
    var text = String(line || "").trim()
    if (text === "") return
    var msg
    try {
      msg = JSON.parse(text)
    } catch (e) {
      setProtocolError("invalid_json", "Malformed JSON")
      return
    }
    if (!msg || typeof msg !== "object") {
      setProtocolError("invalid_message", "Invalid helper message")
      return
    }
    if (msg.type === "state") {
      applyState(msg)
      return
    }
    if (msg.type === "action_result") {
      applyActionResult(msg)
      return
    }
    if (msg.type === "error") {
      applyError(msg)
      return
    }
    setProtocolError("unknown_command", "Unknown message type")
  }

  function scheduleRestart() {
    if (root.expectedStop) return
    if (!nonemptyString(root.pluginRoot)) return
    if (restartTimer.running) return
    restartTimer.interval = root.restartDelayMs
    restartTimer.start()
    root.restartDelayMs = Math.min(root.restartDelayMs * 2, 30000)
  }

  onPluginRootChanged: {
    if (!nonemptyString(root.pluginRoot)) stop()
    else start()
  }

  Component.onCompleted: {
    if (nonemptyString(root.pluginRoot)) start()
  }

  Component.onDestruction: {
    stop()
  }

  property Process helperProc: Process {
    stdinEnabled: true
    stdout: SplitParser {
      onRead: function(line) { root.handleStdoutLine(line) }
    }
    stderr: SplitParser {
      onRead: function(line) {
        if (String(line || "").trim() !== "")
          console.warn("Shepherd helper reported an error")
      }
    }
    onExited: function(exitCode) {
      if (root.expectedStop) {
        root.expectedStop = false
        root.connection = "disconnected"
        root.stale = true
        return
      }
      root.helperCrashed = true
      root.connection = "disconnected"
      root.stale = true
      root.failPending("Unable to focus pane.", "Unable to refresh state.")
      root.scheduleRestart()
    }
  }

  property Timer restartTimer: Timer {
    repeat: false
    onTriggered: root.start()
  }
}
