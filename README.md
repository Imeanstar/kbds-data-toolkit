# kbds-data-toolkit

Human-reviewed, **copy-only** research-data preparation for later K-BDS submission.
The source dataset is never moved, renamed, deleted or overwritten by this toolkit.

**Status: v0.1 executable prototype.** It inventories, plans, copies and verifies files.
It does not submit to K-BDS, create official metadata or implement a hardened human-approval
service. Start with empty practice placeholders in an isolated test environment.

## Requirements and Codex use

Linux and Python 3.10+ (standard library only). Remote invocation additionally requires an
already-authorized, host-verified SSH alias and this toolkit installed on the remote server.
GitHub access alone does not provide SSH access to a lab network.

Open the repository root in Codex. Read AGENTS.md and invoke `$kbds-data-organizer`.
The skill lives at `.agents/skills/kbds-data-organizer/SKILL.md`. If automatic discovery is not
available, explicitly ask Codex to read that file. Standalone skill.zip includes the same engine.

Example request:

> Use kbds-data-organizer and my approved local policy. Inspect only its source, ask about
> unresolved relationships and propose a copy-only plan. Wait for approval of the exact plan
> before staging. Never modify the source or infer missing biological facts.

References: https://developers.openai.com/codex/skills and
https://developers.openai.com/codex/guides/agents-md (checked 2026-09-17).

## kbds-data-organizer with local Qwen and OpenCode

Run OpenCode on the same Linux server as the model and dataset. Use Python 3.10+,
Git and curl. OpenCode 1.18.35 and llama.cpp b11429 were used for validation.
The toolkit uses Python's standard library. It does not require a paid API key.

### 1. Install OpenCode and get this branch

