# Reliability review

Review date: 2026-10-26. This report describes changes to the reusable toolkit. Examples are
synthetic. Private dataset paths, identifiers, logs and model-session transcripts are excluded.
It records observed defects and their fixes, not a claim that every environment is supported.

## Problems and changes

| Problem | Change | Boundary |
|---|---|---|
| Mate parsing missed dot-separated names and could pair inconsistent conventions. | Accept `.R1/.R2` alongside supported underscore/hyphen forms. Preserve internal replicate tokens. Require both mates to use the same separator, mate-token and chunk pattern. | A filename match does not prove biological pairing. Missing or mixed-convention mates stop for review; source files are never renamed. |
| Whole-path collision checks missed case/Unicode aliases in parent directories and file/directory conflicts. | Compare normalized components at each depth, detect path-prefix conflicts, and reject reserved device names, special path characters, trailing spaces/dots and overlong components. Reserved-name checks also cover `CON .txt`, `NUL .fq`, `CONIN$` and `CONOUT$`. Reject undecodable filenames before serialization. | Source spelling stays unchanged. Linux execution and target-filesystem testing remain required. These checks are not a universal filesystem compatibility guarantee. |
| FASTQ validation accepted invalid sequence symbols, a conflicting repeated `+` title or control characters in read headers. | Require supported IUPAC nucleotide symbols and exact repeated-title agreement. After removing the line ending, reject ASCII control characters in the header except tab. Keep record lengths, quality ranges, read IDs/counts, mate markers and gzip integrity checks. Tab-separated header metadata, CRLF and concatenated gzip remain supported. | Wrapped/interleaved paired FASTQ, colorspace and KRA BAM/CRAM remain unsupported. Other repository files receive byte validation only. |
| Compressed `.fna.gz` was omitted from candidate detection. | Classify it consistently with the existing FASTA candidates in both inventory paths. | Candidate classification does not authorize inclusion or establish nucleotide provenance. |
| TSV text could be interpreted as a spreadsheet formula. | New plans use `report_format_version: 2`. Prefix formula-like TSV text with an apostrophe while retaining exact original strings in `plan.json`. | Machine path readers must use JSON. Old plans keep their original TSV serialization, but stricter current path checks may reject legacy names without rewriting files. |
| A manual report's custom destination label was inserted as HTML. | HTML-escape `destination_label` consistently with other report text. | Custom labels are text, not executable markup. This does not turn a manual report into verification evidence. |
| Generated reports were available only in Korean. | Add optional final `--language ko\|en` to scoped `run` and `report`, defaulting to `ko`. Translate generated narrative, interface and SVG labels locally. Record `report_language` in run stdout. | Supplied evidence, identifiers, paths and manual prose stay unchanged. Language does not change plan/scope hashes or data. Existing reports are never overwritten, even to change language. |
| Session elapsed time mixed model generation, approval waiting and file processing. | `run` returns monotonic `timings_seconds` for scope checks, planning, preflight, copy/metadata, verification and report verification/rendering. | These are tool-process durations. They exclude Qwen generation and permission waits. The report phase includes verification; file timestamps are not exact phase timers. |
| A normal final answer could trigger compaction and a synthetic continuation that restarted work. Unchanged reference reads and short command timeouts added delay or interrupted copies. | A local OpenCode guard records successful reference ranges and hashes in existing session metadata, restores state from history, blocks redundant reads within a genuine user turn, and locks tool use after a verified bundled run/report. The continuation hook respects persisted final-stop state. Recognized `apply`/`run` calls receive at least 600000 ms. | A post-final summary can still occur. Genuine new user messages start a new turn. Changed references, unread ranges and mutable data/control files remain readable. Hooks are tested against OpenCode 1.18.35. |
| Broad shell permission patterns alone did not validate command structure. | The guard accepts documented single `python3 scripts/kbds.py` commands, absolute control paths and the toolkit working directory. It rejects shell chains, redirection, substitutions, wrappers, newlines and unquoted expansion. Quoted spaces and Unicode paths are supported. | Existing permission prompts still apply. The guard grants no approval and is not an OS sandbox. |
| OpenCode `--pure` skipped the project guard. | Installation guidance requires normal project loading and checks the effective configuration. It distinguishes disabling bundled default plugins from disabling all project plugins. | Do not use `--pure` or `OPENCODE_PURE=true` for the guarded workflow. Recheck loading after upgrades or deployment changes. |
| A local Qwen chat template rejected additional system messages used for runtime guidance. | Combine existing system instructions and stable runtime rules into one initial system message while preserving instruction order. | This is compatibility with the selected local template, not proof of compatibility with every model or template. |
| After summarization, the model could reconstruct control-file paths from the output workspace and select the wrong location. | Include canonical `project_root` and the fixed absolute paths of `config/policy.local.json` and `config/decisions.local.json` in stable runtime instructions. The model can reuse explicit paths instead of deriving them from `workspace_root`. | These paths identify existing control locations. They grant no new approval, do not modify the frozen scope, and do not broaden writable roots. |
| Updating `references_read` inside the initial system message after each reference read invalidated the long shared prompt prefix in llama.cpp and caused another large prefill. | Keep the initial runtime instructions stable: project/control paths and general reuse/stop rules. Insert dynamic read history, status and report paths only into the compaction checkpoint. Current-state tool gates, history restoration, turn boundaries and the continuation guard remain active. | This removes the identified source of prefix changes. End-to-end speed has not been re-measured after the change; no speedup figure is claimed. Model processing and compaction can still take time. |
| SSH state paths could resolve away links before checks; cleanup could remove unexpected state; output reservation was late or absent; nonfinite timeouts were accepted. | Reject symlink/junction components before resolution, reserve a new output before sending a request, honor direct SSH `--output`, and require finite positive timeouts. Cleanup removes only recognized unchanged bridge files and otherwise preserves the state directory. | The optional bridge needs a trusted local account. It does not authenticate remote human approval, store passwords or replace SSH host verification. Server-local Qwen does not use it. |
| Setup and classification guidance was difficult to reuse outside one language and consumed unnecessary context. | Add an English entrypoint and support matrix while preserving the Korean guide. Keep report instructions in English. Move the legacy-only practice schema to a conditional reference. Fix a broken reference link and document failure recovery and exact-scope limits. | A fixed scope authorizes a fresh package, not updates to a completed output. Unsupported document extraction and scientific formats are stated explicitly. |
| CI covered one implicit Linux Python version, and common research extensions were easy to add to Git accidentally. | Configure Linux Python 3.10/3.14, Windows Python 3.14 pure-logic coverage, and Node 22 guard tests. Extend data-file ignore patterns while allowing synthetic test fixtures. | Git ignores do not inspect content or prevent forced additions. Review every public diff for private data. Windows tests do not establish Windows staging support. |

