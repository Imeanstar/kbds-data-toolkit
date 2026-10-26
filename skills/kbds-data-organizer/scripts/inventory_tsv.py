#!/usr/bin/env python3
"""Write a read-only filename/metadata inventory for one absolute source to TSV stdout."""
import csv
import os
from pathlib import PurePosixPath
import re
import stat
import sys


FASTQ = re.compile(r"\.(?:fastq|fq)(?:\.gz)?$", re.I)


def candidate(path):
    low = path.lower()
    if FASTQ.search(low):
        if re.search(r"trim|unpaired|subsample|filtered|clean|re_fastq", low):
            return "processed_fastq_candidate", "review"
        return "raw_fastq_candidate", "KRA"
    if low.endswith((".vcf", ".vcf.gz", ".bcf")):
        return "variant_candidate", "KVar"
    if low.endswith((".fasta", ".fa", ".fna", ".fasta.gz", ".fa.gz", ".fna.gz")):
        return "sequence_candidate", "KNA"
    if low.endswith((".bam", ".cram", ".sam")):
        return "alignment_requires_review", "review"
    name = PurePosixPath(low).name.removesuffix(".gz")
    if name == "matrix.mtx":
        return "count_matrix_candidate", "GEO"
    if name in ("barcodes.tsv", "features.tsv", "genes.tsv"):
        return "matrix_companion_candidate", "GEO"
    if any(x in low for x in ("samplesheet", "manifest", "metadata")):
        return "metadata_candidate", "review"
    if re.search(r"count|expression", name) and name.endswith((".tsv", ".csv", ".txt", ".mtx", ".h5", ".h5ad", ".xlsx", ".xls")):
        return "expression_candidate", "GEO"
    if "deg" in name and name.endswith((".tsv", ".csv", ".txt", ".xlsx", ".xls")):
        return "functional_genomics_candidate", "KEA"
    return "unknown", "review"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or not argv[0].startswith("/") or argv[0] == "/":
        print("usage: inventory_tsv.py /absolute/source", file=sys.stderr)
        return 2
    source = str(PurePosixPath(argv[0]))
    current = "/"
    try:
        for part in source[1:].split("/"):
            current = os.path.join(current, part)
            mode = os.lstat(current).st_mode
            if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
                raise ValueError("source path contains a symlink or non-directory: " + current)
    except (OSError, ValueError) as exc:
        print("BLOCKED: " + str(exc), file=sys.stderr)
        return 2

    writer = csv.DictWriter(sys.stdout,
        ["record_type", "source_relative", "size", "mtime_ns", "kind",
         "repository_candidate", "message"], delimiter="\t", lineterminator="\n")
    writer.writeheader()
    errors = []

    def failed(exc):
        errors.append(str(exc))

    for base, dirs, files in os.walk(source, topdown=True, followlinks=False, onerror=failed):
        dirs.sort()
        files.sort()
        for name in list(dirs):
            path = os.path.join(base, name)
            try:
                if stat.S_ISLNK(os.lstat(path).st_mode):
                    dirs.remove(name)
                    errors.append("symlink directory blocked: " + os.path.relpath(path, source))
            except OSError as exc:
                dirs.remove(name)
                errors.append(str(exc))
        for name in files:
            path = os.path.join(base, name)
            relative = os.path.relpath(path, source).replace(os.sep, "/")
            try:
                info = os.lstat(path)
                if not stat.S_ISREG(info.st_mode):
                    raise ValueError("nonregular file blocked: " + relative)
                kind, repository = candidate(relative)
                writer.writerow({"record_type": "file", "source_relative": relative,
                    "size": info.st_size, "mtime_ns": info.st_mtime_ns, "kind": kind,
                    "repository_candidate": repository, "message": ""})
            except (OSError, ValueError) as exc:
                errors.append(str(exc))
    for message in errors:
        writer.writerow({"record_type": "error", "source_relative": "", "size": "",
            "mtime_ns": "", "kind": "", "repository_candidate": "", "message": message})
    return 2 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