Install [OpenCode](https://opencode.ai/docs/) from its official installer. These
are operator setup commands; the KBDS agents cannot install software.

```bash
task_installer=$(mktemp)
curl -fsSL https://opencode.ai/install -o "$task_installer"
bash "$task_installer" --version 1.18.35
export PATH="$HOME/.opencode/bin:$HOME/.local/bin:$PATH"
opencode --version

mkdir -p "$HOME/kbds-tools"
cd "$HOME/kbds-tools"
git clone --branch codex/opencode-read-only-qwen-20261010 --single-branch \
  https://github.com/Imeanstar/kbds-data-toolkit.git
cd kbds-data-toolkit
```

Use this branch until its changes are merged into main. A plain clone currently
gets main without this Qwen profile. Start OpenCode from the repository root.

### 2. Start your local Qwen API

If Qwen is already running, check the API in step 3. Otherwise install
[llama.cpp](https://github.com/ggml-org/llama.cpp/blob/b11429/docs/build.md)
using a CPU or CUDA build suitable for your server. Set `LLAMA_SERVER` below to
your installed executable. This example uses the official
[Qwen3.8-27B GGUF](https://huggingface.co/ggml-org/Qwen3.8-27B-GGUF).

```bash
mkdir -p "$HOME/models/Qwen3.8-27B"
cd "$HOME/models/Qwen3.8-27B"
curl -fL --output Qwen3.8-27B-Q4_K_M.gguf \
  https://huggingface.co/ggml-org/Qwen3.8-27B-GGUF/resolve/71bc7b627595dc8a91039addd9c791ae548d6747/Qwen3.8-27B-Q4_K_M.gguf
printf '%s  %s\n' \
  c600de0300ae8a0eb3a6c0b8b5561b8b96f16bd2c863c2a66c42de29d391a747 \
  Qwen3.8-27B-Q4_K_M.gguf | sha256sum -c -
LLAMA_SERVER=/absolute/path/to/llama-server
"$LLAMA_SERVER" -m "$PWD/Qwen3.8-27B-Q4_K_M.gguf" \
  --alias qwen3.8-27b --host 127.0.0.1 --port 8080 \
  --jinja --fit off -c 16384 -np 1 -ngl 24
```

Keep that terminal running. Use a second SSH terminal for OpenCode. Ctrl+C in
that model terminal stops the server and releases its model allocation.
The example splits weights between GPU and RAM. Fewer GPU layers (`-ngl`) use
more RAM; `-ngl 0` permits CPU-only use. Choose the value for your GPU.
The tested hardware has 64 GB RAM and 11 GB VRAM; this is a working example,
not a guarantee for every server. The model file is about 19 GB.
No vision projector is needed for this toolkit's file-list and text-record tasks.

### 3. Check the endpoint and resolved profile

```bash
curl -fsS http://127.0.0.1:8080/health
curl -fsS http://127.0.0.1:8080/v1/models
cd "$HOME/kbds-tools/kbds-data-toolkit"
opencode debug config
opencode debug agent kbds-review
opencode debug agent kbds-stage
opencode debug skill
opencode --agent kbds-review --model qwen-local/qwen3.8-27b
```

The model list must contain `qwen3.8-27b`. Both agents must resolve to
`qwen-local/qwen3.8-27b`. Keep `enabled_providers` and `small_model` on local Qwen.
For a different local endpoint, edit `provider.qwen-local.options.baseURL` in
opencode.json. For a different model ID, update the provider model key and all
model selections together. Use `/v1` in the endpoint. Restart OpenCode after edits.

The profile uses a 16384-token context, early compaction and removal of old tool
outputs. Its llama.cpp requests disable thinking and preserved thinking for
bounded toolkit tasks. This setting affects this project, not other model clients.
Keep the server and profile context sizes equal. Increase both only after checking
memory use. Use compact command summaries and targeted record reads.

### 4. Review first, then request staging

Use OpenCode kbds-data-organizer with local Qwen API at /v1, alias qwen3.8-27b, and server context matching opencode.json (16384 tested configuration). Start in the repository root. Pin --agent kbds-review --model qwen-local/qwen3.8-27b for review. Use --agent kbds-stage with the same model for staging. Example review prompt: 'Inspect source scope and report in chat.' Example staging prompt: 'Create approved plan and wait for exact hash.' No PDF/HWP/Excel interpretation or K-BDS uploader is implemented. Respect permission/account scope limitations and local ignored policies. No automatic replay of old plans. Restart OpenCode after configuration changes.

For an explicitly requested staging task, start:

```bash
opencode --agent kbds-stage --model qwen-local/qwen3.8-27b
```

Use Tab to switch primary agents. Selecting kbds-stage does not approve copying.
Approve each permission request once; do not use --auto or blanket approvals.
Give the approved canonical source, NEW destination, workspace and explicit mode.
After planning, inspect the full mapping reports at the paths provided in chat.
Approve the exact plan SHA in chat before allowing apply. The agent then runs
apply and verify and reports the validation actually performed.

Review denies bash, writes and grep. Staging allows only prompted toolkit command
forms and edits to the two local policy/decision files. Native grep is denied
because its permission pattern matches search expressions, not the read tool's
blocked file paths. The rules are application controls, not an OS sandbox.
OpenCode stores its own sessions outside the dataset. Chat-only does not mean
that OpenCode has no internal state.

## Configure locally for staging, never in public Git

Use config/policy.example.json as the schema. Save your actual policy as the untracked
config/policy.local.json. Set source_root, destination_root and workspace_root to approved,
nonoverlapping absolute paths. Source must exist; destination must not. Their parent directories
must exist. The workspace holds planning reports and must be outside source and destination.
No symlink path components are allowed.

Practice requires mode=practice and allow_practice_zero_bytes=true. Production requires
mode=production and allow_practice_zero_bytes=false. A folder named practice is not permission.

## Inspect, ask, plan

```bash
python3 scripts/kbds.py --policy "$PWD/config/policy.local.json" inventory --summary
python3 scripts/kbds.py --policy "$PWD/config/policy.local.json" plan --name draft-001
```

The first draft normally exits **2 / WAITING_FOR_USER**, because decisions have not been supplied.
This is expected. A new report folder is created under workspace_root; source and destination
are unchanged. Read inventory.tsv and unresolved.tsv. These reports can contain private paths.

Answer biological questions and let the agent prepare untracked config/decisions.local.json.
Use config/decisions.example.json as a schema example, not as real facts. Every source file needs
an explicit include/exclude decision and reason. Includes need evidence, repository and study.
KRA includes also need confirmed local sample/experiment/run labels, PAIRED/SINGLE layout and
raw_confirmed=true. The code does not auto-read spreadsheets or invent missing metadata.

```bash
python3 scripts/kbds.py --policy "$PWD/config/policy.local.json" plan \
  --name reviewed-001 --decisions "$PWD/config/decisions.local.json"
```

Read plan.json, file_mapping.tsv, sample_mapping.tsv, excluded.tsv and unresolved.tsv.
Only READY_FOR_APPROVAL can execute. Review exact source/destination, counts, bytes and the
plan SHA-256. A changed source, decision or policy needs a new plan and approval.

## Apply only after approval

Replace the following paths/hash with the approved plan values:

```bash
python3 scripts/kbds.py --policy /absolute/config/policy.local.json apply \
  --plan /absolute/workspace/reviewed-001/plan.json --approve-plan FULL_PLAN_SHA256
python3 scripts/kbds.py --policy /absolute/config/policy.local.json verify \
  --plan /absolute/workspace/reviewed-001/plan.json
```

The hash flag acknowledges one exact plan; it **does not authenticate a human independently**.
A model with unrestricted shell/code access can bypass application rules. OS permissions and
an independently controlled approval gateway are required for hard isolation. Read docs/SAFETY.md.

## Output

```text
KBDS_ExampleStudy/
  KRA/ExampleStudy/Specimen01_Blood/Library01_WES/LocalRun01/original_R1.fastq.gz
  KRA/ExampleStudy/Specimen01_Blood/Library01_WES/LocalRun01/original_R2.fastq.gz
  KEA/ExampleStudy/<original relative paths, only if approved>
  KVar/ExampleStudy/<original relative paths, only if approved>
  KNA/ExampleStudy/<original relative paths, only if approved>
  review/ExampleStudy/<explicitly retained files only>
  metadata/
    plan.json
    inventory.tsv
    file_mapping.tsv
    sample_mapping.tsv
    excluded.tsv
    unresolved.tsv
    events.jsonl
    COMPLETE.json
```

Only selected repositories are created. These are local staging conventions, not an automatically
recognized K-BDS upload package. Eligibility, metadata and upload approval are separate. Outputs
always set submission_ready=false. Unknown files block execution until included/excluded explicitly.

## SSH wrapper

Verify the server's identity and authorized login yourself first. Keep credentials outside the
agent's readable scope. Install the toolkit and local policy on the server separately, then run
from a computer with existing SSH access:

```bash
python3 scripts/remote_stage.py --host lab-alias \
  --remote-tool /srv/toolkit/scripts/kbds.py \
  --policy /srv/private/policy.local.json inventory
```

Supported actions: inventory, plan, apply, verify. The wrapper streams stdout/stderr, enables
BatchMode and StrictHostKeyChecking, and disables forwarding. It does not install remotely,
provide network access, bypass authentication, or grant a safe filesystem scope by itself.
Password-only/interactive logins may require manual server-side execution. Remote commands use
the remote account's permissions. A lost SSH connection does not prove copying has stopped.

## Validation and tests

No move/delete/overwrite/permission-changing operations. Reject symlinks, path escapes,
incomplete inventories, collisions, missing decisions, split/missing mates and changed sources.
Keep partial output after failure; never merge, delete or auto-resume it.

Practice validates paths and empty sizes only. Production checks SHA-256 and supported four-line
KRA FASTQ/gzip/read pairs; other repositories receive byte checks only. No scientific or official
submission validation is claimed. KRA BAM/CRAM, metadata-preparer and web UI are not implemented.

Verification also compares every generated plan/TSV report with the approved plan, checks the
copy-event sequence, and validates all completion fields. Production without KRA records
sha256_only; practice records paths_and_empty_sizes_only. Old outputs with incorrect completion
claims fail verification. Inspection can still read old records; verification does not repair them.

```bash
python3 -B -m unittest discover -s tests -v
```

Tests use synthetic temporary files only and never connect to a research server.
See docs/SAFETY.md and docs/ROADMAP.md before real-data use.

## Official references

- https://kbds.re.kr/submission/navigation
- https://kbds.re.kr/submission
- https://www.ncbi.nlm.nih.gov/sra/docs/submitmeta/

No research datasets, credentials, live-site paths or official accessions are bundled.
