import QtQuick
import qs.Commons
import qs.Ui

Column {
  id: root

  property var tab: null
  property var agents: []
  property color foreground: Color.foreground
  property string fontFamily: Style.font.family
  property bool serviceReady: false
  property bool focusBusy: false
  property bool presentationBusy: false
  property string pendingPaneId: ""
  property string selectedPaneId: ""
  property bool cursorActive: false

  signal focusRequested(string paneId)
  signal pointerSelectRequested(string paneId)
  signal ensureVisibleRequested(var item)

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
      serviceReady: root.serviceReady
      focusBusy: root.focusBusy
      presentationBusy: root.presentationBusy
      pendingPaneId: root.pendingPaneId
      keyboardSelected: root.cursorActive
                     && root.selectedPaneId !== ""
                     && typeof modelData.pane_id === "string"
                     && modelData.pane_id === root.selectedPaneId
      onActivateRequested: function(paneId) { root.focusRequested(paneId) }
      onPointerSelectRequested: function(paneId) { root.pointerSelectRequested(paneId) }
      onEnsureVisibleRequested: function(item) { root.ensureVisibleRequested(item) }
    }
  }
}
