import assert from "node:assert/strict"
import { mkdtemp, mkdir, readFile, realpath, rm, writeFile } from "node:fs/promises"
import os from "node:os"
import path from "node:path"
import test from "node:test"
import guard from "../.opencode/plugins/kbds-session-guard.js"

const hash = "a".repeat(64)
const run = `python3 scripts/kbds.py run --scope '/approved space/scope.json' --approve-scope ${hash} --name job-001`
const complete = {
  status: "COMPLETE", copied: true, metadata_verified: true,
  plan_sha256: hash, report_path: "/approved space/job-001/report.html",
}
const user = id => ({ info: { role: "user", id, agent: "kbds-stage" }, parts: [{ type: "text", text: "Perform approved task" }] })
const result = (value = complete, exit = 0) => ({ output: JSON.stringify(value), metadata: { exit } })
const toolPart = (args, output) => ({ type: "tool", tool: "bash", state: { status: "completed", input: args, ...output } })
const assistant = (parts = [], finish = "tool-calls", extra = {}) => ({
  info: { role: "assistant", finish, ...extra }, parts,
})

async function fixture(t, messages = [user("first")]) {
  const directory = await mkdtemp(path.join(os.tmpdir(), "kbds-guard-"))
  await mkdir(path.join(directory, "skills/kbds-data-organizer/references"), { recursive: true })
  await writeFile(path.join(directory, "skills/kbds-data-organizer/SKILL.md"), "# Skill\nLoad needed references.\n")
  const ref = path.join(directory, "skills/kbds-data-organizer/references/safety-policy.md")
  await writeFile(ref, "line one\nline two\nline three\nline four")
  const state = { messages, calls: 0, error: false }
  const hooks = await guard({ directory, client: { session: { messages: async () => {
    state.calls++
    return state.error ? { error: "offline" } : { data: state.messages }
  } } } })
  t.after(async () => { await hooks.dispose(); await rm(directory, { recursive: true, force: true }) })
  return { directory, ref, state, hooks }
}

async function read(hooks, filePath, { from = 1, to = 2, sessionID = "one", callID = "read-1" } = {}) {
  const input = { tool: "read", sessionID, callID }
  const args = { filePath, offset: from, limit: to - from + 1 }
  await hooks["tool.execute.before"](input, { args })
  const output = { output: "reference excerpt", metadata: {
    display: { type: "file", lineStart: from, lineEnd: to }, truncated: true,
  } }
  await hooks["tool.execute.after"]({ ...input, args }, output)
  return { type: "tool", tool: "read", state: { status: "completed", input: args, ...output } }
}

test("unchanged overlapping reference pages are blocked, new pages and changed content are allowed", async t => {
  const { hooks, ref } = await fixture(t)
  await read(hooks, ref)
  await assert.rejects(read(hooks, ref, { from: 2, to: 2 }), /KBDS_REFERENCE_ALREADY_READ/)
  await read(hooks, ref, { from: 3, to: 4 })
  await writeFile(ref, "changed one\nchanged two\nline three\nline four")
  await read(hooks, ref)
  const output = { context: [] }
  await hooks["experimental.session.compacting"]({ sessionID: "one" }, output)
  assert.match(output.context[0], /references_read/)
  assert.match(output.context[0], /safety-policy.md:1-2/)
})

test("reference guard ignores mutable controls and source data", async t => {
  const { hooks, directory } = await fixture(t)
  await mkdir(path.join(directory, "config"))
  const control = path.join(directory, "config/policy.local.json")
  await writeFile(control, "{}")
  await read(hooks, control)
  await read(hooks, control)
  await read(hooks, path.join(directory, "source.fastq"))
})

test("full skill load suppresses duplicate loads and equivalent direct reads", async t => {
  const { hooks, directory } = await fixture(t)
  const input = { tool: "skill", sessionID: "one", callID: "skill" }
  const args = { name: "kbds-data-organizer" }
  await hooks["tool.execute.before"](input, { args })
  await hooks["tool.execute.after"]({ ...input, args }, { output: "loaded", metadata: {} })
  await assert.rejects(hooks["tool.execute.before"](input, { args }), /KBDS_REFERENCE_ALREADY_READ/)
  await assert.rejects(read(hooks, path.join(directory, "skills/kbds-data-organizer/SKILL.md")), /KBDS_REFERENCE_ALREADY_READ/)
})

