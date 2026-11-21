import QtQuick

// Paleta Obsidian Gold — isolada ao plugin Ryoku (não altera o tema Omarchy).
QtObject {
  readonly property color bg: "#09090B"
  readonly property color surface: "#18181C"
  readonly property color surfaceRaised: "#1F1F24"
  readonly property color border: "#303035"
  readonly property color gold: "#D4AF67"
  readonly property color goldHover: "#E6C37C"
  readonly property color danger: "#A83B42"
  readonly property color text: "#F2EFE8"
  readonly property color textMuted: "#98989F"
  readonly property color userBubble: "#18181C"
  readonly property color assistantTint: "#121214"

  readonly property real radiusSm: 8
  readonly property real radiusMd: 12
  readonly property real radiusLg: 16
  readonly property real sidebarRatio: 0.30
  readonly property real bubbleMaxRatio: 0.78
}
