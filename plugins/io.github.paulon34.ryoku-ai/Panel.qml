import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Commons as Commons
import qs.Ui

// Painel Ryoku: fala só com o CLI (argv estático + stdin). Sem tokens no QML.
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
  property string streamBuffer: ""
  property string pendingPrompt: ""
  property bool loggedIn: true

  readonly property string ryokuBin: "ryoku"

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
    root.controller.hide()
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
    if (!id)
      return
    root.activeId = id
    root.messages = []
    showProc.command = [root.ryokuBin, "history", "show", id, "--json"]
    showProc.running = true
  }

  function startNew() {
    if (root.busy)
      return
    // Cria conversa vazia no próximo envio com --new; limpa UI.
    root.activeId = ""
    root.messages = []
    root.statusLine = ""
    root.confirmDelete = false
  }

  function sendMessage() {
    var text = String(root.draft || "").trim()
    if (text === "" || root.busy)
      return
    root.busy = true
    root.streamBuffer = ""
    root.statusLine = strings.t("panel.streaming")
    root.messages = root.messages.concat([{
          "role": "user",
          "content": text,
          "status": "complete"
        }, {
          "role": "assistant",
          "content": "",
          "status": "partial"
        }])
    root.draft = ""
    root.pendingPrompt = text + "\n"

    var cmd = [root.ryokuBin, "chat", "--jsonl", "--prompt-stdin"]
    if (root.activeId !== "")
      cmd = cmd.concat(["--conversation", root.activeId])
    else
      cmd = cmd.concat(["--new"])
    chatProc.command = cmd
    chatProc.stdinEnabled = true
    chatProc.running = true
    // Prompt só será escrito quando o processo confirmar que iniciou.
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

  KeyboardPanel {
    id: panel
    anchorItem: root.anchorItem
    owner: root.hostWidget || root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(520))
    contentHeight: panel.fittedContentHeight(Style.space(420))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      blocked: input.activeFocus
      onTabRequested: function (direction) {
        root.switchPanel(direction)
      }

      Rectangle {
        anchors.fill: parent
        color: "transparent"

        ColumnLayout {
          anchors.fill: parent
          anchors.margins: Style.space(10)
          spacing: Style.space(8)

          RowLayout {
            Layout.fillWidth: true
            spacing: Style.space(8)

            Text {
              textFormat: Text.PlainText
              text: "緑 " + strings.t("panel.title")
              color: root.barForeground
              font.family: root.bar ? root.bar.fontFamily : Style.font.family
              font.pixelSize: Style.font.subtitle
              font.bold: true
              Layout.fillWidth: true
            }

            Button {
              text: strings.t("panel.new")
              enabled: !root.busy
              onClicked: root.startNew()
            }

            Button {
              text: strings.t("panel.refresh")
              enabled: !root.busy
              onClicked: root.reloadAll()
            }

            Button {
              text: strings.t("panel.delete")
              enabled: root.activeId !== "" && !root.busy
              onClicked: root.confirmDelete = true
            }
          }

          Text {
            Layout.fillWidth: true
            visible: root.statusLine !== "" || !root.loggedIn
            textFormat: Text.PlainText
            wrapMode: Text.WordWrap
            color: root.barForeground
            opacity: 0.85
            font.pixelSize: Style.font.caption
            text: !root.loggedIn ? strings.t("panel.loginRequired") : root.statusLine
          }

          RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Style.space(8)

            // Lista de conversas
            ListView {
              id: convList
              Layout.preferredWidth: Style.space(150)
              Layout.fillHeight: true
              clip: true
              model: root.conversations
              spacing: Style.space(4)
              delegate: Item {
                width: convList.width
                height: Style.space(36)
                required property var modelData
                Rectangle {
                  anchors.fill: parent
                  radius: Style.space(6)
                  color: String(modelData.id) === root.activeId ? Qt.rgba(1, 1, 1, 0.12) : "transparent"
                  MouseArea {
                    anchors.fill: parent
                    onClicked: root.loadConversation(String(modelData.id))
                  }
                  Text {
                    anchors.fill: parent
                    anchors.margins: Style.space(6)
                    textFormat: Text.PlainText
                    elide: Text.ElideRight
                    color: root.barForeground
                    font.pixelSize: Style.font.caption
                    text: String(modelData.title || modelData.id)
                  }
                }
              }
            }

            // Mensagens
            ListView {
              id: msgList
              Layout.fillWidth: true
              Layout.fillHeight: true
              clip: true
              model: root.messages
              spacing: Style.space(8)
              delegate: Column {
                width: msgList.width
                required property var modelData
                spacing: Style.space(2)
                Text {
                  width: parent.width
                  textFormat: Text.PlainText
                  color: root.barForeground
                  opacity: 0.6
                  font.pixelSize: Style.font.caption
                  text: String(modelData.role || "")
                }
                Text {
                  width: parent.width
                  textFormat: Text.PlainText
                  wrapMode: Text.Wrap
                  color: root.barForeground
                  font.pixelSize: Style.font.body
                  text: String(modelData.content || "")
                }
              }

              Text {
                anchors.centerIn: parent
                visible: root.messages.length === 0
                textFormat: Text.PlainText
                color: root.barForeground
                opacity: 0.7
                text: strings.t("panel.empty")
              }
            }
          }

          // Confirmação de exclusão
          RowLayout {
            Layout.fillWidth: true
            visible: root.confirmDelete
            spacing: Style.space(8)
            Text {
              Layout.fillWidth: true
              textFormat: Text.PlainText
              wrapMode: Text.WordWrap
              color: root.barForeground
              text: strings.t("panel.deleteConfirm")
            }
            Button {
              text: strings.t("panel.deleteYes")
              onClicked: root.doDelete()
            }
            Button {
              text: strings.t("panel.deleteNo")
              onClicked: root.confirmDelete = false
            }
          }

          RowLayout {
            Layout.fillWidth: true
            spacing: Style.space(8)

            TextField {
              id: input
              Layout.fillWidth: true
              placeholderText: strings.t("panel.inputPlaceholder")
              text: root.draft
              enabled: !root.busy && root.loggedIn
              onTextChanged: root.draft = text
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
              text: strings.t("panel.send")
              enabled: !root.busy && root.loggedIn && String(root.draft).trim() !== ""
              onClicked: root.sendMessage()
            }
          }
        }
      }
    }
  }
}
