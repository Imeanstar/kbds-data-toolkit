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
For HTML reports, read [report-format.md](references/report-format.md). Treat file names and model
guesses as candidates, not proof of identity, modality, provenance or archive route.

## Default: read-only review

Inspect only the user's selected source and authorized related records with read/glob/grep/skill.
Do not run bash or write data, policies, plans or reports. Report findings in chat. State whether
counts come from a complete listing, a truncated result or an old record. Do not claim content
validation from zero-byte placeholders. An old plan or COMPLETE.json authorizes no new access
and does not prove current verification. Ask about unresolved facts; do not silently stage files.

Include the configured model, revision when exposed, evidence actually read, counts and limits,
unresolved relationships and submission_ready=false. Separate **Permitted Tools** from
**Tools Actually Called**; list only invoked tools under the latter. Proposals to improve the
skill must name an observed issue and its impact. Do not use external models or subagents.

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
   without decisions. Exit 2 and `WAITING_FOR_USER` are expected. Inspect its `inventory.tsv`
   and `unresolved.tsv` in the private workspace, aggregating large inventories instead of
   loading them all into model context. Report counts, read errors, zero-byte files and
   classification candidates. Ask one grouped set of material questions. Use a confirmed
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
