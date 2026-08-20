import QtQuick
import qs.Commons
import qs.Ui

Column {
  id: root

  property var tab: null
  property var agents: []
  property color foreground: Color.foreground
  property string fontFamily: Style.font.family

  width: parent ? parent.width : implicitWidth
  spacing: Style.space(6)

  PanelSeparator {
    width: parent.width
    foreground: root.foreground
    strength: 0.08
  }

  PanelSectionHeader {
    visible: !!(tab && tab.label && String(tab.label).trim() !== "")
    width: parent.width
    text: (tab && tab.label) ? tab.label : ""
    foreground: Qt.darker(root.foreground, 1.4)
    fontFamily: root.fontFamily
    fontSize: Style.font.caption
  }

  Repeater {
    model: agents || []

    delegate: AgentRow {
      required property var modelData
      width: root.width
      agent: modelData
      foreground: root.foreground
      fontFamily: root.fontFamily
    }
  }
}