test("copy commands get a minimum tool budget without shortening a larger budget", async t => {
  const { hooks } = await fixture(t)
  for (const command of [run, `python3 scripts/kbds.py --policy /approved/policy.json apply --plan /approved/plan.json --approve-plan ${hash}`]) {
    for (const timeout of [undefined, 120000, 900000]) {
      const output = { args: { command, ...(timeout ? { timeout } : {}) } }
      await hooks["tool.execute.before"]({ tool: "bash", sessionID: "one" }, output)
      assert.equal(output.args.timeout, timeout === 900000 ? timeout : 600000)
    }
  }
})

test("stage permits canonical wrappers but rejects shell expansion, chains and another workdir", async t => {
  const { hooks, directory } = await fixture(t)
  const before = args => hooks["tool.execute.before"]({ tool: "bash", sessionID: "one" }, { args })
  for (const command of [run, "python3 scripts/kbds.py self-check",
    "python3 scripts/kbds.py --policy '/srv/연습 자료/policy.json' inventory --summary",
    'python3 scripts/kbds.py --policy "/srv/control/policy.json" plan --name job-001 --decisions /srv/control/decisions.json',
    "python3 scripts/kbds.py --policy /srv/policy.json verify --plan /srv/job/plan.json",
    "python3 scripts/kbds.py run --scope /srv/scope.json --inspect"]) await before({ command, workdir: directory })
  for (const command of [run + "; echo bad", run + "\necho bad", run + " > /srv/overwrite",
    run.replace("job-001", "$(touch /srv/bad)"), run.replace("job-001", "`touch /srv/bad`"),
    "python3 scripts/kbds.py --policy /srv/* inventory", "python3 scripts/kbds.py --policy policy.json inventory",
    `python3 scripts/kbds.py run --scope "/srv/a\\" --approve-scope ${hash} --name " ; echo bad #"`,
    "python3 -c 'print(1)'", "sh -c 'python3 scripts/kbds.py self-check'",
    "python3 scripts/kbds.py self-check\n"]) {
    await assert.rejects(before({ command }), /KBDS_COMMAND_BLOCKED/, command)
  }
  await assert.rejects(before({ command: run, workdir: path.dirname(directory) }), /project root/)
})

test("localized run and report preserve timeout and completion guards with exact language values", async t => {
  for (const language of ["ko", "en"]) {
    for (const base of [run, "python3 scripts/kbds.py report --plan /approved/plan.json"]) {
      const { hooks } = await fixture(t)
      const command = `${base} --language ${language}`
      const args = { command, timeout: 120000 }
      await hooks["tool.execute.before"]({ tool: "bash", sessionID: "one" }, { args })
      if (base === run) assert.equal(args.timeout, 600000)
      const output = base === run ? result() : {
        output: '{"event":"VERIFIED","submission_ready":false}\n/approved/report.html', metadata: { exit: 0 },
      }
      await hooks["tool.execute.after"]({ tool: "bash", sessionID: "one", callID: "localized", args }, output)
      await assert.rejects(hooks["tool.execute.before"]({ tool: "glob", sessionID: "one" }, { args: {} }), /KBDS_TASK_COMPLETE/)
    }
  }
  const { hooks } = await fixture(t)
  for (const base of [run, "python3 scripts/kbds.py report --plan /approved/plan.json"]) {
    for (const suffix of [" --language fr", " --language EN", " --language en --language ko", " --language en; echo bad", " --language en > /approved/other"]) {
      await assert.rejects(hooks["tool.execute.before"]({ tool: "bash", sessionID: "one" }, { args: { command: base + suffix } }), /KBDS_COMMAND_BLOCKED/)
    }
  }
})

test("a failed reference read is not cached, and caches are isolated between sessions", async t => {
  const { hooks, ref } = await fixture(t)
  const input = { tool: "read", sessionID: "one", callID: "failed" }
  const args = { filePath: ref, offset: 1, limit: 2 }
  await hooks["tool.execute.before"](input, { args })
  await read(hooks, ref)
  await read(hooks, ref, { sessionID: "two" })
})

