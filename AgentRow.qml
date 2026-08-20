import QtQuick
import qs.Commons

Row {
  id: root

  property var agent: null
  property color foreground: Color.foreground
  property string fontFamily: Style.font.family

  readonly property bool isFocused: !!(agent && agent.focused === true)
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
  readonly property string statusText: {
    switch (statusKey) {
      case "working": return "Working"
      case "blocked": return "Blocked"
      case "idle": return "Idle"
      case "done": return "Done"
      default: return "Unknown"
    }
  }
  readonly property string displayName: {
    if (agent && agent.name && String(agent.name).trim() !== "")
      return agent.name
    if (agent && agent.pane_id)
      return agent.pane_id
    return "Unknown"
  }

  width: parent ? parent.width : implicitWidth
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
    width: Math.max(0, root.width
                    - statusDot.width
                    - (focusLabel.visible ? focusLabel.implicitWidth + root.spacing : 0)
                    - root.spacing)
    spacing: Style.space(2)

    Text {
      id: nameText
      width: parent.width
      text: root.displayName
      color: root.foreground
      font.family: root.fontFamily
      font.pixelSize: Style.font.body
      font.bold: root.isFocused
      elide: Text.ElideRight
    }

    Text {
      id: statusLabel
      width: parent.width
      text: root.statusText
      color: Qt.darker(root.foreground, 1.4)
      font.family: root.fontFamily
      font.pixelSize: Style.font.caption
      font.letterSpacing: 0.5
      elide: Text.ElideRight
    }
  }

  Text {
    id: focusLabel
    text: "Focus"
    visible: root.isFocused
    color: root.foreground
    font.family: root.fontFamily
    font.pixelSize: Style.font.caption
    font.bold: true
  }
}
