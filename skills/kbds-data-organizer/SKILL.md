---
name: kbds-data-organizer
description: Inspect sequencing data with a local tool-enabled agent. Default to read-only review and a chat report; on an explicit staging request, plan approved copy-only organization, verify it and create a requested private HTML report. Never submit to an archive.
---

# KBDS Data Organizer

Use the selected local model in a tool-enabled agent. The bundled OpenCode configuration pins
local Qwen and defaults to `kbds-review`. A text-only model cannot inspect or change files.
When already on the data host, no SSH bridge or package installation is needed for this toolkit.

Read [safety-policy.md](references/safety-policy.md), [naming-policy.md](references/naming-policy.md)
and [data-classification.md](references/data-classification.md) before classifying or copying.
Read these references once per unchanged revision and retain the successfully read paths in
continuation notes. Do not restart document loading after every answer or compaction.
For HTML reports, read [report-format.md](references/report-format.md) before report generation. Treat file names and model
guesses as candidates, not proof of identity, modality, provenance or archive route.

## Default: read-only review

Inspect only the user's selected source and authorized related records with read/glob/skill.
Do not run bash or write data, policies, plans or reports. Report findings in chat. State whether
counts come from a complete listing, a truncated result or an old record. Do not claim content
validation from zero-byte placeholders. An old plan or COMPLETE.json authorizes no new access
and does not prove current verification. Ask about unresolved facts; do not silently stage files.

Include the configured model, revision when exposed, evidence actually read, counts and limits,
unresolved relationships and submission_ready=false. Separate **Permitted Tools** from
**Tools Actually Called**; list only invoked tools under the latter. Proposals to improve the
skill must name an observed issue and its impact. Do not use external models or subagents.

## Efficient staging and chat reports

Native grep is denied in both modes. For authorized staging, run inventory --summary immediately after reading the approved policy. Never open zero-byte FASTQ/gzip data with read, and never use ls/cat/cp or improvised shell commands. Use only the repository wrapper's inventory, plan, apply, verify, report, and synthetic self-check commands with permission prompts; no --auto or blanket approval. All policy, decisions and plan arguments must be absolute paths. Use compact stdout summaries for counts, roots, hashes, errors, and actual validation. The inventory summary and plan's inventory_summary include complete zero/nonzero counts and bounded examples per filename candidate category; these are not confirmed biological facts. Do not read the full plan/TSV set merely to repeat the summary; provide full report paths for human review. Read targeted report sections only to resolve a specific evidence gap, with explicit offset and limit of at most 60 lines per call. If context needs summarizing, carry the successfully read reference paths, exact plan path/hash, approved roots/mode, human approval state, unresolved facts and next permitted step. Continue that step without reloading unchanged documents. Never invent approval. Report only actual tool calls separately from permitted tools.