test("reference state survives a plugin reload using existing successful tool metadata", async t => {
  const { hooks, ref, directory, state } = await fixture(t)
  const part = await read(hooks, ref)
  state.messages.push(assistant([part]))
  const reloaded = await guard({ directory, client: { session: { messages: async () => ({ data: state.messages }) } } })
  await assert.rejects(read(reloaded, ref), /KBDS_REFERENCE_ALREADY_READ/)
})

test("successful scoped run closes tools and adds authoritative completion checkpoint", async t => {
  const { hooks } = await fixture(t)
  await hooks["tool.execute.after"]({ tool: "bash", sessionID: "one", callID: "run", args: { command: run } }, result())
  await assert.rejects(hooks["tool.execute.before"]({ tool: "skill", sessionID: "one" }, { args: { name: "kbds-data-organizer" } }), /KBDS_TASK_COMPLETE/)
  const output = { context: [] }
  await hooks["experimental.session.compacting"]({ sessionID: "one" }, output)
  assert.match(output.context[0], /VERIFIED_REPORT_COMPLETE/)
  assert.match(output.context[0], /report.html/)
})

test("checkpoint preserves all instructions in one system message for local chat templates", async t => {
  const { hooks } = await fixture(t)
  for (const base of [[], ["base instructions"], ["base instructions", "agent instructions", "project constraints"]]) {
    const output = { system: [...base] }
    await hooks["experimental.chat.system.transform"]({ sessionID: "one" }, output)
    assert.equal(output.system.length, 1)
    assert.ok(output.system[0].startsWith(base.length ? base.join("\n\n") + "\n\n" : "KBDS runtime rules"))
    assert.match(output.system[0], /KBDS runtime rules/)
  }
})

test("checkpoints keep allowed control paths under the project despite a stale workspace summary", async t => {
  const messages = [user("first"), assistant([{ type: "text",
    text: "workspace_root=/srv/private/job; edit /srv/private/job/config/policy.local.json",
  }], "stop", { summary: true })]
  const { hooks, directory } = await fixture(t, messages)
  const root = await realpath(directory)
  const system = { system: [] }, compaction = { context: [] }
  await hooks["experimental.chat.system.transform"]({ sessionID: "one" }, system)
  await hooks["experimental.session.compacting"]({ sessionID: "one" }, compaction)
  for (const text of [system.system[0], compaction.context[0]]) {
    const state = JSON.parse(text.slice(text.indexOf("{") ))
    assert.equal(state.project_root, root)
    assert.deepEqual(state.control_paths, {
      policy: path.join(root, "config/policy.local.json"),
      decisions: path.join(root, "config/decisions.local.json"),
    })
    assert.equal(state.status, text === compaction.context[0] ? "ACTIVE" : undefined)
    assert.match(state.next_action, /No new approval is granted/)
    assert.equal("scope" in state.control_paths, false)
  }
})

test("system prefix stays byte-identical through reads and completion while compaction tracks both", async t => {
  const { hooks, ref } = await fixture(t)
  const system = async () => {
    const output = { system: ["base instructions", "agent instructions"] }
    await hooks["experimental.chat.system.transform"]({ sessionID: "one" }, output)
    assert.equal(output.system.length, 1)
    return Buffer.from(output.system[0], "utf8")
  }
  const checkpoint = async () => {
    const output = { context: [] }
    await hooks["experimental.session.compacting"]({ sessionID: "one" }, output)
    return JSON.parse(output.context[0].slice(output.context[0].indexOf("{")))
  }
  const initial = await system()
  assert.deepEqual((await checkpoint()).references_read, [])
  await read(hooks, ref)
  assert.deepEqual(await system(), initial)
  const active = await checkpoint()
  assert.equal(active.status, "ACTIVE")
  assert.deepEqual(active.references_read, ["skills/kbds-data-organizer/references/safety-policy.md:1-2"])
  await hooks["tool.execute.after"]({ tool: "bash", sessionID: "one", callID: "run", args: { command: run } }, result())
  assert.deepEqual(await system(), initial)
  const completed = await checkpoint()
  assert.equal(completed.status, "VERIFIED_REPORT_COMPLETE")
  assert.equal(completed.report_path, complete.report_path)
  assert.deepEqual(completed.references_read, active.references_read)
  assert.match(completed.next_action, /final chat answer and stop/)
  await assert.rejects(read(hooks, ref), /KBDS_TASK_COMPLETE/)
})

