"""Approved-scope execution preserves the existing copy guards."""
import contextlib
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/kbds-data-organizer/scripts"))
import toolkit as t
import run_scope as scope_runner


def rule():
    return {"pattern": r"batch/(?P<sample>Sample[0-9]+)_R(?P<mate>[12])\.fastq\.gz",
            "decision": {"action": "include", "reason": "Synthetic approved practice",
                "evidence": "Fictional synthetic labels, not biological facts", "repository": "KRA",
                "study": "Study01", "sample_group": "R", "sample": "{sample}",
                "specimen": "{sample}", "assay": "ExampleAssay", "experiment": "{sample}_Library",
                "run": "{sample}_Run", "layout": "PAIRED", "raw_confirmed": True,
                "modality": "bulk", "modality_evidence": "Fictional synthetic modality",
                "file_role": "R{mate}", "data_role": "raw_reads"}}


class PathRuleTests(unittest.TestCase):
    def test_invalid_report_language_stops_before_scope_or_inventory(self):
        with mock.patch.object(scope_runner, "load_scope") as load:
            with self.assertRaisesRegex(t.Blocked, "language"):
                scope_runner.run("/unused/scope.json", "unused", "unused", language="invalid")
            load.assert_not_called()

    def test_numeric_sample_suffix_does_not_become_the_mate(self):
        for stem in ("Sample_1", "Sample_2", "Sample-1"):
            keys = [t.pair_key(f"batch/{stem}_{mate}.fastq.gz") for mate in (1, 2)]
            self.assertEqual(keys, [(f"batch/{stem}.fastq.gz", "1"),
                                    (f"batch/{stem}.fastq.gz", "2")])
        for marker in ("R", ""):
            keys = [t.pair_key(f"batch/Sample_{marker}{mate}_001.fastq.gz") for mate in (1, 2)]
            self.assertEqual(keys, [("batch/Sample_001.fastq.gz", "1"),
                                    ("batch/Sample_001.fastq.gz", "2")])
        self.assertEqual(t.pair_key("batch/Sample_R1_2.fastq.gz"),
                         ("batch/Sample_2.fastq.gz", "1"))
        self.assertIsNone(t.pair_match("SampleRep1.fastq.gz"))

    def test_numbered_replicates_keep_distinct_valid_pairs(self):
        pattern = rule()
        pattern["pattern"] = r"batch/(?P<sample>Sample_[12])_(?P<mate>[12])\.fastq\.gz"
        records = [{"source_relative": f"batch/Sample_{sample}_{mate}.fastq.gz", "size": 0}
                   for sample in (1, 2) for mate in (1, 2)]
        decisions = t.expand_path_rules(records, {"files": {}, "path_rules": [pattern]})["files"]
        policy = {"layout_version": 2, "repository_scope": "KRA", "source_root": "/srv/Example",
                  "destination_root": "/srv/Example_makeup"}
        rows = [{**row, **decisions[row["source_relative"]]} for row in records]
        for row in rows:
            row["destination_relative"] = t.target_path(row, policy)
        self.assertEqual(len(t.validate_rows(rows, "practice", policy)), 2)
        summary = t.inventory_summary([{**row, "kind": "raw_fastq_candidate", "repository_candidate": "KRA"}
                                       for row in records])
        self.assertEqual(summary["path_groups"][0]["name_role_counts"], {"R1": 2, "R2": 2})

    def test_summary_groups_are_bounded_and_unparsed_names_are_not_single_layout(self):
        names = [f"batch{i:02d}/sample_R{mate}.fastq.gz" for i in range(25) for mate in (1, 2)]
        names.append("batch00/accession.fastq.gz")
        records = [{"source_relative": path, "size": 0, "kind": "raw_fastq_candidate",
                    "repository_candidate": "KRA"} for path in names]
        summary = t.inventory_summary(records)
        self.assertEqual(summary["files"], 51)
        self.assertEqual(len(summary["path_groups"]), 20)
        self.assertTrue(summary["path_groups_truncated"])
        first = summary["path_groups"][0]
        self.assertEqual(first["name_role_counts"], {"R1": 1, "R2": 1, "unparsed": 1})
        self.assertEqual(first["examples"]["unparsed"], ["accession.fastq.gz"])

    def test_matches_full_path_and_leaves_unknowns_unresolved(self):
        paths = ["batch/Sample01_R1.fastq.gz", "batch/Sample01_R2.fastq.gz", "other/Sample01_R1.fastq.gz"]
        records = [{"source_relative": p} for p in paths]
        result = t.expand_path_rules(records, {"files": {}, "path_rules": [rule()]})["files"]
        self.assertEqual(set(result), set(paths[:2]))
        self.assertEqual(result[paths[0]]["sample"], "Sample01")
        self.assertEqual(result[paths[1]]["file_role"], "R2")
        self.assertIs(result[paths[0]]["raw_confirmed"], True)

    def test_ambiguous_rules_and_undefined_captures_block(self):
        records = [{"source_relative": "batch/Sample01_R1.fastq.gz"}]
        with self.assertRaisesRegex(t.Blocked, "Ambiguous"):
            t.expand_path_rules(records, {"files": {}, "path_rules": [rule(), rule()]})
        broken = rule()
        broken["decision"]["sample"] = "{missing}"
        with self.assertRaisesRegex(t.Blocked, "capture"):
            t.expand_path_rules(records, {"files": {}, "path_rules": [broken]})

    def test_explicit_exception_overrides_rule(self):
        name = "batch/Sample01_R1.fastq.gz"
        exclude = {"action": "exclude", "reason": "Explicit synthetic exception"}
        result = t.expand_path_rules([{"source_relative": name}],
                                    {"files": {name: exclude}, "path_rules": [rule(), rule()]})
        self.assertEqual(result["files"][name], exclude)

    def test_invalid_regex_and_template_expression_block(self):
        for pattern, sample in [("[", "{sample}"), (rule()["pattern"], "{sample.__class__}")]:
            bad = rule()
            bad["pattern"], bad["decision"]["sample"] = pattern, sample
            with self.subTest(pattern=pattern), self.assertRaises(t.Blocked):
                t.expand_path_rules([{"source_relative": "batch/Sample01_R1.fastq.gz"}],
                                    {"files": {}, "path_rules": [bad]})