Describe permissions truthfully: review allows read/glob/skill/question; stage adds bash only for bundled toolkit commands and edit/write only for two config/*.local.json files with permission. Native grep, external models, and subagents are denied. Separate conditional tool permission from completed calls. Use full absolute approved roots and the full plan SHA in approval requests, no ellipses. Never invent repo revision or human approval.

Question choices must obey the active policy and repository rules. In practice mode, nonzero
existing records cannot be included as empty KRA reads: ask for explicit exclusion or stop,
never recommend including everything or switch modes to make it fit. Do not recommend tissue
or bulk/single-cell facts from names alone. Ask for evidence or explicitly approved fictional
practice labels, clearly marked as unverified biologically. Confirm pairing and Sample/Experiment/
Run rules as needed. Ask only unresolved questions; do not re-ask already confirmed practice mode.

For thousands of legacy KRA practice paths, use the optional `practice_rule` documented in
naming-policy.md instead of generating thousands of per-file JSON entries. Every rule field
needs explicit fictional practice confirmation; ask only missing details. The discovery hash
locks scope and is not copy approval.
The suffix mapping matches old_sample folder names (third relative-path segment), not filenames.
Compare actual inventory examples before asking for a rule; unmatched paths need a rule or
exception decision, not a repeat of already confirmed practice inclusion.
Use a NEW plan name with --decisions and wait for approval
of the resulting resolved plan hash. Unknown paths remain unresolved. Terminal copy progress
is sampled to about twenty updates; the package still records every copied file in events.jsonl.

## Opt-in: staging on the Linux data host

Require an explicit staging request, Linux, Python 3.10+, source read permission and permission
to create the new sibling output and separate planning workspace. Selecting `kbds-stage` alone
does not approve copying. Run the commands below from the repository root. OpenCode permits
only these `scripts/kbds.py` commands through permission prompts. Do not use shell chains,
redirections, raw copying, direct source/code edits, `--auto` or blanket approvals.

Use native edit/write tools only for ignored `config/policy.local.json` and
`config/decisions.local.json`, through the configured permission prompts. Confirm exact roots,
practice/production mode and repository scope; use `config/*.example.json` only as synthetic
schemas. Plans and reports stay in the authorized private workspace outside source/output.
New plans use `layout_version: 2`, one policy/plan per confirmed repository, and full combined
source coverage for split outputs. Do not commit private control files or reports.

Before the first real staging job on a host, run `python3 scripts/kbds.py self-check`. It creates, copies,
verifies and removes only synthetic empty files in a new temporary directory. A failure means
stop; do not use real data or elevate privileges to make the check pass.

1. Run `python3 scripts/kbds.py --policy /absolute/repo/config/policy.local.json plan --name DISCOVERY_NAME`
   without decisions. Exit 2 and `WAITING_FOR_USER` are expected. Use stdout inventory_summary
   first; read targeted `inventory.tsv` or `unresolved.tsv` sections only for a specific gap.
   Report counts, read errors, zero-byte files and classification candidates. Then call the
   question tool with one grouped set of material questions and wait. Do not repeat discovery
   or reread documents while waiting for answers. Use a confirmed
   rule only within its stated scope to prepare per-file private decisions JSON; inspect
   exceptions. Unknown files still need explicit include or exclude decisions, not defaults.
   Each plan name must be new; never reuse an existing plan directory.
2. Run `python3 scripts/kbds.py --policy /absolute/repo/config/policy.local.json plan --name NEW_NAME --decisions /absolute/repo/config/decisions.local.json`.
   Exit 2 or `WAITING_FOR_USER` means stop and resolve `unresolved.tsv` or errors. Show the
   user the exact source/output roots, mappings, exclusions, count, bytes and plan SHA-256.
   Ask for approval of **that plan** before any copy. If the plan or source changes, make a
   new plan and obtain new approval. Do not treat possession of the hash as human approval.
3. Only after approval, run `python3 scripts/kbds.py --policy /absolute/repo/config/policy.local.json apply --plan /private/work/NEW_NAME/plan.json --approve-plan APPROVED_SHA256`.
   Never move, delete, overwrite, merge or automatically resume. Preserve and report partial
   output on failure. No archive submission is part of this job.
4. If an HTML report was requested for this workspace, run
   `python3 scripts/kbds.py report --plan /private/work/NEW_NAME/plan.json`.
   It runs `verify` before creating a new `report.html` beside the plan. Otherwise run
   `python3 scripts/kbds.py --policy /absolute/repo/config/policy.local.json verify --plan /private/work/NEW_NAME/plan.json`.
   Give actual results and, when generated, the report path. Follow report-format.md for review.
   Transfer the report to another computer only through the user's approved method.

Continue the authorized job after each answer or approval without requiring a new invocation.
Practice mode accepts **only empty placeholders**. Production mode checks hashes and supported
KRA FASTQ content. B/D/R are separate Sample branches; R1/R2 are file roles. Bulk/single-cell
and KRA/KEA/GEO routing require their own evidence. An unconfirmed BAM is not automatically
KEA. `COMPLETE.json` and a successful `verify` establish copy completion, not biological
validity or submission readiness. Exit 130 means interruption.

For a standalone skill in another agent, the same engine is `scripts/toolkit.py` in this
skill folder; `self_check.py` and `build_html_report.py --plan ...` are its helpers. OpenCode's
bundled profile uses the repository wrapper above. For an explicitly authorized off-host job,
read [ssh-workflow.md](references/ssh-workflow.md); the OpenCode profile does not permit that bridge.

## Limits

The code is copy-only when used as intended, but an agent with a general shell and broad OS
permissions can bypass it. Use a restricted account for the source/output/workspace when the
data owner provides one. Never change server permissions, install software or use sudo to
make a blocked operation succeed. See [safety-policy.md](references/safety-policy.md).