## Validation recorded for this review

- Linux: 118 Python tests discovered; 117 passed and one Windows-only check skipped.
- Windows: 118 Python tests discovered; 54 passed and 64 Linux filesystem tests skipped.
- OpenCode guard: all 19 behavioral tests passed, including report-language commands, control paths and a stable initial system prefix.
  CI targets Node.js 22.
- Synthetic copy/verify/report checks remain separate from model-session acceptance tests.
- Markdown reference links, example JSON syntax, ignore rules and whitespace checks passed.

Run the checks from the repository root:

```bash
python3 -B -m unittest discover -s tests -v
python3 -B scripts/kbds.py self-check
node --test tests/test_session_guard.mjs
```

These results do not claim that a private live-data job has finished. They do not prove
large-file throughput, behavior under hostile concurrent filesystem mutation, scientific
correctness or archive submission readiness. CI results after push must be checked separately.

## Remaining boundaries

Sources remain immutable; outputs must be new and disjoint. Partial output is retained after
failure. No automatic merge, resume, cleanup, biological inference or archive upload was added.
Production KRA support remains limited to the documented FASTQ subset. Other repository
formats use `sha256_only`; PDF/HWP/Excel extraction and official submission schemas are not
implemented. OS access controls, supported storage, model/template compatibility and release
permissions require validation in each deployment. License selection remains an owner decision.

See [safety and platform limits](SAFETY.md), the [roadmap](ROADMAP.md), and the
[installation guide](../README.md) before broader deployment.
