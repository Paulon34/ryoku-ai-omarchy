import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Commons as Commons
import qs.Ui

// Painel Ryoku Obsidian Gold. Fala só com o CLI (argv estático + stdin). Sem tokens no QML.
Panel {
  id: root
  moduleName: "io.github.paulon34.ryoku-ai"
  manageIpc: false

  property var anchorItem: null
  property var hostWidget: null

  property var conversations: []
  property var messages: []
  property string activeId: ""
  property string statusLine: ""
  property string draft: ""
  property bool busy: false
  property bool confirmDelete: false
  property bool renaming: false
  property bool renameBusy: false
  property string renameDraft: ""
  property string pendingRename: ""
  property string streamBuffer: ""
  property string pendingPrompt: ""
  property string pendingInspect: ""
  property var pendingAttachments: []
  property bool loggedIn: true

  readonly property string ryokuBin: "ryoku"
  readonly property int maxPendingAttachments: 5

  Theme {
    id: theme
  }

  Commons.Translations {
    id: strings
    directory: Qt.resolvedUrl("i18n")
  }

  function open() {
    root.controller.show()
    Qt.callLater(root.reloadAll)
  }

  function close() {
    root.confirmDelete = false
    root.renaming = false
    root.controller.hide()
  }

  function urlToPath(url) {
    var s = String(url || "")
    if (s.indexOf("file://") === 0) {
      s = decodeURIComponent(s.substring(7))
      if (s.indexOf("//") === 0)
        s = s.substring(1)
    }
    return s
  }

  function formatBytes(n) {
    var v = Number(n) || 0
    if (v < 1024)
      return v + " B"
    if (v < 1024 * 1024)
      return Math.round(v / 102.4) / 10 + " KB"
    return Math.round(v / (1024 * 102.4)) / 10 + " MB"
  }

  function removeAttachment(index) {
    var next = root.pendingAttachments.slice()
    if (index < 0 || index >= next.length)
      return
    next.splice(index, 1)
    root.pendingAttachments = next
  }

  function clearAttachments() {
    root.pendingAttachments = []
  }

  function openFilePicker() {
    if (root.busy || root.renameBusy || !root.loggedIn)
      return
    fileDialog.open()
  }

  function queueAttachments(paths) {
    if (!paths || paths.length === 0)
      return
    var room = root.maxPendingAttachments - root.pendingAttachments.length
    if (room <= 0) {
      root.statusLine = strings.t("panel.attachLimit")
      return
    }
    var batch = paths.slice(0, room)
    root.statusLine = strings.t("panel.attachInspecting")
    // Caminhos via stdin JSON — nunca o conteúdo do arquivo no argv.
    root.pendingInspect = JSON.stringify({
      "paths": batch
    }) + "\n"
    inspectProc.command = [root.ryokuBin, "attach", "inspect", "--json"]
    inspectProc.stdinEnabled = true
    inspectProc.running = true
  }

  function mergeInspected(items) {
    var next = root.pendingAttachments.slice()
    for (var i = 0; i < items.length; i++) {
      if (next.length >= root.maxPendingAttachments)
        break
      var item = items[i]
      if (!item || !item.path)
        continue
      var dup = false
      for (var j = 0; j < next.length; j++) {
        if (String(next[j].path) === String(item.path)) {
          dup = true
          break
        }
      }
      if (!dup)
        next.push(item)
    }
    root.pendingAttachments = next
    if (root.pendingAttachments.length > 0)
      root.statusLine = ""
  }

  function switchPanel(direction) {
    if (root.bar && typeof root.bar.switchPanelFrom === "function")
      return root.bar.switchPanelFrom(root.hostWidget || root, direction)
    return false
  }

  function reloadAll() {
    listProc.command = [root.ryokuBin, "history", "list", "--json"]
    listProc.running = true
  }

  function loadConversation(id) {
    if (!id || root.renameBusy)
      return
    root.renaming = false
    root.activeId = id
    root.messages = []
    showProc.command = [root.ryokuBin, "history", "show", id, "--json"]
    showProc.running = true
  }

  function startNew() {
    if (root.busy || root.renameBusy)
      return
    root.renaming = false
    // Cria conversa vazia no próximo envio com --new; limpa UI.
    root.activeId = ""
    root.messages = []
    root.statusLine = ""
    root.confirmDelete = false
  }

  function startRename() {
    if (!root.activeId || root.busy || root.renameBusy)
      return
    var title = ""
    for (var i = 0; i < root.conversations.length; i++) {
      var c = root.conversations[i]
      if (String(c.id) === root.activeId) {
        title = String(c.title || "")
        break
      }
    }
    root.renameDraft = title
    root.confirmDelete = false
    root.renaming = true
    Qt.callLater(function () {
      renameInput.forceActiveFocus()
      renameInput.selectAll()
    })
  }

  function cancelRename() {
    if (root.renameBusy)
      return
    root.renaming = false
    root.renameDraft = ""
    input.forceActiveFocus()
  }

  function saveRename() {
    var title = String(root.renameDraft || "").trim()
    if (!root.activeId || root.busy || root.renameBusy)
      return
    if (!title) {
      root.statusLine = strings.t("panel.renameEmpty")
      return
    }
    root.renameBusy = true
    root.statusLine = ""
    root.pendingRename = title + "\n"
    renameProc.command = [root.ryokuBin, "history", "rename", root.activeId, "--title-stdin"]
    renameProc.stdinEnabled = true
    renameProc.running = true
  }

  function sendMessage() {
    var text = String(root.draft || "").trim()
    if (text === "" || root.busy)
      return
    root.busy = true
    root.streamBuffer = ""
    root.statusLine = strings.t("panel.streaming")
    var label = text
    if (root.pendingAttachments.length > 0) {
      var names = []
      for (var i = 0; i < root.pendingAttachments.length; i++)
        names.push(String(root.pendingAttachments[i].filename || ""))
      label = text + "\n[" + strings.t("panel.attachments") + ": " + names.join(", ") + "]"
    }
    root.messages = root.messages.concat([{
          "role": "user",
          "content": label,
          "status": "complete"
        }, {
          "role": "assistant",
          "content": "",
          "status": "partial"
        }])
    root.draft = ""

    var paths = []
    for (var j = 0; j < root.pendingAttachments.length; j++)
      paths.push(String(root.pendingAttachments[j].path || ""))
    root.pendingPrompt = JSON.stringify({
      "prompt": text,
      "attachments": paths.map(function (p) {
        return {
          "path": p
        }
      })
    }) + "\n"
    root.clearAttachments()

    var cmd = [root.ryokuBin, "chat", "--jsonl", "--request-stdin"]
    if (root.activeId !== "")
      cmd = cmd.concat(["--conversation", root.activeId])
    else
      cmd = cmd.concat(["--new"])
    chatProc.command = cmd
    chatProc.stdinEnabled = true
    chatProc.running = true
    // Request JSON só é escrito quando o processo confirmar que iniciou.
  }

  function handleChatLine(line) {
    var raw = String(line).trim()
    if (raw === "")
      return
    var obj
    try {
      obj = JSON.parse(raw)
    } catch (e) {
      return
    }
    var event = obj.event
    if (event === "start" && obj.conversation_id) {
      root.activeId = String(obj.conversation_id)
      if (obj.truncated)
        root.statusLine = "Contexto truncado (" + obj.omitted + ")"
    } else if (event === "delta" && typeof obj.text === "string") {
      root.streamBuffer += obj.text
      if (root.messages.length > 0) {
        var copy = root.messages.slice()
        var last = Object.assign({}, copy[copy.length - 1])
        last.content = root.streamBuffer
        last.status = "partial"
        copy[copy.length - 1] = last
        root.messages = copy
      }
    } else if (event === "done") {
      root.busy = false
      root.statusLine = ""
      if (obj.conversation_id)
        root.activeId = String(obj.conversation_id)
      Qt.callLater(root.reloadAll)
      if (root.activeId !== "")
        Qt.callLater(function () {
          root.loadConversation(root.activeId)
        })
    } else if (event === "error") {
      root.busy = false
      root.loggedIn = obj.code !== "sign_in_required" && obj.code !== "sharing_not_enabled"
      root.statusLine = strings.t("panel.error") + ": " + String(obj.message || obj.code || "")
    }
  }

  function parseList(text) {
    try {
      var data = JSON.parse(text)
      if (Array.isArray(data)) {
        root.conversations = data
        root.loggedIn = true
        if (root.activeId === "" && data.length > 0)
          root.loadConversation(String(data[0].id))
      }
    } catch (e) {
      root.statusLine = strings.t("panel.loginRequired")
      root.loggedIn = false
    }
  }

  function parseShow(text) {
    try {
      var data = JSON.parse(text)
      if (data && data.conversation)
        root.activeId = String(data.conversation.id)
      root.messages = Array.isArray(data.messages) ? data.messages : []
    } catch (e) {
      root.statusLine = strings.t("panel.error")
    }
  }

  function doDelete() {
    if (root.activeId === "")
      return
    deleteProc.command = [root.ryokuBin, "history", "delete", root.activeId, "--yes"]
    deleteProc.running = true
  }

  Process {
    id: listProc
    running: false
    stdout: StdioCollector {
      onStreamFinished: root.parseList(this.text)
    }
    stderr: StdioCollector {
      onStreamFinished: {
        if (this.text && this.text.indexOf("login") >= 0) {
          root.loggedIn = false
          root.statusLine = strings.t("panel.loginRequired")
        }
      }
    }
  }

  Process {
    id: showProc
    running: false
    stdout: StdioCollector {
      onStreamFinished: root.parseShow(this.text)
    }
  }

  Process {
    id: chatProc
    running: false
    stdinEnabled: true
    onStarted: {
      // --prompt-stdin usa sys.stdin.read(): enviar newline não basta.
      // Fechar o canal libera EOF sem colocar a mensagem no argv.
      chatProc.write(root.pendingPrompt)
      root.pendingPrompt = ""
      chatProc.stdinEnabled = false
    }
    stdout: SplitParser {
      onRead: function (line) {
        root.handleChatLine(line)
      }
    }
    stderr: StdioCollector {
      onStreamFinished: {
        var detail = String(this.text || "").trim()
        if (detail !== "" && root.statusLine === strings.t("panel.streaming"))
          root.statusLine = strings.t("panel.error") + ": " + detail
      }
    }
    onExited: function (exitCode, exitStatus) {
      if (root.busy) {
        root.busy = false
        if (root.statusLine === strings.t("panel.streaming"))
          root.statusLine = strings.t("panel.error") + " (exit " + exitCode + ")"
      }
    }
  }

  Process {
    id: renameProc
    running: false
    stdinEnabled: true
    onStarted: {
      renameProc.write(root.pendingRename)
      root.pendingRename = ""
      renameProc.stdinEnabled = false
    }
    stderr: StdioCollector {
      onStreamFinished: {
        var detail = String(this.text || "").trim()
        if (detail !== "")
          root.statusLine = strings.t("panel.error") + ": " + detail
      }
    }
    onExited: function (exitCode, exitStatus) {
      root.renameBusy = false
      if (exitCode === 0) {
        root.renaming = false
        root.renameDraft = ""
        root.statusLine = ""
        root.reloadAll()
        input.forceActiveFocus()
      } else if (!root.statusLine) {
        root.statusLine = strings.t("panel.error") + " (exit " + exitCode + ")"
      }
    }
  }

  Process {
    id: deleteProc
    running: false
    stdout: StdioCollector {
      onStreamFinished: {
        root.confirmDelete = false
        root.activeId = ""
        root.messages = []
        root.reloadAll()
      }
    }
  }

  Process {
    id: inspectProc
    running: false
    stdinEnabled: true
    onStarted: {
      inspectProc.write(root.pendingInspect)
      root.pendingInspect = ""
      inspectProc.stdinEnabled = false
    }
    stdout: StdioCollector {
      onStreamFinished: {
        var raw = String(this.text || "").trim()
        if (raw === "")
          return
        var obj
        try {
          obj = JSON.parse(raw)
        } catch (e) {
          root.statusLine = strings.t("panel.attachError")
          return
        }
        if (!obj.ok) {
          var msg = (obj.error && obj.error.message) ? String(obj.error.message) : strings.t("panel.attachError")
          root.statusLine = msg
          return
        }
        root.mergeInspected(obj.attachments || [])
        if (obj.attachments && obj.attachments.length) {
          for (var i = 0; i < obj.attachments.length; i++) {
            if (obj.attachments[i].warning) {
              root.statusLine = String(obj.attachments[i].warning)
              break
            }
          }
        }
      }
    }
    stderr: StdioCollector {
      onStreamFinished: {
        var detail = String(this.text || "").trim()
        if (detail !== "")
          root.statusLine = strings.t("panel.error") + ": " + detail
      }
    }
    onExited: function (exitCode, exitStatus) {
      if (exitCode !== 0 && root.statusLine === strings.t("panel.attachInspecting"))
        root.statusLine = strings.t("panel.attachError")
    }
  }

  FileDialog {
    id: fileDialog
    title: strings.t("panel.attachTitle")
    fileMode: FileDialog.OpenFiles
    nameFilters: [
      strings.t("panel.attachFilterDocs") + " (*.txt *.md *.markdown *.log *.json *.csv *.tsv *.py *.js *.ts *.tsx *.jsx *.rs *.go *.java *.c *.h *.cpp *.hpp *.sh *.toml *.yaml *.yml *.xml *.html *.css *.sql *.qml *.pdf)",
      strings.t("panel.attachFilterAll") + " (*)"
    ]
    onAccepted: {
      var urls = fileDialog.selectedFiles
      var paths = []
      for (var i = 0; i < urls.length; i++)
        paths.push(root.urlToPath(urls[i]))
      root.queueAttachments(paths)
    }
  }

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.hostWidget || root
    bar: root.bar
    open: root.opened
    focusTarget: input
    contentWidth: panel.fittedContentWidth(Style.space(560))
    contentHeight: panel.fittedContentHeight(Style.space(460))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      blocked: input.activeFocus || renameInput.activeFocus
      onTabRequested: function (direction) {
        root.switchPanel(direction)
      }

      // Superfície única — sem cards internos.
      Rectangle {
        anchors.fill: parent
        color: theme.bg
        radius: theme.radiusNone

        ColumnLayout {
          anchors.fill: parent
          spacing: 0

          // ---- Barra superior
          Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: headerRow.implicitHeight + Style.space(16)
            color: theme.bg

            RowLayout {
              id: headerRow
              anchors.fill: parent
              anchors.leftMargin: Style.space(14)
              anchors.rightMargin: Style.space(10)
              anchors.topMargin: Style.space(8)
              anchors.bottomMargin: Style.space(8)
              spacing: Style.space(6)

              Text {
                textFormat: Text.PlainText
                text: "緑 " + strings.t("panel.title")
                color: theme.text
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.subtitle
                font.bold: true
                elide: Text.ElideRight
                Layout.fillWidth: true
              }

              Text {
                visible: root.busy
                textFormat: Text.PlainText
                text: strings.t("panel.streaming")
                color: theme.gold
                font.pixelSize: Style.font.caption
              }

              Button {
                text: strings.t("panel.new")
                bordered: true
                foreground: theme.gold
                accent: theme.gold
                background: "transparent"
                horizontalPadding: Style.space(10)
                verticalPadding: Style.space(6)
                enabled: !root.busy && !root.renameBusy
                onClicked: root.startNew()
              }

              Button {
                text: strings.t("panel.refresh")
                bordered: true
                foreground: theme.textMuted
                accent: theme.gold
                background: "transparent"
                horizontalPadding: Style.space(10)
                verticalPadding: Style.space(6)
                enabled: !root.busy && !root.renameBusy
                onClicked: root.reloadAll()
              }

              Button {
                text: strings.t("panel.rename")
                bordered: true
                foreground: theme.gold
                accent: theme.gold
                background: "transparent"
                horizontalPadding: Style.space(10)
                verticalPadding: Style.space(6)
                enabled: root.activeId !== "" && !root.busy && !root.renameBusy
                onClicked: root.startRename()
              }

              Button {
                text: strings.t("panel.delete")
                bordered: true
                foreground: theme.danger
                accent: theme.danger
                background: "transparent"
                horizontalPadding: Style.space(10)
                verticalPadding: Style.space(6)
                enabled: root.activeId !== "" && !root.busy && !root.renameBusy
                onClicked: root.confirmDelete = true
              }
            }
          }

          Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: theme.dividerWidth
            color: theme.divider
          }

          Text {
            Layout.fillWidth: true
            Layout.leftMargin: Style.space(14)
            Layout.rightMargin: Style.space(14)
            Layout.topMargin: Style.space(6)
            Layout.bottomMargin: Style.space(6)
            visible: root.statusLine !== "" || !root.loggedIn
            textFormat: Text.PlainText
            wrapMode: Text.WordWrap
            color: !root.loggedIn || root.statusLine.indexOf(strings.t("panel.error")) === 0
              ? theme.danger
              : theme.textMuted
            font.pixelSize: Style.font.caption
            text: !root.loggedIn ? strings.t("panel.loginRequired") : root.statusLine
          }

          // ---- Corpo: sidebar | chat (divisória vertical)
          RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // Sidebar integrada — nasce da borda, sem card.
            Item {
              id: sidebar
              Layout.preferredWidth: theme.sidebarWidth
              Layout.minimumWidth: Style.space(132)
              Layout.maximumWidth: Style.space(200)
              Layout.fillHeight: true
              clip: true

              ColumnLayout {
                anchors.fill: parent
                anchors.topMargin: Style.space(10)
                anchors.bottomMargin: Style.space(8)
                anchors.leftMargin: Style.space(10)
                anchors.rightMargin: Style.space(8)
                spacing: Style.space(8)

                Text {
                  Layout.fillWidth: true
                  textFormat: Text.PlainText
                  text: strings.t("panel.conversations")
                  color: theme.textMuted
                  font.pixelSize: Style.font.caption
                  font.bold: true
                }

                ListView {
                  id: convList
                  Layout.fillWidth: true
                  Layout.fillHeight: true
                  clip: true
                  model: root.conversations
                  spacing: 0
                  boundsBehavior: Flickable.StopAtBounds
                  delegate: Item {
                    width: convList.width
                    height: Style.space(34)
                    required property var modelData
                    property bool selected: String(modelData.id) === root.activeId
                    property bool hovered: convMouse.containsMouse

                    Rectangle {
                      anchors.fill: parent
                      color: selected ? theme.selectedFill : (hovered ? theme.surface : "transparent")
                      radius: theme.radiusNone

                      // Barra dourada discreta na conversa ativa.
                      Rectangle {
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        width: 2
                        visible: selected
                        color: theme.gold
                      }

                      MouseArea {
                        id: convMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: root.loadConversation(String(modelData.id))
                      }

                      Text {
                        anchors.fill: parent
                        anchors.leftMargin: Style.space(10)
                        anchors.rightMargin: Style.space(6)
                        verticalAlignment: Text.AlignVCenter
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        color: selected ? theme.gold : theme.text
                        font.pixelSize: Style.font.caption
                        text: String(modelData.title || modelData.id)
                      }
                    }
                  }
                }
              }
            }

            Rectangle {
              Layout.preferredWidth: theme.dividerWidth
              Layout.fillHeight: true
              color: theme.divider
            }

            // Área principal do chat — fundo contínuo.
            Item {
              id: messagePane
              Layout.fillWidth: true
              Layout.fillHeight: true
              clip: true

              ListView {
                id: msgList
                anchors.fill: parent
                anchors.margins: Style.space(14)
                clip: true
                model: root.messages
                spacing: Style.space(12)
                boundsBehavior: Flickable.StopAtBounds
                visible: root.messages.length > 0
                onCountChanged: Qt.callLater(function () {
                  msgList.positionViewAtEnd()
                })

                delegate: Item {
                  width: msgList.width
                  height: bubbleCol.height
                  required property var modelData
                  readonly property bool isUser: String(modelData.role) === "user"
                  readonly property bool isPartial: String(modelData.status) === "partial"
                  readonly property real bubbleWidth: Math.min(msgList.width * theme.bubbleMaxRatio, msgList.width)

                  Column {
                    id: bubbleCol
                    width: bubbleWidth
                    anchors.right: isUser ? parent.right : undefined
                    anchors.left: isUser ? undefined : parent.left
                    spacing: Style.space(3)

                    Text {
                      width: parent.width
                      horizontalAlignment: isUser ? Text.AlignRight : Text.AlignLeft
                      textFormat: Text.PlainText
                      color: isUser ? theme.textMuted : theme.gold
                      font.pixelSize: Style.font.caption
                      text: isUser ? strings.t("panel.you") : strings.t("panel.assistant")
                    }

                    Rectangle {
                      width: parent.width
                      height: bodyText.implicitHeight + Style.space(14)
                      color: isUser ? theme.userBubble : theme.assistantTint
                      radius: theme.radiusSm

                      Text {
                        id: bodyText
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: Style.space(8)
                        textFormat: Text.PlainText
                        wrapMode: Text.Wrap
                        color: theme.text
                        opacity: isPartial && String(modelData.content || "") === "" ? 0.55 : 1
                        font.pixelSize: Style.font.body
                        text: String(modelData.content || (isPartial ? "…" : ""))
                      }
                    }
                  }
                }
              }

              Column {
                id: emptyState
                anchors.centerIn: parent
                width: Math.min(parent.width - Style.space(40), Style.space(360))
                spacing: Style.space(8)
                visible: root.messages.length === 0 && root.loggedIn

                Text {
                  width: parent.width
                  horizontalAlignment: Text.AlignHCenter
                  textFormat: Text.PlainText
                  wrapMode: Text.WordWrap
                  color: theme.gold
                  font.pixelSize: Style.font.subtitle
                  font.bold: true
                  text: strings.t("panel.emptyBrand")
                }

                Text {
                  width: parent.width
                  horizontalAlignment: Text.AlignHCenter
                  textFormat: Text.PlainText
                  wrapMode: Text.WordWrap
                  color: theme.text
                  font.pixelSize: Style.font.body
                  text: strings.t("panel.emptyHeadline")
                }

                Text {
                  width: parent.width
                  horizontalAlignment: Text.AlignHCenter
                  textFormat: Text.PlainText
                  wrapMode: Text.WordWrap
                  color: theme.textMuted
                  font.pixelSize: Style.font.caption
                  text: strings.t("panel.emptySubtext")
                }
              }
            }
          }

          // ---- Faixa contextual (rename / delete) — flat, sem card
          ColumnLayout {
            Layout.fillWidth: true
            spacing: 0
            visible: root.renaming || root.confirmDelete

            Rectangle {
              Layout.fillWidth: true
              Layout.preferredHeight: theme.dividerWidth
              color: theme.divider
            }

            RowLayout {
              Layout.fillWidth: true
              Layout.leftMargin: Style.space(12)
              Layout.rightMargin: Style.space(12)
              Layout.topMargin: Style.space(8)
              Layout.bottomMargin: Style.space(8)
              spacing: Style.space(8)
              visible: root.renaming

              TextField {
                id: renameInput
                Layout.fillWidth: true
                placeholderText: strings.t("panel.renamePlaceholder")
                text: root.renameDraft
                enabled: !root.renameBusy
                foreground: theme.text
                accent: theme.gold
                onTextChanged: root.renameDraft = text
                background: Rectangle {
                  color: theme.bg
                  radius: theme.radiusNone
                  border.width: 1
                  border.color: renameInput.activeFocus ? theme.gold : theme.divider
                }
                Keys.onEscapePressed: function (event) {
                  event.accepted = true
                  root.cancelRename()
                }
                Keys.onReturnPressed: function (event) {
                  event.accepted = true
                  root.saveRename()
                }
              }

              Button {
                text: strings.t("panel.renameSave")
                bordered: true
                foreground: theme.gold
                accent: theme.gold
                background: "transparent"
                enabled: !root.renameBusy && String(root.renameDraft).trim() !== ""
                onClicked: root.saveRename()
              }

              Button {
                text: strings.t("panel.renameCancel")
                bordered: true
                foreground: theme.textMuted
                accent: theme.gold
                background: "transparent"
                enabled: !root.renameBusy
                onClicked: root.cancelRename()
              }
            }

            RowLayout {
              Layout.fillWidth: true
              Layout.leftMargin: Style.space(12)
              Layout.rightMargin: Style.space(12)
              Layout.topMargin: Style.space(8)
              Layout.bottomMargin: Style.space(8)
              spacing: Style.space(8)
              visible: root.confirmDelete

              Text {
                Layout.fillWidth: true
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
                color: theme.text
                text: strings.t("panel.deleteConfirm")
              }

              Button {
                text: strings.t("panel.deleteYes")
                bordered: true
                foreground: theme.danger
                accent: theme.danger
                background: "transparent"
                onClicked: root.doDelete()
              }

              Button {
                text: strings.t("panel.deleteNo")
                bordered: true
                foreground: theme.textMuted
                accent: theme.gold
                background: "transparent"
                onClicked: root.confirmDelete = false
              }
            }
          }

          // ---- Composer inferior — faixa de anexos + linha + input
          Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: theme.dividerWidth
            color: theme.divider
          }

          Flow {
            Layout.fillWidth: true
            Layout.leftMargin: Style.space(12)
            Layout.rightMargin: Style.space(12)
            Layout.topMargin: Style.space(6)
            Layout.bottomMargin: Style.space(2)
            spacing: Style.space(6)
            visible: root.pendingAttachments.length > 0

            Repeater {
              model: root.pendingAttachments

              RowLayout {
                spacing: Style.space(4)

                Text {
                  textFormat: Text.PlainText
                  color: theme.gold
                  font.pixelSize: Style.font.caption
                  text: {
                    var name = String(modelData.filename || "")
                    var ext = String(modelData.extension || "").replace(".", "").toUpperCase()
                    var size = root.formatBytes(modelData.size_bytes)
                    var mark = modelData.truncated ? " · " + strings.t("panel.attachTruncated") : ""
                    return name + " · " + ext + " · " + size + mark
                  }
                }

                Button {
                  text: "×"
                  tooltipText: strings.t("panel.attachRemove")
                  bordered: false
                  foreground: theme.danger
                  accent: theme.danger
                  background: "transparent"
                  enabled: !root.busy
                  onClicked: root.removeAttachment(index)
                }
              }
            }
          }

          RowLayout {
            id: composerRow
            Layout.fillWidth: true
            Layout.preferredHeight: Style.space(52)
            Layout.leftMargin: Style.space(12)
            Layout.rightMargin: Style.space(10)
            spacing: Style.space(8)

            Button {
              Layout.alignment: Qt.AlignVCenter
              text: "+"
              tooltipText: strings.t("panel.attach")
              bordered: true
              foreground: enabled ? theme.gold : theme.textMuted
              accent: theme.gold
              background: "transparent"
              enabled: !root.busy && !root.renameBusy && root.loggedIn
              onClicked: root.openFilePicker()
            }

            TextField {
              id: input
              Layout.fillWidth: true
              Layout.alignment: Qt.AlignVCenter
              placeholderText: strings.t("panel.inputPlaceholder")
              text: root.draft
              enabled: !root.busy && !root.renameBusy && root.loggedIn
              foreground: theme.text
              accent: theme.gold
              onTextChanged: root.draft = text
              background: Rectangle {
                color: theme.bg
                radius: theme.radiusNone
                border.width: 1
                border.color: input.activeFocus ? theme.gold : theme.divider
                opacity: input.enabled ? 1 : 0.5
              }
              Keys.onEscapePressed: function (event) {
                event.accepted = true
                root.close()
              }
              Keys.onReturnPressed: function (event) {
                if (event.modifiers & Qt.ShiftModifier) {
                  event.accepted = false
                  return
                }
                event.accepted = true
                root.sendMessage()
              }
            }

            Button {
              Layout.alignment: Qt.AlignVCenter
              iconText: "󰁝"
              text: strings.t("panel.send")
              tooltipText: strings.t("panel.send")
              bordered: true
              foreground: enabled ? theme.gold : theme.textMuted
              accent: theme.gold
              background: "transparent"
              enabled: !root.busy && !root.renameBusy && root.loggedIn && String(root.draft).trim() !== ""
              onClicked: root.sendMessage()
            }
          }
        }
      }
    }
  }
}
