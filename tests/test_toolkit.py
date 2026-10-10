"""Synthetic data only. No network, live SSH server or research records."""
import argparse
import contextlib
import gzip
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


t = module("toolkit", ROOT / "skills/kbds-data-organizer/scripts/toolkit.py")
remote = module("remote", ROOT / "scripts/remote_stage.py")


@unittest.skipUnless(t.FILESYSTEM_SUPPORTED, "Linux no-follow filesystem integration required")
class ToolkitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.src = self.base / "source"
        self.src.mkdir()
        self.dest = self.base / "staged"
        self.policy = {"version": 1, "mode": "practice", "source_root": str(self.src),
                       "destination_root": str(self.dest), "workspace_root": str(self.base / "work"),
                       "allow_practice_zero_bytes": True, "reserve_bytes": 0}
        self.counter = 0
        self.decisions = {"files": {}}
        for mate in (1, 2):
            name = f"example_R{mate}.fastq.gz"
            (self.src / name).touch()
            self.decisions["files"][name] = {"action": "include", "reason": "Synthetic test approval",
                "evidence": "Synthetic user-confirmed mapping, not research metadata", "repository": "KRA",
                "study": "ExampleStudy", "sample": "Specimen001", "experiment": "ExampleLibrary",
                "run": "LocalRun001", "layout": "PAIRED", "raw_confirmed": True}
        self.silence = contextlib.redirect_stderr(io.StringIO())
        self.silence.__enter__()
        self.addCleanup(self.silence.__exit__, None, None, None)

    def plan(self, decisions=None):
        self.counter += 1
        return t.make_plan(self.policy, self.decisions if decisions is None else decisions, f"plan-{self.counter}")

    def production(self, mismatch=False, markers=False):
        self.policy.update(mode="production", allow_practice_zero_bytes=False)
        for mate in (1, 2):
            ident = "different" if mismatch and mate == 2 else "synthetic_read"
            read = 3 - mate if markers else mate
            content = f"@{ident}/{read}\nACGT\n+\nIIII\n".encode()
            (self.src / f"example_R{mate}.fastq.gz").write_bytes(gzip.compress(content, mtime=0))

    def test_copy_and_verify_preserve_source(self):
        plan = self.plan()
        original = {p.name: (p.stat().st_ino, p.stat().st_mtime_ns) for p in self.src.iterdir()}
        self.assertEqual(plan["status"], "READY_FOR_APPROVAL")
        t.apply(self.policy, plan, plan["plan_sha256"])
        t.verify(self.policy, plan)
        self.assertEqual(original, {p.name: (p.stat().st_ino, p.stat().st_mtime_ns) for p in self.src.iterdir()})
        self.assertEqual(len(list(self.dest.rglob("*.fastq.gz"))), 2)
        self.assertFalse(plan["submission_ready"])

    def test_no_approval_no_destination(self):
        plan = self.plan()
        with self.assertRaises(t.Blocked):
            t.apply(self.policy, plan, "not_approved")
        self.assertFalse(self.dest.exists())

    def test_missing_decisions_stop(self):
        plan = self.plan({"files": {}})
        self.assertEqual(len(plan["unresolved"]), 2)
        self.assertEqual(plan["status"], "WAITING_FOR_USER")
        path = Path(self.policy["workspace_root"]) / "plan-1/plan.json"
        with self.assertRaises(t.Blocked):
            t.read_plan(self.policy, str(path))
        self.assertFalse(self.dest.exists())

    def test_half_pair_stop(self):
        self.decisions["files"]["example_R2.fastq.gz"] = {"action": "exclude", "reason": "Testing mate omission"}
        self.assertTrue(any("Missing included mate" in e for e in self.plan()["errors"]))

    def test_mates_cannot_split_runs(self):
        self.decisions["files"]["example_R2.fastq.gz"]["run"] = "OtherRun"
        self.assertEqual(self.plan()["status"], "WAITING_FOR_USER")

    def test_source_changed_after_plan(self):
        plan = self.plan()
        (self.src / "example_R1.fastq.gz").write_bytes(b"changed")
        with self.assertRaises(t.Blocked):
            t.apply(self.policy, plan, plan["plan_sha256"])
        self.assertFalse(self.dest.exists())

    def test_new_source_file_invalidates_plan(self):
        plan = self.plan()
        (self.src / "later.txt").touch()
        with self.assertRaises(t.Blocked):
            t.apply(self.policy, plan, plan["plan_sha256"])

    def test_existing_destination_not_overwritten(self):
        plan = self.plan()
        self.dest.mkdir()
        marker = self.dest / "keep.txt"
        marker.write_text("keep")
        with self.assertRaises(t.Blocked):
            t.apply(self.policy, plan, plan["plan_sha256"])
        self.assertEqual(marker.read_text(), "keep")

    def test_symlink_file_inventory_incomplete(self):
        outside = self.base / "outside"
        outside.write_text("private-value")
        (self.src / "link.fastq.gz").symlink_to(outside)
        plan = self.plan()
        self.assertTrue(plan["errors"])
        self.assertNotIn("private-value", json.dumps(plan))

    def test_symlink_directory_blocked(self):
        (self.src / "external").symlink_to(self.base, target_is_directory=True)
        self.assertEqual(self.plan()["status"], "WAITING_FOR_USER")

    def test_symlink_root_ancestor_blocked(self):
        link = self.base / "alias"
        link.symlink_to(self.src, target_is_directory=True)
        with self.assertRaises(OSError):
            with t.directory(str(link)):
                pass

    def test_traversal_label_blocked(self):
        self.decisions["files"]["example_R1.fastq.gz"]["sample"] = "../../escape"
        self.assertTrue(self.plan()["unresolved"])

    def test_read_relative_traversal_blocked(self):
        with t.directory(str(self.src)) as fd:
            with self.assertRaises(t.Blocked):
                with t.regular(fd, "../outside"):
                    pass

    def test_report_never_overwritten(self):
        self.plan()
        with self.assertRaises(FileExistsError):
            t.make_plan(self.policy, self.decisions, "plan-1")

    def test_tampered_plan_rejected(self):
        self.plan()
        path = Path(self.policy["workspace_root"]) / "plan-1/plan.json"
        data = json.loads(path.read_text())
        data["files"][0]["sample"] = "WrongSample"
        path.write_text(json.dumps(data))
        with self.assertRaises(t.Blocked):
            t.read_plan(self.policy, str(path))

    def test_policy_overlap_rejected(self):
        self.policy["destination_root"] = str(self.src / "output")
        path = self.base / "policy.json"
        path.write_text(json.dumps(self.policy))
        with self.assertRaises(t.Blocked):
            t.load_policy(str(path))

    def test_unknown_policy_key_rejected(self):
        self.policy["allow_delete"] = True
        path = self.base / "policy.json"
        path.write_text(json.dumps(self.policy))
        with self.assertRaises(t.Blocked):
            t.load_policy(str(path))

    def test_practice_does_not_accept_real_data(self):
        (self.src / "example_R1.fastq.gz").write_bytes(b"not empty")
        self.assertEqual(self.plan()["status"], "WAITING_FOR_USER")

    def test_production_rejects_empty_placeholders(self):
        self.policy.update(mode="production", allow_practice_zero_bytes=False)
        self.assertEqual(self.plan()["status"], "WAITING_FOR_USER")

    def test_production_gzip_fastq_success(self):
        self.production()
        plan = self.plan()
        t.apply(self.policy, plan, plan["plan_sha256"])
        t.verify(self.policy, plan)
        for row in plan["files"]:
            self.assertEqual((self.src / row["source_relative"]).read_bytes(),
                             (self.dest / row["destination_relative"]).read_bytes())

    def test_production_pair_id_mismatch(self):
        self.production(mismatch=True)
        plan = self.plan()
        with self.assertRaises(t.Blocked):
            t.apply(self.policy, plan, plan["plan_sha256"])
        self.assertFalse(self.dest.exists())

    def test_invalid_gzip_blocked_before_copy(self):
        self.production()
        (self.src / "example_R1.fastq.gz").write_bytes(b"not a gzip")
        plan = self.plan()
        with self.assertRaises(OSError):
            t.apply(self.policy, plan, plan["plan_sha256"])
        self.assertFalse(self.dest.exists())

    def test_tampered_output_detected(self):
        self.production()
        plan = self.plan()
        t.apply(self.policy, plan, plan["plan_sha256"])
        target = self.dest / plan["files"][0]["destination_relative"]
        data = bytearray(target.read_bytes())
        data[-1] ^= 1
        target.write_bytes(data)
        with self.assertRaises(t.Blocked):
            t.verify(self.policy, plan)

    def test_unknown_additional_output_detected(self):
        plan = self.plan()
        t.apply(self.policy, plan, plan["plan_sha256"])
        (self.dest / "unexpected.txt").touch()
        with self.assertRaises(t.Blocked):
            t.verify(self.policy, plan)

    def test_repeated_execution_refuses_merge(self):
        plan = self.plan()
        t.apply(self.policy, plan, plan["plan_sha256"])
        with self.assertRaises(t.Blocked):
            t.apply(self.policy, plan, plan["plan_sha256"])

    def test_filename_is_only_candidate(self):
        self.assertEqual(t.classify("RNA_trimmed/example_R1.trim.fastq.gz")[1], "review")
        self.assertEqual(t.classify("analysis.vcf.gz")[1], "KVar")
        self.assertEqual(t.classify("sample.fastq.gz")[0], "raw_fastq_candidate")

    def test_empty_hash_does_not_deduplicate(self):
        plan = self.plan()
        self.assertEqual(len(plan["files"]), 2)
        self.assertTrue(all(r["sha256"] is None for r in plan["files"]))

    def test_ssh_wrapper_no_insecure_host_key_option(self):
        args = argparse.Namespace(host="lab-test", remote_tool="/srv/toolkit/scripts/kbds.py",
                                  policy="/srv/config/policy.json", plan=None, decisions=None,
                                  action="inventory", name=None, approve_plan=None, user=None,
                                  port=None, ssh=None, local_tool=None)
        cmd = remote.build_command(args)
        self.assertIn("StrictHostKeyChecking=yes", cmd)
        self.assertIn("ForwardAgent=no", cmd)
        args.host = "-oProxyCommand=bad"
        with self.assertRaises(ValueError):
            remote.build_command(args)

    def test_local_tool_is_streamed_without_remote_install(self):
        tool = self.base / "tool.py"
        tool.write_text("print('safe')\n")
        policy = self.base / "policy.json"
        policy.write_text(json.dumps(self.policy))
        args = argparse.Namespace(remote_tool=None, local_tool=str(tool),
                                  policy=None, local_policy=str(policy), plan=None, decisions=None,
                                  local_decisions=None, action="inventory", name=None,
                                  approve_plan=None)
        command = remote.remote_command(args)
        self.assertIn("python3 -I -c", command)
        self.assertIn("<kbds-data-organizer>", command)
        self.assertIn("--policy-data", command)
        self.assertNotIn(str(tool), command)
        self.assertNotIn(str(policy), command)
        self.assertNotIn("/srv/toolkit", command)
        encoded = remote.encoded_local_json(policy, "policy")
        self.assertEqual(t.decode_json(encoded, "policy"), self.policy)

    def test_generic_remote_shell_action_is_absent(self):
        with self.assertRaises(SystemExit):
            remote.main(["bridge-exec"])

    def test_password_bridge_is_user_owned_and_disables_forwarding(self):
        cmd = remote.session_command("git-ssh", "192.0.2.1", "research", 708)
        self.assertEqual(cmd[-2:], ["192.0.2.1", "sh"])
        self.assertIn("-T", cmd)
        self.assertNotIn("-M", cmd)
        self.assertIn("StrictHostKeyChecking=ask", cmd)
        self.assertIn("ForwardAgent=no", cmd)
        self.assertIn("ClearAllForwardings=yes", cmd)

    def test_password_bridge_queue_runs_through_its_own_mux(self):
        requests = self.base / "requests"
        responses = self.base / "responses"
        requests.mkdir()
        responses.mkdir()
        token = "a" * 64
        request = requests / ("1" * 32 + ".request.json")
        request.write_text(json.dumps({"token": token, "operation": "run",
                                       "command": "printf safe"}))
        marker = "__KBDS_" + token + "_" + "1" * 32
        session = argparse.Namespace(poll=lambda: None, stdin=io.BytesIO(),
                                     stdout=io.BytesIO((marker + "_BEGIN__\nsafe\n" +
                                                        marker + "_END__:0\n").encode()))
        closing, response = remote.handle_request(request, responses, token, session)
        self.assertFalse(closing)
        self.assertEqual(json.loads(response.read_text())["stdout"], "safe")
        self.assertIn(b"printf safe", session.stdin.getvalue())

    def test_password_bridge_preserves_exact_stdout_in_a_real_shell(self):
        session = subprocess.Popen(["sh"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0)
        timeout = threading.Timer(5, session.kill)
        timeout.start()
        try:
            for index, (command, expected) in enumerate(
                    [("printf safe", "safe"), ("printf 'safe\\n'", "safe\n"), ("true", "")]):
                self.assertEqual(remote.run_session_command(session, command, "a" * 64, f"{index:032x}"),
                                 (0, expected))
        finally:
            timeout.cancel()
            session.terminate()
            session.communicate(timeout=5)

    def test_sensitive_directory_is_not_scanned(self):
        (self.src / ".ssh").mkdir()
        (self.src / ".ssh/id_rsa").write_text("private-value")
        plan = self.plan()
        self.assertTrue(plan["errors"])
        self.assertEqual(len(plan["inventory"]), 2)

    def test_sensitive_file_is_not_opened(self):
        (self.src / ".env").write_text("PASSWORD=private-value")
        plan = self.plan()
        self.assertTrue(plan["errors"])
        self.assertNotIn("private-value", json.dumps(plan))

    def test_read_markers_must_match_filenames(self):
        self.production(markers=True)
        plan = self.plan()
        with self.assertRaises(t.Blocked):
            t.apply(self.policy, plan, plan["plan_sha256"])
        self.assertFalse(self.dest.exists())

    def test_nonregular_fifo_blocked(self):
        os.mkfifo(self.src / "pipe.fastq.gz")
        self.assertTrue(self.plan()["errors"])

    def test_casefold_destination_collision(self):
        for name in ("A.txt", "a.txt"):
            (self.src / name).touch()
            self.decisions["files"][name] = {"action": "include", "reason": "synthetic", "evidence": "synthetic",
                                             "repository": "review", "study": "ExampleStudy"}
        self.assertTrue(any("collision" in e for e in self.plan()["errors"]))

    def test_excluded_files_are_preserved(self):
        (self.src / "ignore.txt").write_text("Keep source")
        self.decisions["files"]["ignore.txt"] = {"action": "exclude", "reason": "Synthetic exclusion"}
        plan = self.plan()
        t.apply(self.policy, plan, plan["plan_sha256"])
        self.assertEqual((self.src / "ignore.txt").read_text(), "Keep source")
        self.assertFalse(list(self.dest.rglob("ignore.txt")))

    def test_metadata_reports_delivered(self):
        plan = self.plan()
        t.apply(self.policy, plan, plan["plan_sha256"])
        for name in ("inventory.tsv", "file_mapping.tsv", "sample_mapping.tsv", "unresolved.tsv", "excluded.tsv"):
            self.assertTrue((self.dest / "metadata" / name).is_file())

    def test_cli_waiting_exit_status(self):
        policy = self.base / "policy.json"
        policy.write_text(json.dumps(self.policy))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(t.main(["--policy", str(policy), "plan", "--name", "cli-draft"]), 2)
        self.assertFalse(self.dest.exists())

    def test_plan_cannot_redirect_output(self):
        plan = self.plan()
        plan["files"][0]["destination_relative"] = "../../outside.fastq.gz"
        plan["plan_sha256"] = t.digest({k: v for k, v in plan.items() if k != "plan_sha256"})
        with self.assertRaises(t.Blocked):
            t.apply(self.policy, plan, plan["plan_sha256"])
        self.assertFalse(self.dest.exists())

    def test_missing_raw_confirmation_stops(self):
        self.decisions["files"]["example_R1.fastq.gz"].pop("raw_confirmed")
        self.assertEqual(self.plan()["status"], "WAITING_FOR_USER")

    def test_report_contents_must_match_approved_plan(self):
        plan = self.plan()
        t.apply(self.policy, plan, plan["plan_sha256"])
        for name in t.report_bytes(plan):
            with self.subTest(report=name):
                path = self.dest / "metadata" / name
                original = path.read_bytes()
                path.write_bytes(b"corrupted synthetic report\n")
                with self.assertRaises(t.Blocked):
                    t.verify(self.policy, plan)
                path.write_bytes(original)

    def test_all_completion_fields_are_validated(self):
        plan = self.plan()
        t.apply(self.policy, plan, plan["plan_sha256"])
        path = self.dest / "metadata/COMPLETE.json"
        original = json.loads(path.read_text())
        for key, value in {"mode": "production", "files": 999, "submission_ready": True,
                           "validation": "invented", "plan_sha256": "0" * 64}.items():
            with self.subTest(field=key):
                path.write_text(json.dumps({**original, key: value}))
                with self.assertRaises(t.Blocked):
                    t.verify(self.policy, plan)
        path.write_text(json.dumps(original))
        t.verify(self.policy, plan)

    def test_copy_event_sequence_is_validated(self):
        plan = self.plan()
        t.apply(self.policy, plan, plan["plan_sha256"])
        path = self.dest / "metadata/events.jsonl"
        original = path.read_bytes()
        first = json.loads(original.splitlines()[0])
        for data in (json.dumps({**first, "index": True}).encode() + b"\n" + original.splitlines(keepends=True)[1],
                     original.splitlines(keepends=True)[0], original + b"{}\n"):
            with self.subTest(data=data):
                path.write_bytes(data)
                with self.assertRaises(t.Blocked):
                    t.verify(self.policy, plan)
        path.write_bytes(original)
        t.verify(self.policy, plan)

    def test_non_kra_production_reports_checksum_only(self):
        self.policy.update(mode="production", allow_practice_zero_bytes=False)
        self.decisions = {"files": {name: {"action": "exclude", "reason": "Synthetic exclusion"}
                                    for name in self.decisions["files"]}}
        (self.src / "notes.txt").write_text("Synthetic non-FASTQ data")
        self.decisions["files"]["notes.txt"] = {"action": "include", "reason": "Synthetic inclusion",
            "evidence": "Synthetic user confirmation", "repository": "review", "study": "ExampleStudy"}
        plan = self.plan()
        t.apply(self.policy, plan, plan["plan_sha256"])
        t.verify(self.policy, plan)
        marker = json.loads((self.dest / "metadata/COMPLETE.json").read_text())
        self.assertEqual(marker["validation"], "sha256_only")

    def test_sensitive_roots_and_direct_files_block_before_open(self):
        secret_root = self.src / ".aws"
        secret_root.mkdir()
        (secret_root / "config").write_text("SYNTHETIC_SENTINEL_ONLY")
        with mock.patch.object(t.os, "open", side_effect=AssertionError("Sensitive directory opened")):
            with self.assertRaises(t.Blocked), t.directory(str(secret_root)):
                pass
            with self.assertRaises(t.Blocked):
                t.inventory({**self.policy, "source_root": str(secret_root)})
        (self.src / ".env").write_text("SYNTHETIC_SENTINEL_ONLY")
        with t.directory(str(self.src)) as fd:
            with mock.patch.object(t.os, "open", side_effect=AssertionError("Sensitive file opened")):
                with self.assertRaises(t.Blocked), t.regular(fd, ".env"):
                    pass

    def test_aws_directory_is_blocked_before_opening(self):
        self.policy.update(mode="production", allow_practice_zero_bytes=False)
        (self.src / ".aws").mkdir()
        (self.src / ".aws/config").write_text("SYNTHETIC_SENTINEL_ONLY")
        original = t.regular

        def guarded(fd, relative, **kwargs):
            self.assertNotIn(".aws", relative.split("/"))
            return original(fd, relative, **kwargs)

        with mock.patch.object(t, "regular", side_effect=guarded):
            records, errors = t.inventory(self.policy)
        self.assertEqual(len(records), 2)
        self.assertTrue(any(".aws" in error for error in errors))

    def test_cli_inventory_and_plan_summaries(self):
        policy = self.base / "policy.json"
        policy.write_text(json.dumps(self.policy))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(t.main(["--policy", str(policy), "inventory", "--summary"]), 0)
        summary = json.loads(out.getvalue())
        self.assertEqual((summary["files"], summary["bytes"], summary["error_count"]), (2, 0, 0))
        self.assertFalse(self.dest.exists())
        self.assertFalse(Path(self.policy["workspace_root"]).exists())
        decisions = self.base / "decisions.json"
        decisions.write_text(json.dumps(self.decisions))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(t.main(["--policy", str(policy), "plan", "--name", "summary",
                                    "--decisions", str(decisions)]), 0)
        summary = json.loads(out.getvalue())
        self.assertEqual(summary["included_files"], 2)
        self.assertEqual(summary["excluded_files"], 0)
        self.assertEqual(summary["unresolved_items"], 0)
        self.assertFalse(self.dest.exists())

    def test_cli_verify_does_not_claim_to_repeat_fastq_checks(self):
        self.production()
        policy = self.base / "policy.json"
        policy.write_text(json.dumps(self.policy))
        plan = self.plan()
        t.apply(self.policy, plan, plan["plan_sha256"])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(t.main(["--policy", str(policy), "verify", "--plan",
                                    str(Path(self.policy["workspace_root"]) / "plan-1/plan.json")]), 0)
        summary = json.loads(out.getvalue())
        self.assertEqual(summary["package_validation"], "sha256_and_four_line_fastq")
        self.assertEqual(summary["validation"], "sha256_only")
        self.assertEqual(summary["fastq_files_checked"], 0)
        self.assertTrue(summary["metadata_verified"])


if __name__ == "__main__":
    unittest.main()
