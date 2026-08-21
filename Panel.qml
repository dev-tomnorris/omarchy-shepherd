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

  readonly property bool serviceReady: !!(shepherd
    && shepherd.connection === "connected"
    && shepherd.stale === false
    && !shepherd.helperCrashed)
  readonly property bool focusBusy: !!(shepherd && shepherd.pendingFocus)
  readonly property bool presentationBusy: presentationCooldown.running
  readonly property string pendingPaneId: {
    if (!shepherd || !shepherd.pendingFocus) return ""
    var paneId = shepherd.pendingFocus.paneId
    return typeof paneId === "string" ? paneId : ""
  }
  readonly property bool showFocusError: !!(shepherd && shepherd.lastActionError)
  property string presentationMessage: ""
  readonly property string panelErrorText: {
    if (presentationMessage !== "") return presentationMessage
    if (showFocusError) return "Unable to focus pane."
    return ""
  }
  readonly property bool showPanelError: panelErrorText !== ""

  readonly property string heroMeta: {
    if (!shepherd) return "Service unavailable"
    if (shepherd.helperCrashed) return "Shepherd helper is restarting"
    if (shepherd.stale && hasAgents) return "Reconnecting — showing last known state"
    if (shepherd.connection === "disconnected" && !hasAgents) return "Herdr is not running"
    if (!hasGrouped) return "No agents detected"
    return "Service ready"
  }

  property Presentation presentationUtil: Presentation {}

  property Timer presentationCooldown: Timer {
    interval: presentationUtil.cooldownMs
    repeat: false
  }

  // Request ID captured from shepherd.focus(); consumed on matching completion/failure.
  property string expectedFocusRequestId: ""
  // Snapshot of lastFocusSuccess at Panel bind/init — never launch from pre-existing records.
  property var ignoredFocusSuccess: null

  readonly property var lastFocusSuccess: shepherd ? shepherd.lastFocusSuccess : null
  readonly property var lastActionErrorWatch: shepherd ? shepherd.lastActionError : null

  onShepherdChanged: {
    // Service swap / plugin reload: fail closed on any in-flight expectation.
    root.expectedFocusRequestId = ""
    root.ignoredFocusSuccess = shepherd ? shepherd.lastFocusSuccess : null
  }

  onLastFocusSuccessChanged: root.tryConsumeFocusSuccess()

  onLastActionErrorWatchChanged: root.clearExpectedOnMatchingFailure()

  Component.onCompleted: {
    root.ignoredFocusSuccess = shepherd ? shepherd.lastFocusSuccess : null
  }

  function requestFocus(paneId) {
    if (!shepherd) return
    if (typeof shepherd.focus !== "function") return
    if (shepherd.connection !== "connected") return
    if (shepherd.stale) return
    if (shepherd.helperCrashed) return
    if (shepherd.pendingFocus) return
    if (presentationCooldown.running) return
    if (typeof paneId !== "string" || paneId.trim() === "") return
    // New valid activation clears prior presentation error.
    root.presentationMessage = ""
    var requestId = shepherd.focus(paneId)
    if (typeof requestId === "string" && requestId !== "")
      root.expectedFocusRequestId = requestId
  }

  function clearExpectedOnMatchingFailure() {
    if (root.expectedFocusRequestId === "") return
    var err = root.lastActionErrorWatch
    if (!err || typeof err !== "object") return
    if (err.requestId === root.expectedFocusRequestId)
      root.expectedFocusRequestId = ""
  }

  function tryConsumeFocusSuccess() {
    if (root.expectedFocusRequestId === "") return
    if (!shepherd || shepherd.fixtureMode === true) return
    var rec = root.lastFocusSuccess
    if (!rec || typeof rec !== "object") return
    // Never launch a completion that existed before this Panel expected it.
    if (rec === root.ignoredFocusSuccess) return
    if (rec.requestId !== root.expectedFocusRequestId) return
    if (typeof rec.paneId !== "string" || rec.paneId.trim() === "") return

    // Consume before launch so one completion cannot launch twice.
    root.expectedFocusRequestId = ""
    root.ignoredFocusSuccess = rec
    root.presentAfterFocusSuccess(rec.paneId.trim())
  }

  function presentAfterFocusSuccess(paneId) {
    if (!shepherd) return
    if (shepherd.fixtureMode === true) return
    if (shepherd.connection !== "connected") return
    if (shepherd.stale === true) return
    if (shepherd.helperCrashed === true) return

    var result = presentationUtil.presentAfterFocus(root.bar, {
      connection: shepherd.connection,
      stale: shepherd.stale,
      helperCrashed: shepherd.helperCrashed,
      fixtureMode: shepherd.fixtureMode === true,
      presentation: shepherd.presentation
    })

    if (result.launched) {
      root.presentationMessage = ""
      presentationCooldown.restart()
      return
    }
    if (result.errorMessage !== "")
      root.presentationMessage = result.errorMessage
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

          Text {
            id: panelErrorTextItem
            visible: root.showPanelError
            width: parent.width
            text: root.panelErrorText
            color: Color.urgent
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            wrapMode: Text.WordWrap
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
                serviceReady: root.serviceReady
                focusBusy: root.focusBusy
                presentationBusy: root.presentationBusy
                pendingPaneId: root.pendingPaneId
                onFocusRequested: function(paneId) { root.requestFocus(paneId) }
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
