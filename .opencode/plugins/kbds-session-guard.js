import { createHash } from "node:crypto"
import { readFile, realpath, stat } from "node:fs/promises"
import path from "node:path"

// OpenCode 1.18.35 hooks. This controls agent loops, not filesystem permissions.
const agents = new Set(["kbds-review", "kbds-stage"])
const reference = /^(?:AGENTS\.md|skills\/kbds-data-organizer\/(?:SKILL\.md|references\/[a-z0-9-]+\.md))$/
// Deliberately accept canonical single commands, not the shell language.
const absolute = String.raw`(?:'/[^']*'|"/[^"$\x60\\]*"|/[^\s'"$\x60;&|<>()\\*?{}\[\]~!#]+)`
const name = String.raw`[A-Za-z0-9][A-Za-z0-9_.-]*`
const command = suffix => new RegExp(`^python3 scripts/kbds\\.py ${suffix} *$`)
const runCommand = command(`run --scope ${absolute} --approve-scope [a-f0-9]{64} --name ${name}(?: --language (?:ko|en))?`)
const applyCommand = command(`--policy ${absolute} apply --plan ${absolute} --approve-plan [a-f0-9]{64}`)
const reportCommand = command(`report --plan ${absolute}(?: --language (?:ko|en))?`)
const commands = [runCommand, applyCommand, reportCommand, command("self-check"),
  command(`--policy ${absolute} inventory(?: --summary)?`),
  command(`--policy ${absolute} plan --name ${name}(?: --decisions ${absolute})?`),
  command(`--policy ${absolute} verify --plan ${absolute}`), command(`run --scope ${absolute} --inspect`)]
const canonicalCommand = value => typeof value === "string" && !/[\x00-\x1f\x7f]/.test(value) && commands.some(pattern => pattern.test(value))

function actualPrompt(message) {
  return message.info?.role === "user" && message.parts?.some(
    part => ["text", "file"].includes(part.type) && !part.synthetic && !part.ignored,
  )
}

function completion(args, result) {
  if (result.metadata?.exit !== 0 || typeof result.output !== "string") return
  const command = args?.command || ""
  if (!canonicalCommand(command) || (!runCommand.test(command) && !reportCommand.test(command))) return
  const lines = result.output.trim().split(/\r?\n/)
  const records = lines.flatMap(line => {
    try { return [JSON.parse(line)] } catch { return [] }
  })
  if (runCommand.test(command)) {
    const value = records.findLast(item => item && item.status === "COMPLETE" && item.copied === true &&
      item.metadata_verified === true && /^[a-f0-9]{64}$/.test(item.plan_sha256 || "") &&
      typeof item.report_path === "string" && item.report_path.startsWith("/") && item.report_path.endsWith("/report.html"))
    if (value) return { report_path: value.report_path, plan_sha256: value.plan_sha256 }
  } else if (records.some(item => item?.event === "VERIFIED" && item.submission_ready === false)) {
    const report = lines.at(-1)
    if (report.startsWith("/") && report.endsWith("/report.html")) return { report_path: report }
  }
}

