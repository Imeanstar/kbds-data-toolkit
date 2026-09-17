# Naming and evidence

KRA: `KRA/<study>/<sample>/<experiment>/<run>/<original_filename>`.
Other repositories: `<repository>/<study>/<original_relative_path>`.
These are local human-readable conventions, not mandated archive directory layouts.

Require confirmed unique local labels. Preserve filenames and evidence. New labels use ASCII
letters/digits/underscore/hyphen/dot, starting alphanumeric. Block traversal and case-folded or
Unicode-normalized destination collisions. Never silently normalize distinct identifiers.

A subject/patient/donor is not automatically a BioSample. Tissue, time point, specimen, extraction
and replicate relationships require authoritative records or explicit human answers. Never merge
DNA and RNA into one sample because numeric codes match. Do not invent cell line, organism,
library strategy, selection, instrument or study facts from another project's example.

SampleSheet labels are not assigned BioSample accessions. Facility projects are not necessarily
Studies. An Experiment is not a downstream analysis folder. A flow cell/lane is provenance,
not a universal Run identifier; a batch folder date is not a confirmed sequencing date.
Repeated SampleSheet rows are repeated evidence, not proof of multiple experiments or runs.

R1/R2 and _1/_2 suffixes support filename-pair candidates, not validated paired reads. Practice
cannot inspect reads. Confirm local layouts with the user; use production content checks later.
Unconfirmed official metadata stays unresolved. Local placeholders may be used only when explicitly
approved as such, and the output must remain marked not submission-ready.
