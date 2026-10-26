# Scope and roadmap

Implemented: repository AGENTS.md, standalone skill, inventory/candidate classification,
explicit decision-based planning, copy-only staging, handoff reports, practice/production
validation, JSON progress events, OpenSSH wrapper and synthetic unit tests.

Not implemented: web dashboard, independently authenticated approval gateway, automatic
scientific interpretation of SampleSheets/Excel, full repository schema validators,
K-BDS uploader, automatic copy resume/cleanup/rollback, native Windows/macOS
staging, report languages beyond Korean/English or automated live-model CI tests.

Research and submission metadata preparation is outside this skill and belongs to another tool.
New jobs produce execution records under audit/ and a private HTML report, not sample metadata
tables or official submission sheets. A separate tool may inspect approved decisions and copy
evidence, but must establish its own research facts and current submission requirements.
No metadata-tool integration or official schema conversion is implemented or promised here.

Before wider deployment: run isolated acceptance tests on the intended Linux filesystem,
review OS permissions and network access, establish an independent approval/execution boundary
where required, test interruption and large-file behavior, and obtain data-owner approval.
Private placeholder acceptance runs do not establish production-data correctness. Keep dataset
names, paths and logs out of public reports and fixtures. A web UI can consume progress events.

There is no promise of support for every scientific format, operating system or local archive
rule. Add validators only with a defined format/version, primary specification, representative
synthetic valid/invalid samples and failure tests. Do not silently widen `sha256_only` into a
claim of scientific validation. Confirm licensing terms before distributing a wider release.
