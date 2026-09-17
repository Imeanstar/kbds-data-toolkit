# Scope and roadmap

Implemented: repository AGENTS.md, standalone skill, inventory/candidate classification,
explicit decision-based planning, copy-only staging, handoff reports, practice/production
validation, JSON progress events, OpenSSH wrapper and synthetic unit tests.

Not implemented: web dashboard, independently authenticated approval gateway, automatic
scientific interpretation of SampleSheets/Excel, full repository schema validators, official
metadata-preparer, K-BDS uploader, automatic copy resume/cleanup/rollback or live-server tests.

The future metadata-preparer will consume plan.json, inventory.tsv, file_mapping.tsv,
sample_mapping.tsv, unresolved.tsv and excluded.tsv. Preserve local IDs, evidence, omissions
and explicit decisions. Ask for specimen/library/instrument/submission information and consult
current official templates. Do not infer a subject is a BioSample or a local batch is an SRA Run.

Before wider deployment: run isolated practice acceptance tests, review OS permissions and
network access, implement an independent approval/execution boundary, test interruption and
large-file behavior, and obtain data-owner approval. A web UI can consume the same progress events.