export default async function KBDSStateGuard({ client, directory }) {
  const root = await realpath(directory)
  const project = {
    project_root: root,
    control_paths: {
      policy: path.join(root, "config/policy.local.json"),
      decisions: path.join(root, "config/decisions.local.json"),
    },
  }
  // Keep the initial system prefix stable so local models can reuse its KV cache.
  const systemRules = "KBDS runtime rules (not approval): " + JSON.stringify({
    ...project,
    next_action: "Continue the current authorized step. Reuse unchanged references; do not restart discovery. After a successful verified run/report result, give the final chat answer and stop calling tools. No new approval is granted.",
  })
  const sessions = new Map()
  const pending = new Map()

  async function history(sessionID) {
    const result = await client.session.messages({ path: { id: sessionID }, query: { directory } })
    if (result.error || !Array.isArray(result.data)) throw new Error("KBDS_GUARD_HISTORY_UNAVAILABLE: stop and reconnect; no task state was assumed.")
    return result.data
  }

  function consume(state, message) {
    if (actualPrompt(message)) {
      state.agent = message.info.agent
      state.phase = message.info.id
      state.complete = undefined
      state.stopped = false
    }
    if (message.info?.role !== "assistant" || message.info.summary) return
    if (!agents.has(state.agent)) return
    state.stopped = message.info.finish === "stop" && !message.info.error
    for (const part of message.parts || []) {
      if (part.type !== "tool" || part.state?.status !== "completed") continue
      const saved = part.state.metadata?.kbds_reference
      if (saved && reference.test(saved.file) && /^[a-f0-9]{64}$/.test(saved.sha256) &&
          Number.isSafeInteger(saved.from) && Number.isSafeInteger(saved.to)) {
        state.reads.push(saved)
      }
      if (part.tool === "bash") state.complete = completion(part.state.input, part.state) || state.complete
    }
  }

  async function stateFor(sessionID) {
    if (!sessions.has(sessionID)) {
      const loading = history(sessionID).then(messages => {
        const state = { reads: [], stopped: false }
        for (const message of messages) consume(state, message)
        return state
      })
      sessions.set(sessionID, loading)
      loading.catch(() => sessions.delete(sessionID))
    }
    return sessions.get(sessionID)
  }

  async function snapshot(tool, args) {
    const filePath = tool === "skill" && args.name === "kbds-data-organizer"
      ? path.join(root, "skills/kbds-data-organizer/SKILL.md")
      : tool === "read" && typeof args.filePath === "string" ? path.resolve(directory, args.filePath) : undefined
    if (!filePath) return
    const file = [root, path.resolve(directory)].map(base => path.relative(base, filePath).split(path.sep).join("/"))
      .find(candidate => reference.test(candidate))
    if (!file) return
    try {
      // Only bundled references are read by this hook; never follow them outside the project.
      if (await realpath(filePath) !== path.join(root, ...file.split("/"))) return
      const info = await stat(filePath)
      if (!info.isFile() || info.size > 256 * 1024) return
      const bytes = await readFile(filePath)
      const text = bytes.toString("utf8")
      const lines = text.split("\n").length - Number(text.endsWith("\n"))
      const from = tool === "skill" ? 1 : args.offset || 1
      const to = tool === "skill" ? lines : Math.min(lines, from + (args.limit ?? 2000) - 1)
      return { file, sha256: createHash("sha256").update(bytes).digest("hex"), from, to }
    } catch { return }
  }

  function checkpoint(state) {
    const read = [...new Set(state.reads.map(item => `${item.file}:${item.from}-${item.to}`))].slice(-20)
    return "KBDS runtime checkpoint (tool observations, not approval): " + JSON.stringify({
      status: state.complete ? "VERIFIED_REPORT_COMPLETE" : "ACTIVE",
      ...project,
      ...(state.complete || {}), references_read: read,
      next_action: state.complete ? "Give the final chat answer and stop. Do not call tools or restart staging."
        : "Continue the current authorized step. Reuse unchanged references; do not restart discovery. No new approval is granted.",
    })
  }

  return {
    "chat.message": async (input, output) => {
      if (!actualPrompt({ info: output.message, parts: output.parts })) return
      const state = await stateFor(input.sessionID)
      state.agent = input.agent || output.message.agent
      state.phase = output.message.id
      state.complete = undefined
      state.stopped = false
    },
    "tool.execute.before": async (input, output) => {
      const state = await stateFor(input.sessionID)
      if (!agents.has(state.agent)) return
      if (state.complete) throw new Error("KBDS_TASK_COMPLETE: verified report already exists. Give the final chat answer and stop; a new user request is needed for more tools.")
      if (input.tool === "bash") {
        if (state.agent !== "kbds-stage" || !canonicalCommand(output.args.command)) {
          throw new Error("KBDS_COMMAND_BLOCKED: use one documented python3 scripts/kbds.py command with absolute control paths. No shell operators, expansion, wrappers or redirection.")
        }
        if (output.args.workdir && await realpath(path.resolve(directory, output.args.workdir)) !== root) {
          throw new Error("KBDS_COMMAND_BLOCKED: bundled commands must run from this toolkit project root.")
        }
      }
      if (input.tool === "bash" && (runCommand.test(output.args.command || "") || applyCommand.test(output.args.command || ""))) {
        const timeout = output.args.timeout
        output.args.timeout = Number.isFinite(timeout) && timeout >= 600000 ? timeout : 600000
      }
      const current = await snapshot(input.tool, output.args)
      if (!current) return
      if (state.reads.some(item => item.phase === state.phase && item.file === current.file &&
          item.sha256 === current.sha256 && item.from <= current.from && item.to >= current.to)) {
        throw new Error(`KBDS_REFERENCE_ALREADY_READ: ${current.file}:${current.from}-${current.to} is unchanged and was read in this task step. Continue the next authorized action. Do not retry this read.`)
      }
      pending.set(`${input.sessionID}:${input.callID}`, { ...current, phase: state.phase })
    },
    "tool.execute.after": async (input, output) => {
      const state = await stateFor(input.sessionID)
      if (!agents.has(state.agent)) return
      state.stopped = false
      const key = `${input.sessionID}:${input.callID}`
      const before = pending.get(key)
      pending.delete(key)
      if (before) {
        const current = await snapshot(input.tool, input.args)
        const display = output.metadata?.display
        if (current?.sha256 === before.sha256 && (input.tool === "skill" || display?.type === "file")) {
          const saved = input.tool === "skill" ? before : { ...before, from: display.lineStart, to: display.lineEnd }
          state.reads.push(saved)
          output.metadata = { ...output.metadata, kbds_reference: saved }
        }
      }
      if (input.tool === "bash") state.complete = completion(input.args, output) || state.complete
    },
    "experimental.chat.system.transform": async (input, output) => {
      if (!input.sessionID) return
      const state = await stateFor(input.sessionID)
      if (agents.has(state.agent)) {
        // Local chat templates may accept exactly one initial system message.
        output.system.splice(0, output.system.length, [...output.system, systemRules].join("\n\n"))
      }
    },
    "experimental.session.compacting": async (input, output) => {
      const state = await stateFor(input.sessionID)
      if (agents.has(state.agent)) output.context.push(checkpoint(state))
    },
    "experimental.compaction.autocontinue": async (input, output) => {
      if (!agents.has(input.agent)) return
      // Inspect persisted finish markers, not the model's summary of an older prefix.
      const messages = await history(input.sessionID)
      const state = { reads: [], stopped: false }
      for (const message of messages) consume(state, message)
      if (state.stopped) output.enabled = false
    },
    event: async ({ event }) => {
      if (event.type === "session.deleted") sessions.delete(event.properties.info.id)
    },
    dispose: async () => { sessions.clear(); pending.clear() },
  }
}
