# kbds-data-toolkit

Inspect sequencing files, organize an approved **copy**, verify its contents, and create a
private HTML report. Source files and original filenames stay unchanged. The default agent
is read-only. Research/submission metadata preparation belongs to another tool. This project
does not upload data or produce a submission-ready archive package.

선택한 자료를 조사하고 승인된 새 폴더에 복사·검증합니다. 원본은 보존합니다.
[한국어 상세 사용 안내](docs/README.ko.md)를 참고하세요.

## Supported use

| Area | Supported behavior | Boundary |
|---|---|---|
| File execution | Linux, Python 3.10+, standard library | Windows/macOS do not run the staging engine; use an approved Linux host |
| Agent | OpenCode 1.18.35 with a local, tool-capable Qwen model | Other versions need compatibility tests; no external model fallback |
| KRA production input | `.fastq`, `.fq`, and gzip variants; four-line records; SINGLE or one R1/R2 pair per Run | No wrapped/interleaved FASTQ, colorspace, KRA BAM/CRAM, or format conversion |
| Other repository outputs | Explicitly classified regular files, byte-for-byte copy and SHA-256 checks | No scientific validation of BAM, CRAM, VCF, FASTA, MEX, HDF5 or expression matrices |
| Practice input | Explicitly approved **zero-byte** placeholders | Does not test sequencing contents or prove biological relationships |
| Supporting documents | Selected metadata may inform operator decisions | No PDF/HWP/Excel extraction, OCR, automatic biological inference or research/submission metadata preparation |
| Output | New sibling folder, execution audit records, verification and offline HTML | No research/submission metadata tables, overwrite, merge, automatic resume, cleanup, deduplication, or archive upload |
| Language | English/Korean HTML reports; English instructions and Korean guide; UTF-8 JSON/TSV | Supplied evidence, identifiers and manual prose keep their original language |

KRA/KEA/KVar/KNA are K-BDS routes; GEO is a separate NCBI archive. The repository setting
selects a local organization policy, not archive eligibility. Read [safety limits](docs/SAFETY.md)
before production use. Tests do not establish support for every filesystem or dataset.

## 1. Prepare the local model and OpenCode

Run these steps on the **Linux data host**, using an account approved to read the source and
create the selected output/workspace. Keep the model server bound to loopback. The toolkit
does not install weights, GPU drivers, or services.

