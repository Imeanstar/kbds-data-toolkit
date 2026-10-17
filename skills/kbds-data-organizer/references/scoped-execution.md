# Execute within an approved scope

Use this mode only when the user requested automatic copying within a confirmed policy.
Plans are generated automatically as audit records. The user approves the scope once;
individual matching plans do not need another approval. No background watcher is installed.

## Prepare the scope

Confirm exact canonical source, new sibling destination, separate workspace, practice or
production, repository, inclusion/exclusion and all biological or fictional practice labels.
Use kbds-stage inventory --summary with the confirmed policy for the initial authorized investigation. It reports counts and up to 20 parent-directory groups with bounded filename examples; name_role_counts are suffix candidates, not confirmed PAIRED/SINGLE layouts. Read only the selected source and records. Ask only facts that remain unresolved. A filename
pattern is parsing evidence, not evidence of biology, raw provenance, modality or paired layout.
Never silently classify an unmatched read as SINGLE to bypass a missing mate.

Qwen may propose `config/policy.local.json` and `config/decisions.local.json` using the existing
native edit permissions. If a full path-rule example is needed, read the `decisions` object
in `config/scope.example.json` once; `decisions.example.json` demonstrates individual files.
Do not inspect the engine to rediscover the schema. After inventory and schema are available,
write the drafts; reread only a specific field identified by a validation error.
An authorized operator reviews them against the user's instruction
and freezes `config/scope.local.json` with exactly:

```json
{"version": 1, "policy": {"...": "confirmed policy"}, "decisions": {"files": {}, "path_rules": []}}
```

This abbreviated shape is not runnable. `policy` is the complete layout-version-2 policy;
`decisions` uses the documented files, practice_rule or path_rules schema. The scope is private,
outside source/output, and excluded from Git. The model cannot edit the scope in the bundled
OpenCode profile. Keep the previous job's control files before preparing another job.

Inspect the scope without copying:

```bash
python3 scripts/kbds.py run --scope /absolute/repo/config/scope.local.json --inspect
```

`scope_sha256` binds the canonical policy and decisions. The command does not grant approval.
The operator records the actual user's scope authorization and supplies that hash to Qwen.
Do not turn a generated hash into an invented user approval. This hash is not the plan hash
and not the checksum of the JSON file's bytes. The scope file has no credentials.

## Execute

```bash
python3 scripts/kbds.py run --scope /absolute/repo/config/scope.local.json --approve-scope APPROVED_SCOPE_SHA256 --name new-job-001
```

Use native bash timeout >= 600000 ms for practice; budget longer for large production data.
OpenCode asks once for this bundled operation. The command validates the scope hash, creates
a new plan, checks every source file, copies, verifies and creates `report.html` beside the plan.
The plan records `approval_scope_sha256`. Source changes between planning and copying still
block execution. Matching new files present before planning use the same approved rules.

Any unmatched file, ambiguous rule, missing mate, invalid metadata, inventory error or occupied
destination stops before copying. Exit 2 / WAITING_FOR_USER is an exception to resolve, not a
request for routine plan approval. Do not auto-exclude unknown files. Policy/rule changes need
scope review and a new scope hash. Preserve partial output after errors/timeouts; do not resume,
delete, merge or silently select another output. An occupied successful output also stops.

Report actual counts, scope/plan hashes, validation limits and report path. The report command
verifies files/metadata before writing. Keep submission_ready=false; no archive upload.
This mechanism is not an independently authenticated approval gateway or an OS sandbox.
An operator with general shell/write access can change code or grants; use external filesystem
isolation when required. The model's read-only scope permission is a workflow boundary.

## Named path rules

Decisions can contain `files` and `path_rules`, but cannot combine path_rules with practice_rule.
Each rule has exactly `pattern` (Python regular expression) and `decision` (normal include or
exclude fields). The expression must match the entire source-relative path. Named captures
can replace `{capture}` tokens in string values; expressions, conversions and format specs
are unsupported. Other values such as `raw_confirmed: true` remain literal values.

Synthetic pattern example: `reads/(?P<sample>Sample[0-9]+)_R(?P<mate>[12])\.fastq\.gz`.
With separately confirmed metadata, `sample: "{sample}"`, `file_role: "R{mate}"` and distinct
`run: "{sample}_Run"` can fill the existing decision fields. Supply all other required fields;
there are no default B/D/R, assay or modality values. Include a lane capture in run when lanes
must be separate. Explicit files entries handle confirmed exceptions. Multiple matching rules
are an error; no match leaves the file unresolved. Normal pair/collision/content checks still run.

Use a small number of simple, anchored-by-fullmatch patterns; avoid costly nested repetitions.
Rules are trusted operator-reviewed code-like input, not suggestions imported from data files.
