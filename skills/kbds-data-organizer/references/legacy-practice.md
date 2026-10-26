# Large legacy KRA practice scopes

For a large practice inventory already shaped as
`KRA/<study>/<old_sample>/<experiment>/<run>/<filename>`, an optional `practice_rule`
avoids writing thousands of JSON entries through model context. It is forbidden in production.
The user must explicitly confirm the fictional rule, suffix groups, modality, read layout and
metadata exclusion. Do not supply defaults or treat this confirmation as biological evidence.

This rule uses the study/experiment/run folder labels, strips the confirmed suffix from
old_sample to obtain sample, retains old_sample as the fictional specimen label, and takes
the last underscore segment of experiment as the fictional assay label. PAIRED file roles
come from supported mate suffixes; SINGLE uses single. Unknown/ambiguous layouts remain
unresolved. Explicit per-file entries may handle separately confirmed exceptions.

The source_plan must be a complete discovery plan inside workspace_root with the same policy.
Its full hash and inventory signatures lock the scope. Changed or added files block expansion;
obtain a new discovery scope and rule confirmation. Metadata exclusion applies only to
metadata candidates under metadata/ in that locked scope. Expanded decisions and the rule
are retained in the NEW plan; without an approved scope, its full hash needs human copy approval.

The decisions object has only files and practice_rule. files:{} is valid with this rule.
Do not copy policy keys version/layout_version or invent *_pattern fields. Use layout,
not read_layout. On a schema error, correct the listed keys before generating another plan;
do not repeat the same command or reload all references.
sample_suffix_groups is a JSON object mapping suffix strings to B/D/R strings, not an array.
Its suffixes match the old_sample folder in the third path segment, not FASTQ filenames.
Check the actual folder labels before requesting confirmation; do not repeat a confirmed
inclusion decision when the missing item is a folder naming rule.

Synthetic shape only; use actual authorized absolute paths and confirmed values:

```json
{
  "files": {},
  "practice_rule": {
    "kind": "legacy_kra_bdr",
    "source_plan": "/approved/work/discovery/plan.json",
    "source_plan_sha256": "REPLACE_WITH_FULL_DISCOVERY_HASH",
    "fictional_confirmed": true,
    "sample_suffix_groups": {"_X": "B", "_Y": "D", "_Z": "R"},
    "layout": "PAIRED",
    "modality": "bulk",
    "reason": "Explicit fictional practice rule approval",
    "evidence": "Record the user's exact scoped rule confirmation",
    "modality_evidence": "Record explicit fictional bulk approval",
    "exclude_metadata_reason": "Record explicit exclusion of existing metadata records"
  }
}
```
