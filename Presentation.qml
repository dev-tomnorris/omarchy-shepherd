import QtQuick
import qs.Commons

// Shared presentation sanitize + Omarchy launch planning.
// Quotes via installed Util.shellQuote; launches via bar.run only.
// No Process, no logging of descriptors/commands, no Herdr I/O.
QtObject {
  id: root

  readonly property int cooldownMs: 3000
  readonly property string manualOpenMessage: "Open Herdr manually for this session."
  readonly property string unableOpenMessage: "Unable to open Herdr."
  readonly property var appIdPattern: /^org\.omarchy\.herdr\.session-[a-f0-9]{12}$/

  function unsupportedDescriptor() {
    return {
      kind: "socket_override",
      supported: false,
      app_id: "",
      argv: []
    }
  }

  function nonemptyString(value) {
    return typeof value === "string" && value.trim() !== ""
  }

  function ownKeys(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return []
    return Object.keys(value)
  }

  function exactKeySet(value) {
    var keys = ownKeys(value)
    if (keys.length !== 4) return false
    var required = {
      kind: true,
      supported: true,
      app_id: true,
      argv: true
    }
    for (var i = 0; i < keys.length; i++) {
      if (!required[keys[i]]) return false
    }
    return true
  }

  function copyArgv(argv) {
    var out = []
    if (!Array.isArray(argv)) return out
    for (var i = 0; i < argv.length; i++) out.push(argv[i])
    return out
  }

  function sanitize(value) {
    if (!value || typeof value !== "object" || Array.isArray(value))
      return unsupportedDescriptor()
    if (!exactKeySet(value))
      return unsupportedDescriptor()

    var kind = value.kind
    var supported = value.supported
    var appId = value.app_id
    var argv = value.argv

    if (typeof kind !== "string") return unsupportedDescriptor()
    if (supported !== true && supported !== false) return unsupportedDescriptor()
    if (typeof appId !== "string") return unsupportedDescriptor()
    if (!Array.isArray(argv)) return unsupportedDescriptor()
    for (var i = 0; i < argv.length; i++) {
      if (typeof argv[i] !== "string") return unsupportedDescriptor()
    }

    if (kind === "default") {
      if (supported !== true) return unsupportedDescriptor()
      if (appId !== "org.omarchy.herdr") return unsupportedDescriptor()
      if (argv.length !== 1 || argv[0] !== "herdr") return unsupportedDescriptor()
    } else if (kind === "named") {
      if (supported !== true) return unsupportedDescriptor()
      if (!root.appIdPattern.test(appId)) return unsupportedDescriptor()
      if (argv.length !== 3) return unsupportedDescriptor()
      if (argv[0] !== "herdr" || argv[1] !== "--session") return unsupportedDescriptor()
      // Match Python/helper truthiness: whitespace-only remains nonempty.
      if (argv[2] === "") return unsupportedDescriptor()
    } else if (kind === "socket_override") {
      if (supported !== false) return unsupportedDescriptor()
      if (appId !== "") return unsupportedDescriptor()
      if (argv.length !== 0) return unsupportedDescriptor()
    } else {
      return unsupportedDescriptor()
    }

    return {
      kind: kind,
      supported: supported,
      app_id: appId,
      argv: copyArgv(argv)
    }
  }

  // serviceGate: { connection, stale, helperCrashed, fixtureMode, presentation }
  // Returns { launched, errorMessage, command }. Never throws; never logs.
  function presentAfterFocus(bar, serviceGate) {
    var empty = { launched: false, errorMessage: "", command: "" }
    if (!serviceGate) return empty
    if (serviceGate.fixtureMode === true) return empty
    if (serviceGate.connection !== "connected") return empty
    if (serviceGate.stale === true) return empty
    if (serviceGate.helperCrashed === true) return empty

    var desc = sanitize(serviceGate.presentation)
    if (desc.supported !== true) {
      return {
        launched: false,
        errorMessage: root.manualOpenMessage,
        command: ""
      }
    }

    if (!bar || typeof bar.run !== "function") {
      return {
        launched: false,
        errorMessage: root.unableOpenMessage,
        command: ""
      }
    }

    var tokens = [
      "omarchy-launch-or-focus-tui",
      "--app-id=" + desc.app_id
    ]
    for (var i = 0; i < desc.argv.length; i++)
      tokens.push(desc.argv[i])

    var quoted = []
    for (var j = 0; j < tokens.length; j++)
      quoted.push(Util.shellQuote(tokens[j]))
    var command = quoted.join(" ")

    try {
      bar.run(command)
    } catch (e) {
      return {
        launched: false,
        errorMessage: root.unableOpenMessage,
        command: ""
      }
    }

    return {
      launched: true,
      errorMessage: "",
      command: command
    }
  }
}
