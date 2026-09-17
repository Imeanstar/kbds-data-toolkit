# Safety and limitations

v0.1 is an executable staging prototype, not a hardened autonomous production service.
Tests use synthetic temporary files only. They are not a security audit, a live-SSH test or
proof of resistance to malicious concurrent filesystem changes. No research server was modified.

## Implemented checks

Copy-only writes, disjoint roots, no-follow descriptor walks, exclusive output creation,
explicit include/exclude decisions, exact plan-hash acknowledgement, source inventory rechecks,
free-space check, file hashes and supported KRA FASTQ validation. Original names are preserved.
No delete, move, chmod, chown, sudo, hardlink, compression, deduplication or automatic cleanup.
Reading can update filesystem access times. Partial output remains after failure.

## Human approval is not independently enforced

The --approve-plan flag binds execution to a particular plan, but a model with unrestricted
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
unwrapped four-line KRA FASTQ (gzip through EOF, lengths, quality characters, paired IDs/counts
and available read markers), copies bytes and verifies destination sizes/hashes. Lines over
16 MiB and wrapped FASTQ are unsupported. No biological provenance or full archive metadata
validation is performed. Other repositories receive byte checks only. KRA BAM/CRAM is unsupported.
Full scans and hashes can be I/O-intensive; get data-owner approval. No automatic resume/reflinks.

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
