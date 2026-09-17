---
name: kbds-data-organizer
description: Prepare human-reviewed, copy-only K-BDS staging directories from a precisely scoped research dataset. Use to inspect sequencing file layouts, propose KRA Study-Sample-Experiment-Run mappings, classify other files as repository candidates, ask about ambiguous metadata and execute an explicitly approved copy plan. Support configured zero-byte practice files separately from production. Do not submit to K-BDS, infer biological relationships, delete originals or promise SSH connectivity.
---

# KBDS Data Organizer

## Prerequisites

Read `references/safety-policy.md`, `references/naming-policy.md` and
`references/data-classification.md` before acting. Run `scripts/toolkit.py` in this skill;
inside the full Git repository, `scripts/kbds.py` wraps the same implementation.
Require Linux and Python 3.10+. Do not install software without authorization.

Identify the actual execution environment. A GitHub connection is not SSH access. Either
run on the research server through an authorized terminal, or use the full repository's
OpenSSH wrapper from a computer with verified existing access. Stop if neither is available.

Require an approved local JSON policy with three disjoint absolute roots: source (read-only),
destination (new output) and workspace (new planning reports). Never substitute a similar
path or add another volume. Use only the explicitly selected mode, not a folder-name guess.

## Workflow

1. Inspect the scoped source with `inventory`. Report actual counts and errors. Unreadable
   paths, symlinks, nonregular files and sensitive names block completeness. Do not hide errors.
2. Parse paths into candidates only. Preserve original names. Never merge differently spelled
   identifiers or equate a subject with a BioSample. Do not import facts from another study.
3. Collect exact per-file decisions under the `files` object in a local decisions JSON.
   Every entry needs `action: include|exclude` and `reason`. Includes also need `evidence`,
   `repository`, `study`. KRA includes additionally need confirmed `sample`, `experiment`,
   `run`, `layout: PAIRED|SINGLE`, and `raw_confirmed: true`.
   Ask repeated questions as a group only when their scope/evidence is the same. Record all
   affected paths. Treat missing biological relationships as questions, never defaults.
4. Run `plan --name draft-001`. Missing decisions produce WAITING_FOR_USER and unresolved.tsv,
   not guessed mappings. After answers, run a NEW plan name with `--decisions`. Never overwrite
   an old report. Every source file must be explicitly included or excluded with a reason.
5. Present the full plan, count/bytes, mode, exact source/destination, exclusions, unresolved
   items and plan hash. Explain that these are local staging conventions, not a K-BDS upload
   protocol or official submission metadata. Ask approval for this exact plan and wait.
6. Only after explicit approval run `apply --plan ABSOLUTE_PLAN --approve-plan EXACT_HASH`.
   Never supply approval on the user's behalf. Never change safeguards to make a plan pass.
7. Show actual progress events. If a source changes, a copy fails or the session disconnects,
   stop; retain partial output and explain the known state. Stopping an SSH client does not
   prove the remote process has stopped. Never silently retry into an existing destination.
8. Run `verify`. Declare completion only after verification and COMPLETE.json. Report that
   submission_ready is false and list the checks actually performed. Stop after this task.

## Command examples

These paths are syntax examples, not authorization. Control file paths must be absolute.

```bash
python3 scripts/toolkit.py --policy /approved/policy.local.json inventory
python3 scripts/toolkit.py --policy /approved/policy.local.json plan --name draft-001
python3 scripts/toolkit.py --policy /approved/policy.local.json plan --name reviewed-001 --decisions /approved/decisions.local.json
python3 scripts/toolkit.py --policy /approved/policy.local.json apply --plan /approved/work/reviewed-001/plan.json --approve-plan FULL_SHA256
python3 scripts/toolkit.py --policy /approved/policy.local.json verify --plan /approved/work/reviewed-001/plan.json
```

Exit 2 means blocked/awaiting information, not permission to escalate. Exit 130 means interrupted.
Do not replace a failed operation with raw shell copying or permission changes.

## Deliverables and boundaries

Produce plan.json, inventory.tsv, file_mapping.tsv, sample_mapping.tsv, unresolved.tsv and
excluded.tsv. Preserve evidence and decisions for a future metadata agent. Copy approved files
only, retaining original filenames. Copy the reports into the staged metadata directory as well.

Practice copies empty placeholders only; validate paths/sizes and filename-pair syntax, not reads.
Production checks SHA-256 plus supported unwrapped four-line KRA FASTQ/gzip and paired read IDs.
Other repositories receive byte-integrity checks only. KRA BAM/CRAM, official submission metadata,
web UI and an independent human-approval service are not implemented in v0.1.

Use separate OS permissions or an independently controlled execution gateway for hard isolation.
Python checks and a hash flag are not cryptographic human approval or protection against an agent
that can edit the code/policy or use an unrestricted shell. Do not describe them as such.
