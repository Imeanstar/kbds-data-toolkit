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

## Configure locally, never in public Git

Use config/policy.example.json as the schema. Save your actual policy as the untracked
config/policy.local.json. Set source_root, destination_root and workspace_root to approved,
nonoverlapping absolute paths. Source must exist; destination must not. Their parent directories
must exist. The workspace holds planning reports and must be outside source and destination.
No symlink path components are allowed.

Practice requires mode=practice and allow_practice_zero_bytes=true. Production requires
mode=production and allow_practice_zero_bytes=false. A folder named practice is not permission.

## Inspect, ask, plan

```bash
python3 scripts/kbds.py --policy "$PWD/config/policy.local.json" inventory
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
