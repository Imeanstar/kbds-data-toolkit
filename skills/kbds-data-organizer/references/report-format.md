# Private HTML report

Create one self-contained HTML file. It must use no remote images, CSS or fonts. The browser's
print button can export PDF. The renderer defaults to Korean (`ko`) and also supports English
(`en`). It does not translate supplied evidence, identifiers, paths or manual report prose.
Explain results in the user's requested chat language.

## Content

1. Report title.
2. Full source and output paths, right-aligned under the title.
3. A structure diagram of the actual verified output: Study → Sample → Experiment → Run →
   file roles. Include counts. Separate confirmed B/D/R Sample branches; R1/R2 are file roles.
4. Findings: file counts, bytes, formats, classification/copy/verification state, exclusions,
   unresolved items and validation limits.
5. Recorded structural relationships and evidence. Distinguish confirmed facts, explicitly
   fictional practice assumptions, and unresolved interpretations.

Label any unexecuted structure as planned. Do not show a new layout as an existing result.
Do not replace unknown counts with zero. Practice assumptions belong only to this dataset's
private records and report, not to reusable classification defaults. Do not equate local IDs
with official archive accessions or claim submission readiness.
Describe approved organization decisions from plan.json. Do not create a separate sample
metadata table, fill research/submission fields, or turn practice labels into biological facts.
Metadata preparation belongs to another tool; the HTML explains this skill's execution result.

## Verified plan report

After an authorized `apply`, use the repository wrapper:

```bash
python3 scripts/kbds.py report --plan /approved/work/job-001/plan.json
```

For English, append `--language en` as the last option; `--language ko` explicitly selects
Korean. This translates generated narrative, interface and SVG labels without changing
scope/plan hashes or copied data. Choose the language before creating the report: switching
languages does not permit overwriting an existing `report.html`.

`kbds-stage` can request this command. `kbds-review` produces a chat report only. An approved
scoped `run` performs the report step automatically; do not run it again after COMPLETE.
For a standalone skill, `<skill-dir>/scripts/build_html_report.py --plan ...` is equivalent.

The generator verifies a completed layout-version-2 output and creates a new `report.html`
beside its plan. It never overwrites a report. The inline SVG counts recorded Study, Sample,
Experiment, Run and file-role branches. Non-KRA output must not invent Sample/Experiment/Run
relationships absent from mappings. A practice label is not biological evidence.

`run` reports measured `timings_seconds` in stdout. Separate tool durations from model
generation, approval waits and total session elapsed time. The report phase includes verification;
do not describe it as HTML rendering alone. Do not estimate exact phases from file timestamps.
New TSV cells that could execute a spreadsheet formula are prefixed with an apostrophe;
exact original strings remain in plan.json (`report_format_version: 3` for new plans).

Keep the report in the private workspace. Moving it to a user's approved computer is a separate
authorized action; never publish it with the reusable skill. The plan, mappings and logs can
contain private identifiers and full paths.

## Optional reviewed manual report

For a separately authorized manual report, use:

```bash
python <skill-dir>/scripts/build_html_report.py --data /approved/report.local.json --output /approved/new-report.html
```

This mode does not verify a staged package. Its JSON must contain `title`, `source_path`,
`destination_paths`, `structure_image`, `results` and `relationships`. The three lists
`destination_paths`, `results` and `relationships` must contain nonempty strings.
`structure_image` must be an existing PNG, absolute or relative to the JSON file. Optional
fields are `image_caption`, `image_alt` and `destination_label`. Use a new private output path.
Append `--language en` to the manual command for English interface labels; its supplied prose
stays unchanged. Text, including a custom `destination_label`, is HTML-escaped. Both modes
use the Python standard library only and call no external translation service.

Check text encoding and title/path/diagram/body order. Do not claim visual or print QA on a
headless host. When a browser is available, inspect readability and print clipping. Export PDF
only when requested. Do not reinterpret a manual report as verification evidence.
