# Classification and submission boundaries

A filename classifier proposes candidates only. No extension proves provenance, scientific
validity, repository acceptance or authorization to share. The user selects staging destinations.

- KRA: sequencing-read candidates; v0.1 supports FASTQ content validation, not BAM/CRAM.
- KEA: functional-genomics processed-data candidates, including expression/count tables.
- KVar: variant candidates, including VCF; verify provenance and current submission requirements.
- KNA: nucleotide-sequence candidates; a FASTA might instead be a reference download or protein.
- review: material explicitly retained for review, never automatically submitted.

Trimmed, filtered, unpaired or subsample names trigger review, not silent deletion or universal
rejection. Metadata can live under analysis directories. Do not exclude a whole tree just because
its name suggests processing. Metadata conflicts require questions. A demultiplexing Control=N
field is not evidence that a specimen is not a biological experimental control.

K-BDS uses separate submission workflows; naming a directory KRA/KEA/KVar does not register it.
A later metadata-preparer must consult current official templates. Do not claim generic DEG
results, pipeline intermediates, every VCF or every FASTA will be accepted.

Primary references checked 2026-09-17; recheck before implementing submission metadata:
- https://kbds.re.kr/submission/navigation
- https://kbds.re.kr/submission
- https://www.ncbi.nlm.nih.gov/sra/docs/submitmeta/

NCBI describes Study, Sample, Experiment and Run as metadata entities. The local tree is not
all database relations. Paired-end files belong to the same Run; a lane is not universally one Run.