test("completion is not inferred from prose, failed commands, partial output or arbitrary shell", async t => {
  for (const [command, output] of [
    [run, result(complete, 2)], [run, result({ ...complete, metadata_verified: false })],
    [run, { output: "COMPLETE", metadata: { exit: 0 } }],
    ["cat saved-result.json", result()], [run + "; echo other", result()],
    [run.replace("--approve-scope " + hash, "--inspect"), result()],
  ]) {
    const { hooks } = await fixture(t)
    await hooks["tool.execute.after"]({ tool: "bash", sessionID: "one", callID: "run", args: { command } }, output)
    await hooks["tool.execute.before"]({ tool: "glob", sessionID: "one" }, { args: {} })
  }
})

test("separate verified report command also closes the task", async t => {
  const { hooks } = await fixture(t)
  const output = { output: '{"event":"VERIFIED","submission_ready":false}\n/approved/report.html', metadata: { exit: 0 } }
  await hooks["tool.execute.after"]({ tool: "bash", sessionID: "one", callID: "report", args: { command: "python3 scripts/kbds.py report --plan /approved/plan.json" } }, output)
  await assert.rejects(hooks["tool.execute.before"]({ tool: "read", sessionID: "one" }, { args: {} }), /KBDS_TASK_COMPLETE/)
})

test("only a new actual user prompt clears terminal state; compaction continuation does not", async t => {
  const { hooks, ref } = await fixture(t)
  await hooks["tool.execute.after"]({ tool: "bash", sessionID: "one", callID: "run", args: { command: run } }, result())
  await hooks["chat.message"]({ sessionID: "one", agent: "kbds-stage" }, {
    message: { role: "user", id: "synthetic" }, parts: [{ type: "text", synthetic: true, text: "Continue", metadata: { compaction_continue: true } }],
  })
  await assert.rejects(read(hooks, ref), /KBDS_TASK_COMPLETE/)
  const next = user("second")
  await hooks["chat.message"]({ sessionID: "one", agent: "kbds-stage" }, { message: next.info, parts: next.parts })
  await read(hooks, ref)
})

test("completed final answer suppresses synthetic restart but tool completion permits one final answer", async t => {
  const messages = [user("first"), assistant([toolPart({ command: run }, result())])]
  const { hooks, state } = await fixture(t, messages)
  let output = { enabled: true }
  await hooks["experimental.compaction.autocontinue"]({ sessionID: "one", agent: "kbds-stage" }, output)
  assert.equal(output.enabled, true)
  state.messages.push(assistant([{ type: "text", text: "Done" }], "stop"))
  state.messages.push({ info: { role: "user", id: "compact" }, parts: [{ type: "compaction" }] })
  state.messages.push(assistant([{ type: "text", text: "Stale summary: needs copying" }], "stop", { summary: true }))
  output = { enabled: true }
  await hooks["experimental.compaction.autocontinue"]({ sessionID: "one", agent: "kbds-stage" }, output)
  assert.equal(output.enabled, false)
  state.messages.push(user("next-task"))
  output = { enabled: true }
  await hooks["experimental.compaction.autocontinue"]({ sessionID: "one", agent: "kbds-stage" }, output)
  assert.equal(output.enabled, true)
})

test("a normal read-only final answer also stays stopped after compaction", async t => {
  const first = user("first")
  first.info.agent = "kbds-review"
  const { hooks } = await fixture(t, [first, assistant([], "stop")])
  const output = { enabled: true }
  await hooks["experimental.compaction.autocontinue"]({ sessionID: "one", agent: "kbds-review" }, output)
  assert.equal(output.enabled, false)
})

test("SDK failures stop safely and can be retried after reconnection", async t => {
  const { hooks, state } = await fixture(t)
  state.error = true
  await assert.rejects(hooks["tool.execute.before"]({ tool: "glob", sessionID: "one" }, { args: {} }), /KBDS_GUARD_HISTORY_UNAVAILABLE/)
  state.error = false
  await hooks["tool.execute.before"]({ tool: "glob", sessionID: "one" }, { args: {} })
})

test("plugin and its tests contain no package dependency", async () => {
  const source = await readFile(new URL("../.opencode/plugins/kbds-session-guard.js", import.meta.url), "utf8")
  assert.ok([...source.matchAll(/from "([^"]+)"/g)].every(match => match[1].startsWith("node:")))
})
