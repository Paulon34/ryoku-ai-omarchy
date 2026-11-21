import QtQuick

// Paleta Obsidian Gold — isolada ao plugin Ryoku (não altera o tema Omarchy).
// Visual minimalista: raio quase nulo, divisórias em vez de cards.
QtObject {
  readonly property color bg: "#09090B"
  readonly property color surface: "#121214"
  readonly property color surfaceRaised: "#18181C"
  readonly property color border: "#303035"
  readonly property color divider: "#242428"
  readonly property color gold: "#D4AF67"
  readonly property color goldHover: "#E6C37C"
  readonly property color danger: "#A83B42"
  readonly property color text: "#F2EFE8"
  readonly property color textMuted: "#98989F"
  readonly property color userBubble: "#161618"
  readonly property color assistantTint: "#0E0E10"
  readonly property color selectedFill: Qt.rgba(0.831, 0.686, 0.404, 0.10)

  readonly property real radiusNone: 0
  readonly property real radiusSm: 2
  readonly property real radiusMd: 2
  readonly property real radiusLg: 2
  readonly property real dividerWidth: 1
  readonly property real sidebarWidth: 168
  readonly property real bubbleMaxRatio: 0.72
}
