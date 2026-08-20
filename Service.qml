import QtQuick

QtObject {
  id: root

  property var shell: null
  property var manifest: null

  readonly property string pluginSourceDir: {
    var dir = root.manifest && root.manifest.__sourceDir
    return dir ? String(dir) : ""
  }
  readonly property string helperPath: root.pluginSourceDir !== ""
    ? root.pluginSourceDir + "/helper/shepherd_helper.py"
    : ""

  readonly property alias connection: bridge.connection
  readonly property alias stale: bridge.stale
  readonly property alias agents: bridge.agents
  readonly property alias counts: bridge.counts
  readonly property alias helperRunning: bridge.helperRunning
  readonly property alias helperCrashed: bridge.helperCrashed
  readonly property alias pendingFocus: bridge.pendingFocus
  readonly property alias lastActionError: bridge.lastActionError
  readonly property alias lastProtocolError: bridge.lastProtocolError

  function focus(paneId) {
    return bridge.focus(paneId)
  }

  function refresh() {
    return bridge.refresh()
  }

  property HelperBridge bridge: HelperBridge {
    helperPath: root.helperPath
  }
}