@unittest.skipUnless(t.FILESYSTEM_SUPPORTED, "Linux no-follow filesystem integration required")
class ScopeRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "Example"
        (self.source / "batch").mkdir(parents=True)
        self.destination = self.root / "Example_makeup"
        self.scope = {"version": 1, "policy": {"version": 1, "layout_version": 2,
            "repository_scope": "KRA", "mode": "practice", "source_root": str(self.source),
            "destination_root": str(self.destination), "workspace_root": str(self.root / "work"),
            "allow_practice_zero_bytes": True, "reserve_bytes": 0},
            "decisions": {"files": {}, "path_rules": [rule()]}}
        self.scope_path = self.root / "scope.local.json"
        self.save_scope()
        self.add_pair("01")
        self.quiet = contextlib.redirect_stderr(io.StringIO())
        self.quiet.__enter__()
        self.addCleanup(self.quiet.__exit__, None, None, None)

    def save_scope(self):
        self.scope_path.write_text(json.dumps(self.scope))

    def add_pair(self, sample):
        for mate in (1, 2):
            (self.source / "batch" / f"Sample{sample}_R{mate}.fastq.gz").touch()

    def run_job(self, name="auto-001"):
        return scope_runner.run(str(self.scope_path), t.digest(self.scope), name)

    def test_new_matching_files_need_no_new_plan_approval_and_report_is_verified(self):
        approval = t.digest(self.scope)
        self.add_pair("02")
        before = {str(p): t.signature(p.stat()) for p in self.source.rglob("*.gz")}
        result, code = scope_runner.run(str(self.scope_path), approval, "auto-001")
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["report_language"], "ko")
        self.assertEqual(result["included_files"], 4)
        timings = result["timings_seconds"]
        self.assertEqual(set(timings), {"scope_validation", "planning", "scope_recheck", "preflight",
                                      "copy_and_metadata", "verification", "report_verification_and_rendering", "total"})
        self.assertTrue(all(value >= 0 for value in timings.values()))
        self.assertGreaterEqual(timings["total"], sum(value for key, value in timings.items() if key != "total"))
        self.assertIn("excludes model inference", result["timing_scope"])
        self.assertFalse(result["submission_ready"])
        self.assertTrue(Path(result["report_path"]).is_file())
        self.assertIn(approval, Path(result["report_path"]).read_text())
        complete = json.loads((self.destination / "audit/COMPLETE.json").read_text())
        self.assertEqual(complete["files"], 4)
        plan = json.loads(Path(result["plan_path"]).read_text())
        self.assertEqual(plan["approval_scope_sha256"], approval)
        self.assertEqual(before, {str(p): t.signature(p.stat()) for p in self.source.rglob("*.gz")})

    def test_changed_scope_is_blocked_before_inventory(self):
        original = t.digest(self.scope)
        for section, key, value in [("policy", "mode", "production"),
                                    ("policy", "source_root", str(self.root / "other"))]:
            changed = copy.deepcopy(self.scope)
            changed[section][key] = value
            self.scope_path.write_text(json.dumps(changed))
            with self.subTest(key=key), mock.patch.object(t, "inventory") as scan:
                with self.assertRaisesRegex(t.Blocked, "Approved scope changed"):
                    scope_runner.run(str(self.scope_path), original, "blocked")
                scan.assert_not_called()
        changed = copy.deepcopy(self.scope)
        changed["decisions"]["path_rules"][0]["decision"]["sample_group"] = "D"
        self.scope_path.write_text(json.dumps(changed))
        with self.assertRaisesRegex(t.Blocked, "Approved scope changed"):
            scope_runner.run(str(self.scope_path), original, "blocked")
        self.assertFalse(self.destination.exists())

    def test_unknown_file_or_missing_mate_stops_without_copy(self):
        unknown = self.source / "unknown.txt"
        unknown.touch()
        result, code = self.run_job("unknown")
        self.assertEqual(code, 2)
        self.assertEqual(result["unresolved_items"], 1)
        self.assertFalse(result["copied"])
        self.assertFalse(self.destination.exists())
        unknown.unlink()
        (self.source / "batch/Sample01_R2.fastq.gz").unlink()
        result, code = self.run_job("missing-mate")
        self.assertEqual(code, 2)
        self.assertTrue(any("Missing included mate" in e for e in result["errors_preview"]))
        self.assertFalse(self.destination.exists())

    def test_existing_destination_and_nonempty_practice_data_stop(self):
        self.destination.mkdir()
        marker = self.destination / "keep.txt"
        marker.write_text("preserve")
        result, code = self.run_job("existing")
        self.assertEqual(code, 2)
        self.assertEqual(marker.read_text(), "preserve")
        marker.unlink()
        self.destination.rmdir()
        (self.source / "batch/Sample01_R1.fastq.gz").write_bytes(b"nonempty")
        result, code = self.run_job("nonempty")
        self.assertEqual(code, 2)
        self.assertFalse(self.destination.exists())

    def test_source_change_between_plan_and_apply_still_blocks(self):
        original = t.apply
        def changed(policy, plan, approval):
            self.add_pair("02")
            return original(policy, plan, approval)
        with mock.patch.object(t, "apply", side_effect=changed), self.assertRaises(t.Blocked):
            self.run_job()
        self.assertFalse(self.destination.exists())

    def test_cli_inspect_does_not_write_and_run_works(self):
        command = [sys.executable, "-B", str(ROOT / "scripts/kbds.py"), "run", "--scope", str(self.scope_path)]
        inspected = subprocess.run(command + ["--inspect"], capture_output=True, text=True)
        self.assertEqual(inspected.returncode, 0, inspected.stderr)
        self.assertEqual(json.loads(inspected.stdout)["scope_sha256"], t.digest(self.scope))
        self.assertFalse(self.destination.exists())
        executed = subprocess.run(command + ["--approve-scope", t.digest(self.scope), "--name", "cli-run", "--language", "en"],
                                  capture_output=True, text=True)
        self.assertEqual(executed.returncode, 0, executed.stderr)
        result = json.loads(executed.stdout)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["report_language"], "en")
        self.assertIn('<html lang="en">', Path(result["report_path"]).read_text())
        self.assertEqual(json.loads(Path(result["plan_path"]).read_text())["approval_scope_sha256"], t.digest(self.scope))

    def test_report_failure_is_not_success_and_preserves_verified_copy(self):
        with mock.patch.object(scope_runner, "build_verified_report", side_effect=ValueError("report failed")):
            with contextlib.redirect_stdout(io.StringIO()):
                result = scope_runner.main(["--scope", str(self.scope_path), "--approve-scope",
                                            t.digest(self.scope), "--name", "report-failure"])
        self.assertEqual(result, 2)
        self.assertTrue((self.destination / "audit/COMPLETE.json").exists())
        self.assertFalse((self.root / "work/report-failure/report.html").exists())


if __name__ == "__main__":
    unittest.main()
