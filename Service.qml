import QtQuick

Item {
  id: root
  visible: false

  property var shell: null
  property var manifest: null

  readonly property string pluginSourceDir: {
    var dir = root.manifest && root.manifest.__sourceDir
    return dir ? String(dir) : ""
  }
  readonly property string helperPath: root.pluginSourceDir !== ""
    ? root.pluginSourceDir + "/helper/shepherd_helper.py"
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
  property bool helperRunning: false
  property bool helperCrashed: false
}
