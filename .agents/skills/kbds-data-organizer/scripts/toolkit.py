#!/usr/bin/env python3
"""KBDS copy-only staging prototype. Linux, Python 3.10+, standard library only."""
from __future__ import annotations

import argparse
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
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
READ_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
FASTQ = re.compile(r"\.(?:fastq|fq)(?:\.gz)?$", re.I)
PAIR = re.compile(r"^(.*?)[_-]R?([12])(_[0-9]+)?(\.(?:fastq|fq)(?:\.gz)?)$", re.I)
REPOSITORIES = {"KRA", "KEA", "KVar", "KNA", "review"}
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
    return (name in {".ssh", ".env", "credentials", "secrets"} or name.startswith((".env.", "id_rsa", "id_ed25519"))
            or name.endswith((".pem", ".key")))


@contextlib.contextmanager
def directory(path, create=False):
    """Walk from / without following symlinks, including ancestor components."""
    absolute(path)
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


def load_policy(path):
    policy = load_json(path)
    require(isinstance(policy, dict) and set(policy) == {
        "version", "mode", "source_root", "destination_root", "workspace_root",
        "allow_practice_zero_bytes", "reserve_bytes"}, "Unknown/missing policy keys")
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
    if any(x in low for x in ("samplesheet", "manifest", "metadata")):
        return "metadata_candidate", "review"
    if re.search(r"count|expression|deg", low) and low.endswith((".tsv", ".csv", ".txt", ".xlsx", ".xls")):
        return "expression_candidate", "KEA"
    return "unknown", "review"


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
    event("INVENTORY", files=len(records), errors=len(errors), mode=policy["mode"])
    return records, errors


def pair_key(path):
    p = PurePosixPath(path)
    match = PAIR.fullmatch(p.name)
    require(match is not None, "Cannot parse mate suffix; no pairing inference allowed: " + path)
    stem, mate, chunk, extension = match.groups()
    return str(p.parent) + "/" + stem + (chunk or "") + extension.lower(), mate


def target_path(row):
    parts(row["source_relative"])
    require(row["repository"] in REPOSITORIES, "Unsupported repository")
    segments = [row["repository"], label(row["study"])]
    if row["repository"] == "KRA":
        segments += [label(row[k]) for k in ("sample", "experiment", "run")]
        segments += [PurePosixPath(row["source_relative"]).name]
    else:
        segments += parts(row["source_relative"])
    return "/".join(segments)


def validate_rows(rows, mode):
    seen, pairs, experiments, sources = set(), {}, {}, set()
    for row in rows:
        require(row["source_relative"] not in sources, "A source is included more than once")
        sources.add(row["source_relative"])
        target = row["destination_relative"]
        require(target == target_path(row), "Destination must follow the approved naming scheme")
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
                                      "experiment", "run", "layout", "raw_confirmed"}, "Unknown decision field")
            require(isinstance(decision.get("reason"), str) and decision["reason"].strip(), "Missing decision reason")
            if decision.get("action") == "exclude":
                excluded.append({"source_relative": rel, "reason": decision["reason"]})
                continue
            require(decision.get("action") == "include", "Awaiting user decision")
            require(isinstance(decision.get("evidence"), str) and decision["evidence"].strip(), "Missing evidence/user-confirmation record")
            require(decision.get("repository") in REPOSITORIES, "Repository must be explicitly selected")
            row = {**record, **decision}
            row["destination_relative"] = target_path(row)
            rows.append(row)
        except (Blocked, KeyError) as exc:
            unresolved.append({"source_relative": rel, "reason": str(exc)})
    if not records:
        errors.append("No regular files found")
    try:
        validate_rows(rows, policy["mode"])
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


def write_reports(fd, plan, prefix=""):
    write_new(fd, prefix + "plan.json", json_bytes(plan))
    write_new(fd, prefix + "inventory.tsv", tsv_bytes(plan["inventory"],
        ["source_relative", "size", "sha256", "kind", "repository_candidate"]))
    write_new(fd, prefix + "file_mapping.tsv", tsv_bytes(plan["files"],
        ["source_relative", "destination_relative", "repository", "study", "sample", "experiment", "run", "layout", "reason", "evidence"]))
    samples = sorted({(r.get("study", ""), r.get("sample", ""), r.get("experiment", ""))
                      for r in plan["files"] if r["repository"] == "KRA"})
    write_new(fd, prefix + "sample_mapping.tsv", tsv_bytes(
        [dict(zip(["study", "sample", "experiment"], s)) for s in samples], ["study", "sample", "experiment"]))
    write_new(fd, prefix + "unresolved.tsv", tsv_bytes(plan["unresolved"] +
        [{"source_relative": "", "reason": e} for e in plan["errors"]], ["source_relative", "reason"]))
    write_new(fd, prefix + "excluded.tsv", tsv_bytes(plan["excluded"], ["source_relative", "reason"]))