Install [OpenCode](https://opencode.ai/docs/#install) using your administrator's approved method.
The tested version is **1.18.35**. One pinned installation method is:

```bash
task_installer=$(mktemp)
curl -fsSL https://opencode.ai/install -o "$task_installer"
bash "$task_installer" --version 1.18.35
export PATH="$HOME/.opencode/bin:$HOME/.local/bin:$PATH"
opencode --version
python3 --version
```

Prepare `llama-server` using the [llama.cpp b11429 build guide](https://github.com/ggml-org/llama.cpp/blob/b11429/docs/build.md).
The example model is the [ggml-org Qwen3.8-27B GGUF](https://huggingface.co/ggml-org/Qwen3.8-27B-GGUF).
Use a new model directory; the download command writes the named file.

```bash
mkdir -p "$HOME/models/Qwen3.8-27B"
cd "$HOME/models/Qwen3.8-27B"
curl -fL --output Qwen3.8-27B-Q4_K_M.gguf \
  https://huggingface.co/ggml-org/Qwen3.8-27B-GGUF/resolve/71bc7b627595dc8a91039addd9c791ae548d6747/Qwen3.8-27B-Q4_K_M.gguf
printf '%s  %s\n' \
  c600de0300ae8a0eb3a6c0b8b5561b8b96f16bd2c863c2a66c42de29d391a747 \
  Qwen3.8-27B-Q4_K_M.gguf | sha256sum -c -
llama-server --model "$HOME/models/Qwen3.8-27B/Qwen3.8-27B-Q4_K_M.gguf" \
  --alias qwen3.8-27b --host 127.0.0.1 --port 8080 --ctx-size 16384 \
  --parallel 1 --jinja --fit off --gpu-layers 24
```

Keep that terminal open. Adjust GPU layers for your hardware; `0` runs on the CPU. Reducing
GPU layers keeps more model weights in RAM. The example ran on 64 GB RAM / 11 GB VRAM;
this is an example, not a minimum-memory guarantee. A vision projector is not needed for
filename/listing work. Stop this foreground model with Ctrl+C when it is no longer needed.

From a second terminal, check the server:

```bash
curl http://127.0.0.1:8080/v1/models
```

The model ID must match `qwen3.8-27b` in `opencode.json`. This is an API alias, not proof of
the installed model's identity. A different ID requires matching provider keys, `model`,
`small_model`, both task-agent models, and the compaction alias's `id`. The compact alias
uses the **same** local model with a smaller output budget. Both services must run on the
same host, or you must explicitly configure an authorized connection.

## 2. Get the skill and check the environment

```bash
git clone --branch codex/opencode-read-only-qwen-20261010 --single-branch https://github.com/Imeanstar/kbds-data-toolkit.git
cd kbds-data-toolkit
opencode debug config
opencode debug agent kbds-review
opencode debug agent kbds-stage
opencode debug skill
python3 -B scripts/kbds.py self-check
```

Check the **effective** configuration, including global overrides. Only `qwen-local` should
provide task and summary models. `skills.paths` discovers `./skills`; do not copy the skill
to another hidden directory or regenerate `AGENTS.md` with `/init`.

`self-check` uses only new synthetic files in a temporary directory, then removes its own
test directory. It checks plan/copy/verify/report plumbing, not Qwen judgment or permissions
on the real source. Stop if it fails.

The profile uses a 16,384-token context, 2,048-token task output and 1,024-token summary
output. Match the model server's context to the profile. Keep each job in a fresh session.
Apply configuration changes only when relevant sessions are idle. A project instance refresh
can reload configuration; restart the OpenCode process after plugin code changes because Bun
caches imported modules. Cache refresh does not complete a failed copy.

OpenCode auto-loads the bundled `.opencode/plugins/kbds-session-guard.js`; keep this directory
when deploying. It requires no npm packages. On OpenCode 1.18.35 it blocks duplicate reads of
unchanged bundled reference ranges within one user turn, restores checkpoints from session
history, and stops tool use after a verified bundled run/report. New genuine user messages
start a new turn; synthetic compaction continuations do not. Updated references, unread
ranges and mutable control/data files remain readable. A summary may still run after the
final answer, but it cannot restart the completed task through the guarded continuation hook.
Stable system instructions include the canonical project root, fixed absolute policy/decisions
paths and general reuse/stop rules. Changing job status and read history enter the checkpoint
only during compaction, so ordinary reference reads do not rewrite the initial system prefix.
This avoids a known cause of local prompt-cache invalidation; the speed change has not been
re-measured. Tool gates still use current session state. No scope approval is granted or changed.
The guard also raises recognized `apply`/`run` timeouts to at least 600000 ms. It does not
grant permissions, authenticate approvals, or provide an OS sandbox. Other OpenCode versions
need explicit hook compatibility tests before use. See the
[plugin API](https://opencode.ai/docs/plugins/) and the
[pinned hook definitions](https://github.com/anomalyco/opencode/blob/v1.18.35/packages/plugin/src/index.ts).
Only documented single wrapper commands from the toolkit root are accepted. Shell chains,
redirection, substitutions and wrappers are blocked even if a broad permission pattern matches.

Do not use `--pure` or `OPENCODE_PURE=true`: OpenCode skips project plugins in that mode,
even when `/config` lists their paths. To disable built-in provider plugins while keeping this
local guard, use `OPENCODE_DISABLE_DEFAULT_PLUGINS=true` as shown below. Before approving
staging, confirm a successful bundled skill/reference read has `kbds_reference` metadata in
the local OpenCode session record. A listed plugin path alone does not prove its hooks loaded.

## 3. Inspect without changing files

```bash
OPENCODE_DISABLE_DEFAULT_PLUGINS=true opencode --agent kbds-review --model qwen-local/qwen3.8-27b
```

Example request (replace the synthetic path):

> Use kbds-data-organizer. Inspect the file list in /srv/example/raw/Example and the
> related records I select. Do not create, change, copy, move or delete files. Explain
> confirmed findings, incomplete counts and unresolved relationships in chat.

This agent allows native read/glob/skill/question tools. Shell commands, grep and file writes
are denied. OpenCode stores its own session records outside the dataset. A previous report
or `COMPLETE.json` alone does not verify the current files.

## 4. Organize a copy and create the report

```bash
OPENCODE_DISABLE_DEFAULT_PLUGINS=true opencode --agent kbds-stage --model qwen-local/qwen3.8-27b
```

Example request:

> Use kbds-data-organizer. Source: /srv/example/raw/Example.
> New output: /srv/example/raw/Example_makeup. Workspace: /srv/example/work/job-001.
> Use production mode. Preserve the source. Ask about unresolved classification or
> sample/library/Run relationships. Show a copy plan. After I approve its plan_sha256,
> copy, verify and create the HTML report. Stop when the report is complete.

The agent drafts only ignored `config/policy.local.json` and `config/decisions.local.json`.
Preserve the previous job's drafts first. All control-file arguments must be absolute paths.
Quote shell paths that contain spaces; keep their original spelling in UTF-8 JSON.
The source must exist; destination/workspace parents must exist. The three roots must be
disjoint. The new output must be a sibling named `<source>_makeup` or
`<source>_<repository>_makeup`. Existing output blocks execution.

`config/*.example.json` contains **synthetic** paths and facts. Replace them with reviewed
values. Every source file needs an explicit include/exclude decision or a matching approved
path rule. Extension matching is only a candidate classification. Names do not prove
provenance, biology, bulk/single-cell, or paired layout. See the
[decision schema and naming rules](skills/kbds-data-organizer/references/naming-policy.md).

For placeholder practice, set `mode: "practice"` and `allow_practice_zero_bytes: true`.
Record explicit fictional assumptions for this dataset. Never switch real data to practice
to bypass validation. Never reuse another dataset's assumptions as facts.

Without a preapproved scope, approve the exact **`plan_sha256` from plan stdout**. It is a
canonical-plan hash, not the checksum of the JSON file. Tool permission and task approval
are separate; the bundled profile asks for each permitted operation. Do not enable all shell
commands or use `--auto`. Use native bash timeout at least **600000 ms** for practice
`apply`/`run`, and budget longer for large files and verification.

### Automatic execution within an approved scope

Approve exact roots, mode and classification rules once. An operator reviews the drafts and
stores a private scope using [scope.example.json](config/scope.example.json). The data agent
cannot edit that scope through the bundled profile. The operator can inspect it with:

```bash
python3 scripts/kbds.py run --scope /absolute/repo/config/scope.local.json --inspect
```

After recording actual user authorization, supply the resulting `scope_sha256` to Qwen:

```bash
python3 scripts/kbds.py run --scope /absolute/repo/config/scope.local.json --approve-scope APPROVED_SCOPE_SHA256 --name job-001
```

This creates a fresh plan, checks it, copies, verifies and writes `report.html`. Matching
plans need no new plan approval. New roots/rules require scope review. Unknown files, missing
mates, conflicting rules, invalid content or occupied output stop the run. A scope is not a
background watcher or an authenticated approval service. See
[scoped execution](skills/kbds-data-organizer/references/scoped-execution.md).
An exact scope authorizes a fresh output, not updates to a completed package. New output
paths require a new reviewed scope; changing files does not permit merging into old results.

## 5. Read the result and handle a stop

The private plan directory contains `plan.json`, four audit TSVs and `report.html`. New output
`audit/` contains seven execution records: `plan.json`, `inventory.tsv`, `file_mapping.tsv`,
`unresolved.tsv`, `excluded.tsv`, `events.jsonl` and `COMPLETE.json`.
No `sample_mapping.tsv` or research/submission metadata table is generated. The file map
contains source/output paths, size, SHA-256, repository, file role, reason and evidence.
The plan retains approved folder decisions so verification can reproduce the operation;
these records do not supply verified biological facts or official submission fields.
Selected existing metadata may inform decisions and remains subject to source preservation
and explicit include/exclude rules. Reports always state `submission_ready=false`.
New plans use `report_format_version: 3`: TSV text that could start a spreadsheet formula
gets a leading apostrophe. Exact original strings remain in `plan.json`. Use that JSON as
the source for automated path processing; do not treat the escaped TSV cell as a filename.
Version-1/2 plans keep their original TSV serialization and `metadata/` records, including
their sample table. They remain available for read-only verification and reports; applying an
old plan to a new output is blocked. Create a fresh version-3 plan for new copies. Existing
packages are not migrated or cleaned up. Stricter path checks can still
reject an old nonportable package; the toolkit does not rewrite it.
HTML is self-contained, with no remote fonts/images/styles. Reports default to Korean.
Append **`--language en` as the last option** to `run` or `report` for English generated
narrative, interface and diagram labels; `--language ko` explicitly selects Korean.
Supplied evidence, identifiers, paths and manual report prose remain unchanged. Language does
not change the plan/scope hash or copied data. JSON/TSV field names remain English.

```bash
python3 scripts/kbds.py run --scope /absolute/repo/config/scope.local.json --approve-scope APPROVED_SCOPE_SHA256 --name job-001 --language en
```

For a completed package that does not yet have a report, use:

```bash
python3 scripts/kbds.py report --plan /approved/work/job-001/plan.json --language en
```

Choose the language before generation. An existing `report.html` is never overwritten,
including when another language is requested. A browser can print HTML to PDF.
Do not claim browser/print QA on a headless host unless it was actually performed.

Production checks file size/SHA-256 and supported KRA FASTQ contents. Other repository files
receive `sha256_only` validation. A separate `verify` checks stored bytes and audit records; it
does not repeat FASTQ parsing. Practice checks empty placeholders and path/pair consistency.
None of these checks establishes scientific correctness or release permission.

Exit 2 / `WAITING_FOR_USER` identifies an exception, not automatic permission to exclude a
file or convert PAIRED to SINGLE. Preserve partial output after failure, timeout or disconnect.
Inspect whether a process is still running before retrying. Never rerun into existing output.
Resolve the cause and review a new permitted destination/plan; changing the plan name alone
does not change the output path. Stop after confirmed completion.

Names are preserved. New identifiers use 1–128 ASCII letters/digits/underscore/hyphen/dot,
starting alphanumeric. Unicode source names can remain Unicode, but destination collisions
and names incompatible with portable file components cause a stop, not an automatic rename.
The engine remains Linux-only; long-path limits, network filesystems and cross-platform
exports still need testing on the intended storage. Use UTF-8 for private JSON/TSV.

`run` stdout includes `timings_seconds` for scope checks, planning, preflight, copy/audit records,
verification and report verification/rendering. These durations measure the tool process.
The timing key `copy_and_metadata` is retained for compatibility and now measures copying
plus execution-record writing; it does not mean research metadata generation.
They exclude model generation and OpenCode approval waits. Use session timestamps separately
for end-to-end time; file modification times do not establish exact phase durations.

Read [safety limits](docs/SAFETY.md) and [report requirements](skills/kbds-data-organizer/references/report-format.md).
Keep data, paths, control files and logs private. Source read-only rights and scoped write
rights require OS enforcement; Markdown rules and hashes are not a sandbox.

## Development and validation

```bash
python3 -B -m unittest discover -s tests -v
python3 -B scripts/kbds.py self-check
node --test tests/test_session_guard.mjs
```

CI runs synthetic tests on Linux with Python 3.10 and 3.14, and pure-logic tests on Windows
with Python 3.14. Filesystem tests deliberately skip on Windows. Tests do not contact a
research server or model. Local model acceptance tests are separate from CI evidence.
The session-guard behavior tests use Node.js 22 without third-party packages.

The recorded review run discovered 119 Python tests: Linux passed 118 and skipped one;
local Windows passed 55 and skipped 64. CI skip counts can differ with platform capabilities,
including symlink privileges. All 19 session-guard tests passed.
These results cover synthetic checks, not completion of a private model-driven data job.

- `AGENTS.md`: data-agent rules. Repository maintenance is a separate task.
- `opencode.json`: local models, tool permissions and skill discovery.
- `skills/kbds-data-organizer/`: self-contained skill, references and Python engine.
- `scripts/kbds.py`: repository entrypoint.
- `scripts/remote_stage.py`: optional off-host bridge; not used by server Qwen. It needs a
  trusted local account and does not authenticate remote human approval.

See [known boundaries and roadmap](docs/ROADMAP.md).
The [reliability review](docs/reliability-review.md) records the defects fixed, validation
scope and remaining limitations.
