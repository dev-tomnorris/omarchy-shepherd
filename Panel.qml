import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

Panel {
  id: root
  moduleName: "dev.tomnorris.shepherd"
  ipcTarget: "dev.tomnorris.shepherd"
  manageIpc: false

  readonly property var shepherd: bar?.shell?.serviceFor("dev.tomnorris.shepherd")
  readonly property color foreground: bar ? bar.foreground : Color.foreground
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

  readonly property bool hasAgents: !!(shepherd && shepherd.agents && shepherd.agents.length > 0)
  readonly property bool hasGrouped: !!(shepherd && shepherd.grouped && shepherd.grouped.length > 0)
  readonly property var groupedModel: hasGrouped ? shepherd.grouped : []

  readonly property string heroMeta: {
    if (!shepherd) return "Service unavailable"
    if (shepherd.helperCrashed) return "Shepherd helper is restarting"
    if (shepherd.stale && hasAgents) return "Reconnecting — showing last known state"
    if (shepherd.connection === "disconnected" && !hasAgents) return "Herdr is not running"
    if (!hasGrouped) return "No agents detected"
    return "Service ready"
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  IpcHandler {
    target: root.ipcTarget

    function open(): void { root.open() }
    function close(): void { root.close() }
    function show(): void { root.open() }
    function hide(): void { root.close() }
    function toggle(): void { root.toggle() }
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "󰭘"
    tooltipText: "Shepherd agents."
    onPressed: function(buttonCode) {
      if (buttonCode === Qt.LeftButton) root.toggle()
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(380))
    contentHeight: panel.fittedContentHeight(column.implicitHeight)

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent

      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }

      Flickable {
        id: panelFlick
        anchors.fill: parent
        contentWidth: width
        contentHeight: column.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick
        interactive: contentHeight > height
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        Column {
          id: column
          width: panelFlick.width
          spacing: Style.space(14)

          PanelHero {
            width: parent.width
            title: "Shepherd"
            meta: root.heroMeta
            foreground: root.foreground
            fontFamily: root.fontFamily
            iconComponent: Component {
              Text {
                text: "󰭘"
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.display
              }
            }
          }

          StatusSummary {
            id: statusSummary
            visible: root.hasGrouped
            width: parent.width
            total: root.shepherd && root.shepherd.counts ? (root.shepherd.counts.total || 0) : 0
            working: root.shepherd && root.shepherd.counts ? (root.shepherd.counts.working || 0) : 0
            blocked: root.shepherd && root.shepherd.counts ? (root.shepherd.counts.blocked || 0) : 0
            idle: root.shepherd && root.shepherd.counts ? (root.shepherd.counts.idle || 0) : 0
            done: root.shepherd && root.shepherd.counts ? (root.shepherd.counts.done || 0) : 0
            unknown: root.shepherd && root.shepherd.counts ? (root.shepherd.counts.unknown || 0) : 0
            foreground: root.foreground
          }

          Column {
            id: hierarchyColumn
            visible: root.hasGrouped
            width: parent.width
            spacing: Style.space(14)

            Repeater {
              id: workspaceRepeater
              model: root.groupedModel

              delegate: WorkspaceSection {
                required property var modelData
                width: hierarchyColumn.width
                workspace: modelData.workspace
                tabs: modelData.tabs
                foreground: root.foreground
                fontFamily: root.fontFamily
              }
            }
          }

          Text {
            visible: root.shepherd && !root.shepherd.helperCrashed
                     && root.shepherd.connection !== "disconnected"
                     && !root.hasGrouped
            width: parent.width
            text: "No agents detected"
            color: Qt.darker(root.foreground, 1.5)
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
          }

          Text {
            visible: root.shepherd && root.shepherd.connection === "disconnected"
                     && !root.hasAgents && !root.shepherd.helperCrashed
            width: parent.width
            text: "Herdr is not running"
            color: Qt.darker(root.foreground, 1.5)
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
          }

          Text {
            visible: root.shepherd && root.shepherd.helperCrashed && !root.hasGrouped
            width: parent.width
            text: "Shepherd helper is restarting"
            color: Color.urgent
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
          }

          Text {
            visible: !root.shepherd
            width: parent.width
            text: "Service unavailable"
            color: Qt.darker(root.foreground, 1.5)
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
          }
        }
      }
    }
  }
}
