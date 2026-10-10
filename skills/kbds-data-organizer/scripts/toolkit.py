#!/usr/bin/env python3
"""KBDS copy-only staging prototype. Linux, Python 3.10+, standard library only."""
from __future__ import annotations

import argparse
import base64
import binascii
import contextlib
import csv
import gzip
import hashlib
import io
import itertools
import json
import os
from pathlib import PurePosixPath
import re
import stat
import sys
import unicodedata
import zlib

VERSION = 1
FILESYSTEM_SUPPORTED = sys.platform.startswith("linux")
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW if FILESYSTEM_SUPPORTED else None
READ_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK if FILESYSTEM_SUPPORTED else None
FASTQ = re.compile(r"\.(?:fastq|fq)(?:\.gz)?$", re.I)
PAIR = re.compile(r"^(.*?)[_-]R?([12])(_[0-9]+)?(\.(?:fastq|fq)(?:\.gz)?)$", re.I)
REPOSITORIES = {"KRA", "KEA", "GEO", "KVar", "KNA", "review"}
MAX_LINE = 16 * 1024 * 1024


class Blocked(ValueError):
    """An explicit stop; never a request to broaden privileges."""


def require(condition, message):
    if not condition:
        raise Blocked(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                     separators=(",", ":")).encode()).hexdigest()


def event(name, **fields):
    print(json.dumps({"event": name, **fields}, ensure_ascii=True), file=sys.stderr, flush=True)


def parts(relative):
    require(isinstance(relative, str) and relative and not relative.startswith("/"),
            "Expected a nonempty relative path")
    result = relative.split("/")
    require(all(p not in ("", ".", "..") and not any(ord(c) < 32 or ord(c) == 127 for c in p)
                for p in result), "Unsafe path component")
    return result


def absolute(value):
    require(isinstance(value, str) and value.startswith("/") and value != "/",
            "Roots must be explicit absolute paths other than /")
    parts(value[1:])
    return value


def label(value):
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value),
            "Labels must start alphanumeric; use 1-128 ASCII letters/digits/underscore/hyphen/dot")
    return value


def sensitive(name):
    name = name.lower()
    return (name in {".ssh", ".aws", ".env", "credentials", "secrets"} or name.startswith((".env.", "id_rsa", "id_ed25519"))
            or name.endswith((".pem", ".key")))


