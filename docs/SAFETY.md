# Safety and limitations

v0.1 is an executable staging prototype, not a hardened autonomous production service.
Repository tests use synthetic temporary files only and do not contact research servers.
They are not a security audit, a live-model acceptance test or proof of resistance to malicious
concurrent filesystem changes. Operator-run private acceptance jobs are separate evidence.

## Implemented checks

Copy-only writes, disjoint roots, no-follow descriptor walks, exclusive output creation,
explicit include/exclude decisions, exact plan-hash acknowledgement, source inventory rechecks,
free-space check, file hashes and supported KRA FASTQ validation. Original names are preserved.
No delete, move, chmod, chown, sudo, hardlink, compression, deduplication or automatic cleanup.
Reading can update filesystem access times. Partial output remains after failure.

Verification compares the staged plan and TSV bytes with their approved-plan serialization,
checks copy events in order, and validates every completion field. Production without KRA
records checksum validation only. Filesystem helpers reject sensitive path components before
opening data or control files, including when .aws is selected as a root.
OpenCode denies native grep because its regex permission does not enforce read-path rules.

New plans use `report_format_version: 2` to escape formula-like text in TSV exports with a
leading apostrophe. This protects common spreadsheet opening, not every spreadsheet import
configuration. Exact strings remain in plan.json; use JSON for machine path processing.
Older plans retain their original TSV serialization so that verification remains reproducible.
Current stricter path checks still apply: a legacy package with nonportable names can stop
verification with a specific error. Existing files are not rewritten or repaired.

## Human approval is not independently enforced

The --approve-plan flag binds execution to a particular plan. The optional scoped `run`
command binds exact policy and classification decisions to --approve-scope and automatically
generates/executes matching plans. Unknown files and other validation errors still stop the job.
The model cannot edit the scope file through the bundled profile. This is not independent
authentication: a model with unrestricted
shell access can supply that hash. AGENTS.md forbids inventing approval; a prompt is not a hard
security boundary. The independently authenticated human gateway is NOT implemented in v0.1.
Do not describe this prototype as guaranteeing that a misbehaving model cannot bypass approval.

## OS isolation

An account with arbitrary writes can bypass the Python program. An administrator must enforce
read-only source and source-parent rights, scoped destination/workspace access, immutable reviewed
code/policy and separation from the general research account. Do not casually modify existing lab
permissions. Begin in an isolated test account or environment. Deny sudo and access to credentials.

No-follow checks reduce accidental symlink traversal but do not defend all rename/mount/hardlink
races or hostile concurrent root replacement. Do not permit other writers to mutate staging roots.
A local Codex sandbox does not automatically restrict a remote SSH account.

## Production validation scope

Production rejects zero-byte included files. It inventories and rechecks SHA-256, validates
unwrapped four-line KRA FASTQ (gzip through EOF, IUPAC nucleotide symbols, lengths, repeated
plus-line identifiers when present, quality characters, paired IDs/counts and available read
markers), copies bytes and verifies destination sizes/hashes. Lines over 16 MiB, wrapped FASTQ,
colorspace and interleaved paired reads are unsupported. No biological provenance or full archive
metadata validation is performed. Other repositories receive byte checks only. KRA BAM/CRAM
is unsupported. A successful byte copy does not validate a matrix, variant or alignment file.
Full scans and hashes can be I/O-intensive; get data-owner approval. No automatic resume/reflinks.

## Platform and filename boundaries

Filesystem operations require Linux and its no-follow directory-descriptor support. Windows
and macOS cannot run the staging engine. Pure-logic Windows tests are not Windows staging tests.
Use UTF-8 control files. Original Unicode names are preserved; new grouping labels use the
documented ASCII subset. The plan rejects normalized/case-folded component aliases,
file/directory collisions, Windows-reserved names, special path characters and trailing
spaces/dots in destination components. Components longer than 255 UTF-8 bytes and undecodable
source filenames are blocked. It does not rename or sanitize source files to pass.
Portable-name checks do not certify every filesystem's length limits, Unicode handling or
network storage behavior. Test the intended storage with synthetic files before real data.
Output permissions are private by default; original owner, ACLs, extended attributes and
timestamps are not a preserved archival copy of the source filesystem.

## Practice, failure and cancellation

Practice accepts only empty included data placeholders. It validates path/copy and pair-name
handling, not sequencing data. Never deduplicate different placeholders by empty hashes.
Outputs always set submission_ready=false. Completion is recorded only after verification.
A disconnected/killed SSH client may leave a remote process running. Reconnect and inspect the
state before retrying. No remote stop/rollback service exists. Existing output blocks re-execution;
never remove partial output automatically. Use a new destination only after review and approval.

## Confidentiality

Public Git must contain synthetic examples only. Keep real IDs, paths, inventories, decisions,
clinical metadata, policies, credentials and logs private. Directory staging is not permission to
send data to an external model or public archive. Confirm institutional release policy separately.
