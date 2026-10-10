# Classification and archive routing

No file extension proves biological provenance, modality or archive eligibility.
Candidates support questions; only explicit evidence and decisions authorize a plan.

## Default review priorities

| Evidence | Candidate / action |
|---|---|
| Raw sequencing FASTQ | KRA; confirm raw provenance and sample/library/Run mapping |
| BAM, CRAM, SAM | Ask about raw/aligned origin and assay; do not automatically send to KEA |
| Expression/count matrix | GEO candidate under this user's workflow; KEA may also accept functional-genomics data |
| barcodes.tsv + matrix.mtx + features.tsv (or genes.tsv), optionally gzip, in one directory | Single-cell MEX candidate; keep all companions together |
| VCF/BCF | KVar candidate; confirm content/provenance |
| FASTA | KNA candidate; could instead be protein/reference data |
| Unknown or conflicting evidence | Ask; no automatic inclusion, exclusion or bulk default |

The correct abbreviation is KEA (Korea/Korean Expression Archive), not KAE.
KRA accepts raw read data in formats including BAM; BAM is therefore not synonymous with KEA.
KEA covers functional genomics, including bulk and single-cell RNA-seq and epigenomics.
For a confirmed functional-genomics BAM assigned to KEA, use the user's KEA output;
for a genomic WES/WGS BAM or unclear BAM, ask rather than forcing that route.
The toolkit currently cannot validate KRA BAM/CRAM for staging.

GEO is NCBI's Gene Expression Omnibus, separate from K-BDS. Expression matrices can be prepared
in a GEO output at the user's preference; GEO also requires metadata and appropriate raw-data
linkage. A count matrix alone is not a complete submission and GEO is not its only possible archive.

## Bulk versus single-cell

The three commonly intended names are cell barcodes, count matrix, and gene/feature annotations.
The same-directory MEX trio is strong candidate evidence, not universal proof: related matrix
formats can represent nuclei, spatial spots or different feature types. Confirm the protocol
and which FASTQ/library the matrix belongs to. A matrix in one sample must not label the whole
study as single-cell. FASTQ-only datasets may be bulk or single-cell.
HDF5/AnnData and non-10x workflows may have no three-file set; ask using their metadata.

Preserve raw/filtered matrix distinctions. Spatial or other data that cannot be confidently
assigned to the two requested modality groups remain unresolved.
R1 may contain barcodes/UMIs in single-cell data; do not claim both mates are transcript reads.

## Evidence boundaries

B, D and R are local folder labels, not specimen types or official BioSamples. Confirm their
meaning for each dataset. Blood is a specimen source; DNA/RNA are molecules. WES remains WES.
Do not infer token meanings, tissue, time point, extraction/library identity, reference genome
or organism from a patient ID. Batch names preserve provenance but do not establish Run identity.
IRB approval alone does not describe the data's release permissions.

Primary sources checked 2026-09-22:
- K-BDS submission guide (KRA raw FASTQ/BAM, KEA processed functional genomics):
  https://kbds.re.kr/submission/navigation
- KEA scope: https://kbds.re.kr/KEA
- GEO sequencing submissions: https://www.ncbi.nlm.nih.gov/geo/info/seq.html
- 10x feature-barcode MEX files:
  https://www.10xgenomics.com/support/software/cell-ranger/latest/analysis/outputs/cr-outputs-mex-matrices

Recheck official requirements when implementing a submission, not on every local copy.