def check_plan(policy, plan):
    require(plan.get("plan_sha256") == digest({k: v for k, v in plan.items() if k != "plan_sha256"}), "Plan hash mismatch")
    require(plan["version"] == VERSION and plan["policy"] == policy, "Policy/plan changed; rebuild and reapprove")
    require(plan["status"] == "READY_FOR_APPROVAL" and not plan["unresolved"] and not plan["errors"],
            "Unresolved/blocked plan cannot execute")
    require(plan["files"], "Empty plan cannot execute")
    validate_rows(plan["files"], policy["mode"])
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
            pairs = validate_rows(plan["files"], "production")
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
        report_names = {"plan.json", "inventory.tsv", "file_mapping.tsv", "sample_mapping.tsv", "unresolved.tsv", "excluded.tsv", "events.jsonl"}
        required = expected | {"metadata/" + n for n in report_names}
        allowed = required | {"metadata/COMPLETE.json"}
        require(observed <= allowed, "Unexpected files in destination")
        require(required <= observed, "Missing files/reports in destination")
        with regular(dest, "metadata/plan.json") as stream:
            require(json.load(stream) == plan, "Stored plan differs from approved plan")
        if require_complete:
            with regular(dest, "metadata/COMPLETE.json") as stream:
                require(json.load(stream)["plan_sha256"] == plan["plan_sha256"], "Completion marker mismatch")
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
                    entry = {"event": "COPIED", "index": index, "total": len(plan["files"]),
                             "destination_relative": row["destination_relative"]}
                    log.write((json.dumps(entry) + "\n").encode())
                    log.flush()
                    os.fsync(log.fileno())
                    event("COPIED", index=index, total=len(plan["files"]))
                verify(policy, plan, require_complete=False)
                write_new(dest, "metadata/COMPLETE.json", json_bytes({"plan_sha256": approval,
                    "mode": policy["mode"], "files": len(plan["files"]), "submission_ready": False,
                    "validation": "paths_and_empty_sizes_only" if policy["mode"] == "practice" else "sha256_and_four_line_fastq"}))
        event("COMPLETE", destination=str(path), submission_ready=False)
    except BaseException:
        event("FAILED_PARTIAL_DESTINATION_PRESERVED", destination=str(path))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("inventory")
    p = sub.add_parser("plan")
    p.add_argument("--decisions")
    p.add_argument("--name", required=True)
    for command in ("apply", "verify"):
        p = sub.add_parser(command)
        p.add_argument("--plan", required=True)
        if command == "apply":
            p.add_argument("--approve-plan", required=True)
    args = parser.parse_args(argv)
    try:
        policy = load_policy(args.policy)
        if args.command == "inventory":
            records, errors = inventory(policy)
            print(json.dumps({"files": records, "errors": errors}, indent=2))
            return 2 if errors else 0
        if args.command == "plan":
            decisions = load_json(args.decisions) if args.decisions else {"files": {}}
            plan = make_plan(policy, decisions, args.name)
            print(json.dumps({"status": plan["status"], "plan_sha256": plan["plan_sha256"],
                              "report_directory": policy["workspace_root"] + "/" + args.name}))
            return 0 if plan["status"] == "READY_FOR_APPROVAL" else 2
        plan = read_plan(policy, args.plan)
        if args.command == "apply":
            apply(policy, plan, args.approve_plan)
        else:
            verify(policy, plan)
        return 0
    except (Blocked, OSError, EOFError, KeyError, TypeError, json.JSONDecodeError, zlib.error) as exc:
        event("BLOCKED", reason=str(exc))
        return 2
    except KeyboardInterrupt:
        event("INTERRUPTED", message="No automatic cleanup; inspect any partial destination")
        return 130


if __name__ == "__main__":
    sys.exit(main())
