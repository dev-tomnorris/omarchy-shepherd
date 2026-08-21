import QtQuick
import qs.Commons
import qs.Ui

Column {
  id: root

  property var workspace: null
  property var tabs: []
  property color foreground: Color.foreground
  property string fontFamily: Style.font.family
  property bool serviceReady: false
  property bool focusBusy: false
  property bool presentationBusy: false
  property string pendingPaneId: ""

  signal focusRequested(string paneId)

  width: parent ? parent.width : implicitWidth
  spacing: Style.space(8)

  PanelSectionHeader {
    width: parent.width
    text: {
      if (workspace && workspace.label && String(workspace.label).trim() !== "")
        return workspace.label
      if (workspace && workspace.id)
        return workspace.id
      return "Workspace"
    }
    foreground: root.foreground
    fontFamily: root.fontFamily
  }

  Repeater {
    model: tabs || []

    delegate: TabSection {
      required property var modelData
      width: root.width
      tab: modelData.tab
      agents: modelData.agents
      foreground: root.foreground
      fontFamily: root.fontFamily
      serviceReady: root.serviceReady
      focusBusy: root.focusBusy
      presentationBusy: root.presentationBusy
      pendingPaneId: root.pendingPaneId
      onFocusRequested: function(paneId) { root.focusRequested(paneId) }
    }
  }
}
