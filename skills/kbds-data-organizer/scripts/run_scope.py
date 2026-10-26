#!/usr/bin/env python3
"""Execute one job under a previously approved policy and classification decisions."""
import argparse
import base64
import json
from pathlib import PurePosixPath
import time
import zlib

import toolkit as t
from build_html_report import build_verified_report


def load_scope(path, approval=None):
    scope = t.load_json(path)
    t.require(isinstance(scope, dict) and set(scope) == {"version", "policy", "decisions"},
              "Scope must contain exactly version, policy and decisions")
    t.require(scope["version"] == 1 and isinstance(scope["decisions"], dict), "Invalid scope schema")
    fingerprint = t.digest(scope)
    if approval is not None:
        t.require(approval == fingerprint, "Approved scope changed; stop for scope review")
    policy = t.load_policy(data=base64.b64encode(t.json_bytes(scope["policy"])).decode())
    t.require(policy.get("layout_version") == 2, "Scoped runs require layout_version 2")
    # Keep the grant out of data trees so it cannot be copied as input or created as output.
    scope_path = t.absolute(path)
    for key in ("source_root", "destination_root"):
        root = policy[key]
        t.require(scope_path != root and not scope_path.startswith(root + "/"),
                  "Store scope outside source and destination")
    return scope, policy, fingerprint


def run(path, approval, name, language="ko"):
    t.require(language in ("ko", "en"), "Report language must be ko or en")
    started = time.perf_counter()
    scope, policy, fingerprint = load_scope(path, approval)
    scope_finished = time.perf_counter()
    plan = t.make_plan(policy, scope["decisions"], name, scope_sha256=fingerprint)
    plan_finished = time.perf_counter()
    timings = {"scope_validation": scope_finished - started, "planning": plan_finished - scope_finished}
    plan_path = str(PurePosixPath(policy["workspace_root"]) / name / "plan.json")
    result = {**t.plan_summary(plan), "approval_scope_sha256": fingerprint, "plan_path": plan_path}
    if plan["status"] != "READY_FOR_APPROVAL":
        return {**result, "status": "WAITING_FOR_USER", "copied": False,
                "timings_seconds": {**timings, "total": time.perf_counter() - started}}, 2
    load_scope(path, approval)
    approval_finished = time.perf_counter()
    timings["scope_recheck"] = approval_finished - plan_finished
    # The human approved this scope, not the newly generated plan hash.
    # apply still performs all plan, inventory, pairing and exclusive-output checks.
    applied = t.apply(policy, plan, plan["plan_sha256"])
    timings.update({key: value for key, value in applied.items() if key != "total"})
    execution_finished = time.perf_counter()
    report = build_verified_report(plan_path, language)
    finished = time.perf_counter()
    timings.update(report_verification_and_rendering=finished - execution_finished, total=finished - started)
    return {**result, "status": "COMPLETE", "copied": True, "report_path": str(report),
            "report_language": language,
            "timings_seconds": timings,
            "timing_scope": "Tool process only; excludes model inference and permission waiting",
            "metadata_verified": True, "validation": t.completion_record(plan)["validation"]}, 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true", help="Show scope hash; does not grant approval")
    mode.add_argument("--approve-scope", help="Previously approved canonical scope SHA-256")
    parser.add_argument("--name", help="New private plan directory name")
    parser.add_argument("--language", choices=("ko", "en"), default="ko", help="HTML report language; default ko")
    args = parser.parse_args(argv)
    if not args.inspect and not args.name:
        parser.error("--name is required for execution")
    try:
        if args.inspect:
            scope, policy, fingerprint = load_scope(args.scope)
            result, code = {"scope_sha256": fingerprint, "policy": policy,
                            "decisions": scope["decisions"], "approved": False}, 0
        else:
            result, code = run(args.scope, args.approve_scope, args.name, args.language)
        print(json.dumps(result, ensure_ascii=True))
        return code
    except (ValueError, OSError, EOFError, KeyError, TypeError, zlib.error) as exc:
        t.event("BLOCKED", reason=str(exc))
        return 2
    except KeyboardInterrupt:
        t.event("INTERRUPTED", message="Preserve partial output; no automatic retry")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