@contextlib.contextmanager
def directory(path, create=False):
    """Walk from / without following symlinks, including ancestor components."""
    require(FILESYSTEM_SUPPORTED, "Filesystem operations require Linux; do not weaken no-follow checks")
    absolute(path)
    require(not any(sensitive(name) for name in parts(path[1:])), "Sensitive directory path blocked")
    fd = os.open("/", DIR_FLAGS)
    try:
        for component in path[1:].split("/"):
            if create:
                try:
                    os.mkdir(component, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            new = os.open(component, DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = new
        yield fd
    finally:
        os.close(fd)


@contextlib.contextmanager
def parent_at(root_fd, relative, create=False):
    components = parts(relative)
    fd = os.dup(root_fd)
    try:
        for component in components[:-1]:
            if create:
                try:
                    os.mkdir(component, 0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            new = os.open(component, DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = new
        yield fd, components[-1]
    finally:
        os.close(fd)


@contextlib.contextmanager
def regular(root_fd, relative, new=False):
    require(not any(sensitive(name) for name in parts(relative)), "Sensitive file path blocked")
    with parent_at(root_fd, relative, create=new) as (parent, name):
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW if new else READ_FLAGS
        fd = os.open(name, flags, 0o600, dir_fd=parent)
        try:
            require(stat.S_ISREG(os.fstat(fd).st_mode), "Not a regular file: " + relative)
            stream = os.fdopen(fd, "wb" if new else "rb")
        except BaseException:
            os.close(fd)
            raise
        with stream:
            yield stream


def signature(st):
    return {"size": st.st_size, "mtime_ns": st.st_mtime_ns, "device": st.st_dev, "inode": st.st_ino}


def hash_stream(stream):
    h = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        h.update(block)
    return h.hexdigest()


def load_json(path):
    path = absolute(str(path))
    parent = str(PurePosixPath(path).parent)
    require(parent != "/", "Store control files below an explicit directory, not directly in /")
    with directory(parent) as fd:
        with regular(fd, PurePosixPath(path).name) as stream:
            return json.load(stream)


def decode_json(value, label):
    try:
        packed = base64.b64decode(value, validate=True)
        try:
            packed = zlib.decompress(packed)
        except zlib.error:
            pass
        return json.loads(packed.decode("utf-8"))
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Blocked("Invalid encoded " + label) from exc


def load_policy(path=None, data=None):
    policy = load_json(path) if path else decode_json(data, "policy")
    required = {
        "version", "mode", "source_root", "destination_root", "workspace_root",
        "allow_practice_zero_bytes", "reserve_bytes"}
    require(isinstance(policy, dict) and required <= set(policy) and
            set(policy) <= required | {"layout_version", "repository_scope"}, "Unknown/missing policy keys")
    validate_layout_policy(policy)
    require(policy["version"] == VERSION, "Unsupported policy version")
    require(policy["mode"] in ("practice", "production"), "Mode must be explicit")
    require(policy["allow_practice_zero_bytes"] is (policy["mode"] == "practice"),
            "Zero-byte exception must be enabled only in practice")
    require(type(policy["reserve_bytes"]) is int and policy["reserve_bytes"] >= 0, "Invalid reserve")
    roots = [absolute(policy[key]) for key in ("source_root", "destination_root", "workspace_root")]
    for a, b in itertools.combinations(roots, 2):
        require(not (a == b or a.startswith(b + "/") or b.startswith(a + "/")),
                "Source, destination and workspace must be disjoint")
    with directory(policy["source_root"]):
        pass
    for target in roots[1:]:
        with directory(str(PurePosixPath(target).parent)):
            pass
    return policy


def validate_layout_policy(policy):
    version = policy.get("layout_version", 1)
    require(type(version) is int and version in (1, 2), "Unsupported layout_version")
    if version == 1:
        require("repository_scope" not in policy, "repository_scope requires layout_version 2")
        return
    scope = policy.get("repository_scope")
    require(scope in REPOSITORIES, "Select one repository_scope per output plan")
    source, destination = (PurePosixPath(absolute(policy[k])) for k in ("source_root", "destination_root"))
    require(destination.parent == source.parent, "Makeup output must be a sibling of its source")
    require(destination.name in (source.name + "_makeup", source.name + "_" + scope + "_makeup"),
            "Use <source>_makeup or <source>_<repository>_makeup")


def classify(path):
    low = path.lower()
    if FASTQ.search(low):
        if re.search(r"trim|unpaired|subsample|filtered|clean|re_fastq", low):
            return "processed_fastq_candidate", "review"
        return "raw_fastq_candidate", "KRA"
    if low.endswith((".vcf", ".vcf.gz", ".bcf")):
        return "variant_candidate", "KVar"
    if low.endswith((".fasta", ".fa", ".fna", ".fasta.gz", ".fa.gz")):
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


def annotate_matrix_candidates(records):
    """Same-directory MEX trio is evidence to review, never an automatic FASTQ assignment."""
    groups = {}
    for row in records:
        p = PurePosixPath(row["source_relative"])
        groups.setdefault(str(p.parent), set()).add(p.name.lower().removesuffix(".gz"))
    for row in records:
        p = PurePosixPath(row["source_relative"])
        names = groups[str(p.parent)]
        trio = {"matrix.mtx", "barcodes.tsv"} <= names and bool(names & {"features.tsv", "genes.tsv"})
        if trio and p.name.lower().removesuffix(".gz") in {"matrix.mtx", "barcodes.tsv", "features.tsv", "genes.tsv"}:
            row["modality_candidate"] = "single_cell"
            row["modality_candidate_evidence"] = "Same-directory MEX trio; confirm cell/nucleus/spatial protocol and FASTQ linkage"


def inventory(policy):
    records, errors = [], []
    with directory(policy["source_root"]) as root:
        def onerror(exc):
            errors.append(str(exc))
        for base, dirs, files, fd in os.fwalk(".", dir_fd=root, follow_symlinks=False, onerror=onerror):
            prefix = "" if base == "." else base[2:] + "/"
            for name in list(dirs):
                try:
                    parts(prefix + name)
                    require(not sensitive(name), "Sensitive directory blocked: " + prefix + name)
                    require(not stat.S_ISLNK(os.stat(name, dir_fd=fd, follow_symlinks=False).st_mode),
                            "Symlink directory blocked: " + prefix + name)
                except (OSError, Blocked) as exc:
                    dirs.remove(name)
                    errors.append(str(exc))
            for name in files:
                rel = prefix + name
                try:
                    parts(rel)
                    require(not any(sensitive(x) for x in parts(rel)), "Sensitive path blocked")
                    with regular(root, rel) as stream:
                        before = signature(os.fstat(stream.fileno()))
                        checksum = hash_stream(stream) if policy["mode"] == "production" else None
                        require(before == signature(os.fstat(stream.fileno())), "Source changed during inventory")
                    kind, candidate = classify(rel)
                    records.append({"source_relative": rel, **before, "sha256": checksum,
                                    "kind": kind, "repository_candidate": candidate})
                except (OSError, Blocked) as exc:
                    errors.append(rel + ": " + str(exc))
    records.sort(key=lambda r: r["source_relative"])
    if policy.get("layout_version", 1) == 2:
        annotate_matrix_candidates(records)
    event("INVENTORY", files=len(records), errors=len(errors), mode=policy["mode"])
    return records, errors


def pair_key(path):
    p = PurePosixPath(path)
    match = PAIR.fullmatch(p.name)
    require(match is not None, "Cannot parse mate suffix; no pairing inference allowed: " + path)
    stem, mate, chunk, extension = match.groups()
    return str(p.parent) + "/" + stem + (chunk or "") + extension.lower(), mate


def target_path(row, policy=None):
    parts(row["source_relative"])
    require(row["repository"] in REPOSITORIES, "Unsupported repository")
    if policy and policy.get("layout_version", 1) == 2:
        validate_layout_policy(policy)
        require(row["repository"] == policy["repository_scope"], "Repository differs from output scope")
        require(row.get("modality") in ("bulk", "single_cell"), "Confirm bulk/single_cell; absence of a matrix is not bulk evidence")
        for key in ("reason", "evidence", "modality_evidence"):
            require(isinstance(row.get(key), str) and row[key].strip(), "Missing " + key)
        prefix = PurePosixPath(policy["destination_root"]).name + "_" + row["modality"]
        segments = [prefix, label(row["study"])]
        if row["repository"] == "KRA":
            require(row.get("sample_group") in ("B", "D", "R"), "Confirm B/D/R Sample grouping")
            for key in ("sample", "specimen", "assay", "experiment", "run"):
                label(row.get(key))
            require(row.get("data_role") == "raw_reads", "Confirm raw-read role")
            role = row.get("file_role", "")
            require(role in ("R1", "R2", "single"), "Confirm R1/R2 or single file_role")
            if row.get("layout") == "PAIRED":
                require(role.endswith("R" + pair_key(row["source_relative"])[1]), "file_role disagrees with mate suffix")
            else:
                require(role.endswith("single"), "SINGLE layout requires a single role")
            segments += [row["sample_group"], row["sample"], row["experiment"], row["run"], role,
                         PurePosixPath(row["source_relative"]).name]
        else:
            require(isinstance(row.get("data_role"), str) and row["data_role"].strip(), "Confirm processed data role")
            if row["source_relative"].lower().endswith((".bam", ".cram", ".sam")):
                require(row["repository"] == "KEA" and row["data_role"] == "processed_functional_genomics",
                        "Alignment requires confirmed functional-genomics KEA routing; BAM alone is insufficient")
            segments += parts(row["source_relative"])
        return "/".join(segments)
    segments = [row["repository"], label(row["study"])]
    if row["repository"] == "KRA":
        segments += [label(row[k]) for k in ("sample", "experiment", "run")]
        segments += [PurePosixPath(row["source_relative"]).name]
    else:
        segments += parts(row["source_relative"])
    return "/".join(segments)


def validate_rows(rows, mode, policy=None):
    seen, pairs, experiments, sources, runs = set(), {}, {}, set(), {}
    for row in rows:
        require(row["source_relative"] not in sources, "A source is included more than once")
        sources.add(row["source_relative"])
        target = row["destination_relative"]
        require(target == target_path(row, policy), "Destination must follow the approved naming scheme")
        parts(target)
        normalized = unicodedata.normalize("NFC", target).casefold()
        require(normalized not in seen, "Destination collision: " + target)
        seen.add(normalized)
        if mode == "practice":
            require(row["size"] == 0, "Practice copy permits empty placeholders only")
        else:
            require(row["size"] > 0, "Zero-byte data blocked in production")
        if row["repository"] != "KRA":
            continue
        require(FASTQ.search(row["source_relative"]) is not None,
                "v0.1 stages KRA FASTQ only; other KRA formats need a future validator")
        require(row.get("raw_confirmed") is True, "Raw provenance must be explicitly confirmed")
        require(row.get("layout") in ("PAIRED", "SINGLE"), "Missing confirmed layout")
        experiment = tuple(row[k] for k in ("study", "sample", "experiment"))
        previous = experiments.setdefault(experiment, row["layout"])
        require(previous == row["layout"], "Conflicting layouts within an experiment")
        if policy and policy.get("layout_version", 1) == 2:
            identity = (row["modality"], row["sample_group"], row["specimen"], row["assay"])
            require(experiments.setdefault(("identity",) + experiment, identity) == identity,
                    "An Experiment cannot merge different specimens/assays/modalities")
            run = (row["study"], row["sample_group"], row["sample"], row["experiment"], row["run"])
            pair = pair_key(row["source_relative"])[0] if row["layout"] == "PAIRED" else row["source_relative"]
            require(runs.setdefault(run, pair) == pair, "Different read pairs require distinct Runs")
        if row["layout"] == "PAIRED":
            key, mate = pair_key(row["source_relative"])
            group = pairs.setdefault(key, {})
            require(mate not in group, "Duplicate mate")
            group[mate] = row
    for key, group in pairs.items():
        require(set(group) == {"1", "2"}, "Missing included mate: " + key)
        a, b = group["1"], group["2"]
        require(all(a[k] == b[k] for k in ("repository", "study", "sample", "experiment", "run", "layout")),
                "Mates assigned to different experiments/runs")
        if policy and policy.get("layout_version", 1) == 2:
            require(all(a[k] == b[k] for k in ("sample_group", "specimen", "assay", "modality", "data_role")),
                    "Mates assigned conflicting metadata")
            require(a["file_role"] == "R1" and b["file_role"] == "R2",
                    "Mates assigned different R1/R2 file roles")
    return pairs


def write_new(fd, relative, data):
    with regular(fd, relative, new=True) as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def json_bytes(data):
    return (json.dumps(data, ensure_ascii=True, indent=2) + "\n").encode()


def tsv_bytes(rows, columns):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, columns, delimiter="\t", extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def make_plan(policy, decisions, name):
    label(name)
    validate_layout_policy(policy)
    require(isinstance(decisions, dict) and set(decisions) == {"files"}, "Decisions require a files mapping")
    require(isinstance(decisions["files"], dict), "files must map exact source-relative paths to decisions")
    records, errors = inventory(policy)
    rows, excluded, unresolved = [], [], []
    known = {r["source_relative"] for r in records}
    for key in sorted(set(decisions["files"]) - known):
        unresolved.append({"source_relative": key, "reason": "Decision references a missing source"})
    for record in records:
        rel = record["source_relative"]
        decision = decisions["files"].get(rel)
        try:
            require(isinstance(decision, dict), "Needs user decision: include/exclude and rationale")
            require(set(decision) <= {"action", "reason", "evidence", "repository", "study", "sample",
                                      "experiment", "run", "layout", "raw_confirmed", "sample_group",
                                      "specimen", "assay", "modality", "modality_evidence", "file_role",
                                      "data_role"}, "Unknown decision field")
            require(isinstance(decision.get("reason"), str) and decision["reason"].strip(), "Missing decision reason")
            if decision.get("action") == "exclude":
                excluded.append({"source_relative": rel, "reason": decision["reason"]})
                continue
            require(decision.get("action") == "include", "Awaiting user decision")
            require(isinstance(decision.get("evidence"), str) and decision["evidence"].strip(), "Missing evidence/user-confirmation record")
            require(decision.get("repository") in REPOSITORIES, "Repository must be explicitly selected")
            row = {**record, **decision}
            row["destination_relative"] = target_path(row, policy)
            rows.append(row)
        except (Blocked, KeyError) as exc:
            unresolved.append({"source_relative": rel, "reason": str(exc)})
    if not records:
        errors.append("No regular files found")
    try:
        validate_rows(rows, policy["mode"], policy)
    except (Blocked, KeyError) as exc:
        errors.append(str(exc))
    if os.path.lexists(policy["destination_root"]):
        errors.append("Destination already exists; select a NEW destination, never merge or overwrite")
    plan = {"version": VERSION, "policy": policy, "inventory": records, "files": rows,
            "excluded": excluded, "unresolved": unresolved, "errors": errors,
            "status": "READY_FOR_APPROVAL" if not unresolved and not errors and rows else "WAITING_FOR_USER",
            "submission_ready": False, "content_validation": "not_yet_run"}
    plan["plan_sha256"] = digest(plan)
    with directory(policy["workspace_root"], create=True) as work:
        os.mkdir(name, 0o700, dir_fd=work)
        report = os.open(name, DIR_FLAGS, dir_fd=work)
        try:
            write_reports(report, plan)
        finally:
            os.close(report)
    event(plan["status"], plan_sha256=plan["plan_sha256"], include=len(rows), exclude=len(excluded),
          unresolved=len(unresolved), errors=len(errors), bytes=sum(r["size"] for r in rows))
    return plan


def report_bytes(plan):
    """The same approved-plan serialization is used for writing and verification."""
    inventory_columns = ["source_relative", "size", "sha256", "kind", "repository_candidate"]
    mapping_columns = ["source_relative", "destination_relative", "repository", "study", "sample", "experiment", "run", "layout", "reason", "evidence"]
    sample_columns = ["study", "sample", "experiment"]
    if plan["policy"].get("layout_version", 1) == 2:
        inventory_columns += ["modality_candidate", "modality_candidate_evidence"]
        mapping_columns = ["source_relative", "destination_relative", "repository", "study", "sample_group", "sample", "specimen",
                           "assay", "experiment", "run", "layout", "modality", "file_role", "data_role", "reason", "evidence", "modality_evidence"]
        sample_columns = ["study", "sample_group", "sample", "specimen", "assay", "experiment", "modality"]
    samples = sorted({tuple(r.get(k, "") for k in sample_columns)
                      for r in plan["files"] if r["repository"] == "KRA"})
    return {
        "plan.json": json_bytes(plan),
        "inventory.tsv": tsv_bytes(plan["inventory"], inventory_columns),
        "file_mapping.tsv": tsv_bytes(plan["files"], mapping_columns),
        "sample_mapping.tsv": tsv_bytes([dict(zip(sample_columns, s)) for s in samples], sample_columns),
        "unresolved.tsv": tsv_bytes(plan["unresolved"] +
            [{"source_relative": "", "reason": e} for e in plan["errors"]], ["source_relative", "reason"]),
        "excluded.tsv": tsv_bytes(plan["excluded"], ["source_relative", "reason"]),
    }


def write_reports(fd, plan, prefix=""):
    for name, data in report_bytes(plan).items():
        write_new(fd, prefix + name, data)


def copy_event(index, row, total):
    return {"event": "COPIED", "index": index, "total": total,
            "destination_relative": row["destination_relative"]}


def completion_record(plan):
    practice = plan["policy"]["mode"] == "practice"
    has_fastq = any(row["repository"] == "KRA" for row in plan["files"])
    return {"plan_sha256": plan["plan_sha256"], "mode": plan["policy"]["mode"],
            "files": len(plan["files"]), "submission_ready": False,
            "validation": "paths_and_empty_sizes_only" if practice else
                          "sha256_and_four_line_fastq" if has_fastq else "sha256_only"}


def inventory_summary(records):
    """Bounded filename candidates, never confirmed classifications or decisions."""
    groups = {}
    for row in records:
        key = (row["kind"], row["repository_candidate"])
        group = groups.setdefault(key, {"kind": key[0], "repository_candidate": key[1],
                                       "files": 0, "zero_byte_files": 0,
                                       "examples": [], "examples_truncated": False})
        group["files"] += 1
        group["zero_byte_files"] += row["size"] == 0
        if len(group["examples"]) < 2:
            path = row["source_relative"]
            group["examples"].append(path[:200])
            group["examples_truncated"] |= len(path) > 200
    empty = sum(row["size"] == 0 for row in records)
    return {"files": len(records), "bytes": sum(row["size"] for row in records),
            "zero_byte_files": empty, "nonzero_byte_files": len(records) - empty,
            "classification_candidates": [groups[key] for key in sorted(groups)]}


def plan_summary(plan):
    return {"status": plan["status"], "plan_sha256": plan["plan_sha256"],
            **{key: plan["policy"][key] for key in ("mode", "source_root", "destination_root", "workspace_root")},
            "inventory_files": len(plan["inventory"]), "included_files": len(plan["files"]),
            "inventory_summary": inventory_summary(plan["inventory"]),
            "excluded_files": len(plan["excluded"]), "unresolved_items": len(plan["unresolved"]),
            "error_count": len(plan["errors"]), "bytes": sum(row["size"] for row in plan["files"]),
            "errors_preview": [error[:512] for error in plan["errors"][:10]],
            "unresolved_preview": [{key: item[key][:512] for key in ("source_relative", "reason")}
                                   for item in plan["unresolved"][:10]],
            "submission_ready": False}


def check_plan(policy, plan):
    validate_layout_policy(policy)
    require(plan.get("plan_sha256") == digest({k: v for k, v in plan.items() if k != "plan_sha256"}), "Plan hash mismatch")
    require(plan["version"] == VERSION and plan["policy"] == policy, "Policy/plan changed; rebuild and reapprove")
    require(plan["status"] == "READY_FOR_APPROVAL" and not plan["unresolved"] and not plan["errors"],
            "Unresolved/blocked plan cannot execute")
    require(plan["files"], "Empty plan cannot execute")
    validate_rows(plan["files"], policy["mode"], policy)
    by_path = {r["source_relative"]: r for r in plan["inventory"]}
    included = {r["source_relative"] for r in plan["files"]}
    excluded = {r["source_relative"] for r in plan["excluded"]}
    require(not (included & excluded) and included | excluded == set(by_path), "Plan does not account for every source exactly once")
    for row in plan["files"]:
        require(all(row[k] == by_path[row["source_relative"]][k] for k in
                    ("size", "mtime_ns", "device", "inode", "sha256")), "Plan file differs from inventory")


def read_plan(policy, path):
    path = absolute(str(path))
    require(path.startswith(policy["workspace_root"] + "/"), "Plan must be inside configured workspace")
    plan = load_json(path)
    check_plan(policy, plan)
    return plan


def fastq_ids(root, row):
    """Validate unwrapped four-line FASTQ/gzip; yield normalized IDs and read markers."""
    rel = row["source_relative"]
    with regular(root, rel) as raw:
        with contextlib.ExitStack() as stack:
            stream = stack.enter_context(gzip.GzipFile(fileobj=raw)) if rel.lower().endswith(".gz") else raw
            count = 0
            while True:
                header = stream.readline(MAX_LINE + 1)
                if not header:
                    break
                seq, plus, quality = (stream.readline(MAX_LINE + 1) for _ in range(3))
                require(max(map(len, (header, seq, plus, quality))) <= MAX_LINE, "FASTQ line exceeds 16 MiB safety limit")
                require(header.startswith(b"@") and plus.startswith(b"+") and quality,
                        "Invalid four-line FASTQ: " + rel)
                seq, quality = seq.rstrip(b"\r\n"), quality.rstrip(b"\r\n")
                require(seq and len(seq) == len(quality), "Sequence/quality length mismatch: " + rel)
                require(all(33 <= b <= 126 for b in quality), "Invalid quality character: " + rel)
                tokens = header[1:].split()
                require(tokens, "Missing read ID: " + rel)
                ident, mate = tokens[0], None
                if ident.endswith((b"/1", b"/2")):
                    mate, ident = ident[-1:].decode(), ident[:-2]
                if len(tokens) > 1 and tokens[1].startswith((b"1:", b"2:")):
                    other = tokens[1][:1].decode()
                    require(mate is None or mate == other, "Contradictory read markers: " + rel)
                    mate = other
                require(ident, "Missing normalized read ID")
                count += 1
                yield ident, mate
            require(count > 0, "Empty FASTQ: " + rel)


def preflight(policy, plan):
    current, errors = inventory(policy)
    require(not errors and current == plan["inventory"], "Inventory/source changed; create a new plan")
    require(not os.path.lexists(policy["destination_root"]), "Destination must not exist")
    if policy["mode"] == "production":
        with directory(policy["source_root"]) as root:
            pairs = validate_rows(plan["files"], "production", policy)
            paired_paths = set()
            for group in pairs.values():
                a, b = group["1"], group["2"]
                for left, right in itertools.zip_longest(fastq_ids(root, a), fastq_ids(root, b)):
                    require(left is not None and right is not None and left[0] == right[0], "Paired FASTQ read IDs/count mismatch")
                    require(left[1] in (None, "1") and right[1] in (None, "2"), "Paired read markers disagree with filename")
                paired_paths.update([a["source_relative"], b["source_relative"]])
            for row in plan["files"]:
                if row["repository"] == "KRA" and row["source_relative"] not in paired_paths:
                    for _ in fastq_ids(root, row):
                        pass
    with directory(str(PurePosixPath(policy["destination_root"]).parent)) as fd:
        space = os.fstatvfs(fd)
        needed = sum(r["size"] for r in plan["files"]) + policy["reserve_bytes"]
        require(space.f_bavail * space.f_frsize >= needed, "Insufficient destination free space")


def verify(policy, plan, require_complete=True):
    expected = {r["destination_relative"] for r in plan["files"]}
    reports = report_bytes(plan)
    with directory(policy["destination_root"]) as dest:
        for row in plan["files"]:
            with regular(dest, row["destination_relative"]) as stream:
                require(os.fstat(stream.fileno()).st_size == row["size"], "Destination size mismatch")
                if policy["mode"] == "production":
                    require(hash_stream(stream) == row["sha256"], "Destination checksum mismatch")
        observed = set()
        def failed(exc):
            raise Blocked("Verification traversal failed: " + str(exc))
        for base, dirs, files, fd in os.fwalk(".", dir_fd=dest, follow_symlinks=False, onerror=failed):
            prefix = "" if base == "." else base[2:] + "/"
            for name in dirs:
                require(not stat.S_ISLNK(os.stat(name, dir_fd=fd, follow_symlinks=False).st_mode), "Symlink in destination")
            for name in files:
                require(stat.S_ISREG(os.stat(name, dir_fd=fd, follow_symlinks=False).st_mode), "Nonregular destination entry")
                observed.add(prefix + name)
        required = expected | {"metadata/" + n for n in reports} | {"metadata/events.jsonl"}
        allowed = required | {"metadata/COMPLETE.json"}
        require(observed <= allowed, "Unexpected files in destination")
        require(required <= observed, "Missing files/reports in destination")
        for name, data in reports.items():
            with regular(dest, "metadata/" + name) as stream:
                require(stream.read(len(data) + 1) == data, "Stored report differs from approved plan: " + name)
        with regular(dest, "metadata/events.jsonl") as stream:
            for index, row in enumerate(plan["files"], 1):
                line = stream.readline(MAX_LINE + 1)
                require(len(line) <= MAX_LINE and line, "Missing/oversized copy event")
                require(digest(json.loads(line)) == digest(copy_event(index, row, len(expected))), "Copy event mismatch")
            require(not stream.read(1), "Unexpected copy events")
        if require_complete:
            with regular(dest, "metadata/COMPLETE.json") as stream:
                require(digest(json.load(stream)) == digest(completion_record(plan)), "Completion marker mismatch")
    event("VERIFIED", files=len(expected), mode=policy["mode"], submission_ready=False)


def apply(policy, plan, approval):
    check_plan(policy, plan)
    require(approval == plan["plan_sha256"], "Exact plan hash approval is required")
    preflight(policy, plan)
    path = PurePosixPath(policy["destination_root"])
    with directory(str(path.parent)) as parent:
        os.mkdir(path.name, 0o700, dir_fd=parent)
    try:
        with directory(policy["source_root"]) as source, directory(str(path)) as dest:
            write_reports(dest, plan, "metadata/")
            with regular(dest, "metadata/events.jsonl", new=True) as log:
                for index, row in enumerate(plan["files"], 1):
                    before = {k: row[k] for k in ("size", "mtime_ns", "device", "inode")}
                    with regular(source, row["source_relative"]) as inp:
                        require(signature(os.fstat(inp.fileno())) == before, "Source changed before copy")
                        h, copied = hashlib.sha256(), 0
                        with regular(dest, row["destination_relative"], new=True) as out:
                            for block in iter(lambda: inp.read(1024 * 1024), b""):
                                out.write(block)
                                h.update(block)
                                copied += len(block)
                            out.flush()
                            os.fsync(out.fileno())
                        require(copied == row["size"], "Copy size mismatch")
                        require(signature(os.fstat(inp.fileno())) == before, "Source changed during copy")
                        if policy["mode"] == "production":
                            require(h.hexdigest() == row["sha256"], "Source checksum changed")
                    entry = copy_event(index, row, len(plan["files"]))
                    log.write((json.dumps(entry) + "\n").encode())
                    log.flush()
                    os.fsync(log.fileno())
                    event("COPIED", index=index, total=len(plan["files"]))
                verify(policy, plan, require_complete=False)
                write_new(dest, "metadata/COMPLETE.json", json_bytes(completion_record(plan)))
        event("COMPLETE", destination=str(path), submission_ready=False)
    except BaseException:
        event("FAILED_PARTIAL_DESTINATION_PRESERVED", destination=str(path))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    policy_group = parser.add_mutually_exclusive_group(required=True)
    policy_group.add_argument("--policy")
    policy_group.add_argument("--policy-data")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("inventory")
    p.add_argument("--summary", action="store_true", help="Print counts and bounded errors without the full file list")
    p = sub.add_parser("plan")
    decision_group = p.add_mutually_exclusive_group()
    decision_group.add_argument("--decisions")
    decision_group.add_argument("--decisions-data")
    p.add_argument("--name", required=True)
    for command in ("apply", "verify"):
        p = sub.add_parser(command)
        p.add_argument("--plan", required=True)
        if command == "apply":
            p.add_argument("--approve-plan", required=True)
    args = parser.parse_args(argv)
    try:
        policy = load_policy(args.policy, args.policy_data)
        if args.command == "inventory":
            records, errors = inventory(policy)
            result = {"files": records, "errors": errors}
            if args.summary:
                result = {"mode": policy["mode"], "source_root": policy["source_root"],
                          **inventory_summary(records),
                          "error_count": len(errors), "errors_preview": [error[:512] for error in errors[:10]]}
            print(json.dumps(result, indent=2))
            return 2 if errors else 0
        if args.command == "plan":
            decisions = (load_json(args.decisions) if args.decisions else
                         decode_json(args.decisions_data, "decisions") if args.decisions_data else
                         {"files": {}})
            plan = make_plan(policy, decisions, args.name)
            print(json.dumps({**plan_summary(plan), "report_directory": policy["workspace_root"] + "/" + args.name}))
            return 0 if plan["status"] == "READY_FOR_APPROVAL" else 2
        plan = read_plan(policy, args.plan)
        if args.command == "apply":
            apply(policy, plan, args.approve_plan)
        else:
            verify(policy, plan)
        print(json.dumps({**plan_summary(plan), "status": "COMPLETE" if args.command == "apply" else "VERIFIED",
                          "package_validation": completion_record(plan)["validation"],
                          "validation": completion_record(plan)["validation"] if args.command == "apply" else
                                        "paths_and_empty_sizes_only" if policy["mode"] == "practice" else "sha256_only",
                          "metadata_verified": True,
                          "fastq_files_checked": sum(row["repository"] == "KRA" for row in plan["files"])
                                                 if args.command == "apply" and policy["mode"] == "production" else 0}))
        return 0
    except (Blocked, OSError, EOFError, KeyError, TypeError, json.JSONDecodeError, zlib.error) as exc:
        event("BLOCKED", reason=str(exc))
        return 2
    except KeyboardInterrupt:
        event("INTERRUPTED", message="No automatic cleanup; inspect any partial destination")
        return 130


if __name__ == "__main__":
    sys.exit(main())
