import QtQuick
import qs.Commons

// Compact 2×3 count grid. A single six-column Row overflows at the
// panel's ~Style.space(380) content width (caption labels like WORKING /
// UNKNOWN are wider than a 1/6 share after Style.space gaps).
Grid {
  id: root

  property color foreground: Color.foreground
  property int total: 0
  property int working: 0
  property int blocked: 0
  property int idle: 0
  property int done: 0
  property int unknown: 0

  columns: 3
  columnSpacing: Style.space(12)
  rowSpacing: Style.space(8)
  width: parent ? parent.width : implicitWidth

  readonly property real cellWidth: columns > 0
    ? Math.max(0, (width - columnSpacing * (columns - 1)) / columns)
    : 0

  readonly property var cells: [
    { label: "TOTAL", value: total, urgent: false },
    { label: "WORKING", value: total > 0 ? working : 0, urgent: false },
    { label: "BLOCKED", value: total > 0 ? blocked : 0, urgent: true },
    { label: "IDLE", value: total > 0 ? idle : 0, urgent: false },
    { label: "DONE", value: total > 0 ? done : 0, urgent: false },
    { label: "UNKNOWN", value: total > 0 ? unknown : 0, urgent: false }
  ]

  Repeater {
    model: root.cells

    delegate: Column {
      required property var modelData
      width: root.cellWidth
      spacing: Style.space(2)

      Text {
        width: parent.width
        text: modelData.value
        color: modelData.urgent ? Color.urgent : root.foreground
        font.family: Style.font.family
        font.pixelSize: Style.font.body
        font.bold: true
        elide: Text.ElideRight
      }

      Text {
        width: parent.width
        text: modelData.label
        color: Qt.darker(root.foreground, 1.5)
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
        font.letterSpacing: 1.2
        elide: Text.ElideRight
      }
    }
  }
}
