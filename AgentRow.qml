import QtQuick
import qs.Commons
import qs.Ui

// Interactive agent row. Emits activateRequested(paneId); Panel owns Service.focus().
Item {
  id: root

  property var agent: null
  property color foreground: Color.foreground
  property string fontFamily: Style.font.family
  // serviceReady: connected && !stale && !helperCrashed && service exists
  property bool serviceReady: false
  // Any in-flight focus request (all rows disabled while true).
  property bool focusBusy: false
  property string pendingPaneId: ""

  signal activateRequested(string paneId)

  readonly property bool isFocused: !!(agent && agent.focused === true)
  readonly property string paneId: {
    if (agent && typeof agent.pane_id === "string") return agent.pane_id
    return ""
  }
  readonly property bool hasPaneId: paneId.trim() !== ""
  readonly property bool isPending: focusBusy && hasPaneId && pendingPaneId === paneId
  readonly property bool canActivate: serviceReady && !focusBusy && hasPaneId

  readonly property string statusKey: {
    var status = (agent && agent.status) ? String(agent.status).toLowerCase() : "unknown"
    switch (status) {
      case "working":
      case "blocked":
      case "idle":
      case "done":
        return status
      default:
        return "unknown"
    }
  }
  readonly property string agentStatusText: {
    switch (statusKey) {
      case "working": return "Working"
      case "blocked": return "Blocked"
      case "idle": return "Idle"
      case "done": return "Done"
      default: return "Unknown"
    }
  }
  readonly property string actionStatusText: {
    if (isPending) return "Focusing…"
    if (isFocused) return "Focused"
    return agentStatusText
  }
  readonly property string displayName: {
    if (agent && agent.name && String(agent.name).trim() !== "")
      return agent.name
    if (hasPaneId)
      return paneId
    return "Unknown"
  }

  width: parent ? parent.width : implicitWidth
  implicitHeight: contentRow.implicitHeight + Style.space(8)

  Accessible.role: Accessible.Button
  Accessible.name: displayName + ", " + actionStatusText
  Accessible.description: canActivate ? "Request focus" : (isPending ? "Focus pending" : "Unavailable")
  Accessible.onPressAction: root.tryActivate()

  function tryActivate() {
    if (!canActivate) return
    activateRequested(paneId.trim())
  }

  CursorSurface {
    id: chrome
    anchors.fill: parent
    foreground: root.foreground
    hasCursor: mouseArea.containsMouse && (root.canActivate || root.isPending)
    current: root.isFocused && !root.isPending
    opacity: (root.canActivate || root.isPending || root.isFocused) ? 1.0 : 0.55
  }

  MouseArea {
    id: mouseArea
    anchors.fill: parent
    hoverEnabled: true
    acceptedButtons: Qt.LeftButton
    enabled: root.canActivate
    cursorShape: root.canActivate ? Qt.PointingHandCursor : Qt.ArrowCursor
    onClicked: root.tryActivate()
  }

  Row {
    id: contentRow
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.verticalCenter: parent.verticalCenter
    anchors.leftMargin: Style.space(6)
    anchors.rightMargin: Style.space(6)
    spacing: Style.space(12)

    Item {
      id: statusDot
      width: Style.space(8)
      height: nameColumn.implicitHeight

      Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.verticalCenter: parent.top
        anchors.verticalCenterOffset: Style.font.body * 0.55
        width: Style.space(4)
        height: Style.space(4)
        radius: width / 2
        color: statusKey === "blocked" ? Color.urgent : root.foreground
      }
    }

    Column {
      id: nameColumn
      width: Math.max(0, contentRow.width - statusDot.width - contentRow.spacing)
      spacing: Style.space(2)

      Text {
        id: nameText
        width: parent.width
        text: root.displayName
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        font.bold: root.isFocused || root.isPending
        elide: Text.ElideRight
      }

      Text {
        id: statusLabel
        width: parent.width
        text: root.actionStatusText
        color: root.isPending ? root.foreground : Qt.darker(root.foreground, 1.4)
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        font.letterSpacing: 0.5
        font.bold: root.isPending || root.isFocused
        elide: Text.ElideRight
      }
    }
  }
}
