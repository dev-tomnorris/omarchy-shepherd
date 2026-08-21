import QtQuick
import Quickshell

QtObject {
  id: root

  property var shell: null
  property var manifest: null

  readonly property string pluginSourceDir: {
    var dir = root.manifest && root.manifest.__sourceDir
    return dir ? String(dir) : ""
  }

  // Exact string "1" only — matches installed Omarchy env checks
  // (e.g. Ui/BarIconButton.qml Quickshell.env(...) === "1").
  readonly property bool fixtureMode: Quickshell.env("SHEPHERD_DEV_FIXTURE") === "1"

  // Compatibility path to the helper module file. Process launch uses
  // pluginSourceDir as workingDirectory with `python3 -m helper.shepherd_helper`.
  readonly property string helperPath: root.pluginSourceDir !== ""
    ? root.pluginSourceDir + "/helper/shepherd_helper.py"
    : ""

  readonly property string fixturePath: root.pluginSourceDir !== ""
    ? root.pluginSourceDir + "/tests/fixtures/normalized_state.json"
    : ""

  readonly property var activeBridge: root.fixtureMode ? fixtureBridge : helperBridge

  readonly property string connection: activeBridge.connection
  readonly property bool stale: activeBridge.stale
  readonly property var agents: activeBridge.agents
  readonly property var counts: activeBridge.counts
  readonly property var presentation: activeBridge.presentation
  readonly property bool helperRunning: activeBridge.helperRunning
  readonly property bool helperCrashed: activeBridge.helperCrashed
  readonly property var pendingFocus: activeBridge.pendingFocus
  readonly property var lastActionError: activeBridge.lastActionError
  readonly property var lastProtocolError: activeBridge.lastProtocolError
  readonly property var grouped: model.grouped

  // Production HelperBridge only — never forwarded from fixture mode.
  signal focusSucceeded(string paneId)

  function focus(paneId) {
    return activeBridge.focus(paneId)
  }

  function refresh() {
    return activeBridge.refresh()
  }

  property ShepherdModel model: ShepherdModel {
    agents: root.agents
  }

  // Fixture mode: empty pluginRoot so HelperBridge never starts Process.
  property HelperBridge helperBridge: HelperBridge {
    pluginRoot: root.fixtureMode ? "" : root.pluginSourceDir
  }

  // Outside fixture mode, keep FixtureBridge idle with an empty path.
  property FixtureBridge fixtureBridge: FixtureBridge {
    fixturePath: root.fixtureMode ? root.fixturePath : ""
  }

  property Connections helperFocusForwarder: Connections {
    target: root.helperBridge
    enabled: !root.fixtureMode
    function onFocusSucceeded(paneId) {
      root.focusSucceeded(paneId)
    }
  }
}
