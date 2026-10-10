# Output layout and decision schema

## Roots and routing

For a single confirmed repository, use a new sibling `<source>_makeup`.
For multiple repositories, create independent sibling `<source>_KRA_makeup`,
`<source>_KEA_makeup`, and/or `<source>_GEO_makeup` outputs, only when their routes
are confirmed. Use one policy and plan per output; never widen the writable root to the parent.
Each policy has `layout_version: 2` and one `repository_scope`.

In every output, separate `<output-name>_bulk` and `<output-name>_single_cell`.
Create only the categories that are actually included. Do not treat SINGLE read layout as
single-cell modality; paired/single reads and bulk/single-cell are independent fields.

Example (synthetic names; source files retain their exact filenames):

```text
Example_makeup/
  Example_makeup_bulk/
    Study01/
      B/
        ID001/
          WES_B/Run_B/R1/ID001-B_1.fastq.gz
          WES_B/Run_B/R2/ID001-B_2.fastq.gz
      D/
        ID001/
          WES_D/Run_D/R1/ID001-D_1.fastq.gz
          WES_D/Run_D/R2/ID001-D_2.fastq.gz
      R/
        ID001/
          RNA_library/Run_R/R1/ID001-R_1.fastq.gz
          RNA_library/Run_R/R2/ID001-R_2.fastq.gz
  metadata/
```

KRA path relative to its output:
`<output-name>_<modality>/<study>/<sample_group>/<sample>/<experiment>/<run>/<file_role>/<original_filename>`.

- `sample_group`: confirmed B, D or R label. Keep these as separate Sample branches.
  Confirm what each token means for this dataset; a token is not a specimen type or BioSample.
- `sample`: confirmed local ID inside its B, D or R branch. The same ID in different branches
  does not prove a biological relationship. `specimen` records the confirmed specimen identity.
- `experiment` and `run`: retain distinct library/Run identities. Do not put B and D
  into one Run merely to make four files appear together. Each paired Run has one R1/R2 pair.
- `file_role`: R1/R2 for confirmed pairs, or single for SINGLE layout. The B/D/R label
  belongs to the Sample branch, not the file-role directory. Original filenames stay unchanged.

Other repositories use:
`<output-name>_<modality>/<study>/<original_relative_path>`.
Keep matrix.mtx, barcodes.tsv and features.tsv (or genes.tsv) together at their original
relative location. No flattening, duplicate removal or matrix merging.

## Decisions

Direct-host policy is private JSON with exactly these keys: `version: 1`,
`layout_version: 2`, `repository_scope`, `mode: practice|production`, absolute
`source_root`, `destination_root`, `workspace_root`,
`allow_practice_zero_bytes` (true only in practice), and nonnegative integer
`reserve_bytes`. Example values in the full repository's `config/policy.example.json`
are synthetic and must not be reused as live paths. Decisions JSON has the shape
`{"files":{"relative/name":{"action":"exclude","reason":"confirmed reason"}}}`;
each include also needs the fields below. OpenCode uses the ignored
config/policy.local.json and config/decisions.local.json so its edit permissions match.
Other agents may keep these JSON files in an approved private directory. Plans and reports
remain in workspace_root, outside source and destination.

Every source-relative path must have `action: include|exclude` and a nonempty `reason`.
Includes require `evidence`, `repository`, `study`, `modality: bulk|single_cell`,
`modality_evidence`, and `data_role`. The repository must match policy.repository_scope.
For split outputs, explicitly exclude files routed elsewhere and verify combined coverage
before copying. If any final route is unresolved, ask before executing the affected plans.

KRA also requires `sample_group`, `sample`, `specimen`, `assay`, `experiment`,
`run`, `file_role`, `layout: PAIRED|SINGLE`, `raw_confirmed: true`, and
`data_role: raw_reads`. Record exact supporting metadata or the user's scoped answer.
KEA alignment files additionally require `data_role: processed_functional_genomics`;
the evidence must explain the experiment and intended KEA use, not merely the .bam suffix.
For GEO use roles such as expression_matrix, matrix_barcodes and matrix_features.

Unknowns are questions, not defaults. A user's practice-only assumptions are not permanent
classification rules. General B/D/R mappings are deliberately not supplied by the toolkit.

## Compatibility and collisions

Labels use 1–128 ASCII letters/digits/underscore/hyphen/dot, starting alphanumeric.
Preserve spelling, original filenames and per-file source mappings. Reject traversal,
case-folded/Unicode-normalized collisions and existing output directories.
Never merge files because they have identical names or empty practice hashes.

Policies without layout_version retain legacy layout 1 so old plans can still be checked.
For new jobs use the version-2 example policy. Never rewrite or silently migrate an existing
output/approved plan; change layout through a newly reviewed copy plan.
