"""Portable layout decisions plus Linux-only copy verification, using synthetic data."""
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


t = module("layout_toolkit", ROOT / "skills/kbds-data-organizer/scripts/toolkit.py")
remote = module("layout_remote", ROOT / "scripts/remote_stage.py")
fallback = module("layout_fallback", ROOT / "skills/kbds-data-organizer/scripts/inventory_tsv.py")
html_report = module("layout_html_report", ROOT / "skills/kbds-data-organizer/scripts/build_html_report.py")


def policy(scope="KRA", mixed=False):
    return {"version": 1, "layout_version": 2, "repository_scope": scope, "mode": "practice",
            "source_root": "/srv/Example", "destination_root": "/srv/Example" +
            ("_" + scope if mixed else "") + "_makeup", "workspace_root": "/srv/work",
            "allow_practice_zero_bytes": True, "reserve_bytes": 0}


def pair(token="B", group=None, modality="bulk"):
    group = group or token
    return [{"source_relative": f"batch/ID001-{token}_{mate}.fastq.gz", "size": 0,
             "action": "include", "reason": "Synthetic copy", "evidence": "Synthetic specimen/library record",
             "repository": "KRA", "study": "Study01", "sample_group": group, "sample": "ID001",
             "specimen": "Specimen_" + token, "assay": "RNA_seq" if token == "R" else "WES",
             "experiment": "Library_" + token, "run": "Run_" + token, "modality": modality,
             "modality_evidence": "Synthetic protocol", "data_role": "raw_reads",
             "layout": "PAIRED", "raw_confirmed": True, "file_role": f"R{mate}"}
            for mate in (1, 2)]


def mapped(rows, p):
    result = copy.deepcopy(rows)
    for row in result:
        row["destination_relative"] = t.target_path(row, p)
    return result


class LayoutTests(unittest.TestCase):
    def test_blood_dna_rna_are_separate_sample_groups(self):
        p = policy()
        rows = mapped(pair() + pair("D") + pair("R"), p)
        self.assertEqual(len(t.validate_rows(rows, "practice", p)), 3)
        self.assertEqual(rows[0]["destination_relative"],
                         "Example_makeup_bulk/Study01/B/ID001/Library_B/Run_B/R1/ID001-B_1.fastq.gz")
        self.assertIn("/D/ID001/Library_D/Run_D/R2/", rows[3]["destination_relative"])
        self.assertIn("/R/ID001/", rows[4]["destination_relative"])
        self.assertEqual(len({r["specimen"] for r in rows}), 3)
        self.assertEqual(len({r["sample_group"] for r in rows}), 3)

    def test_missing_decisions_never_default(self):
        for key in ("sample_group", "sample", "specimen", "assay", "modality", "modality_evidence", "file_role", "data_role"):
            with self.subTest(key=key):
                row = pair()[0]
                row.pop(key)
                with self.assertRaises(t.Blocked):
                    t.target_path(row, policy())

    def test_role_must_match_mate_and_group(self):
        for changes in ({"file_role": "R2"}, {"sample_group": "Whole_Genome"},
                        {"file_role": "B_R1"}, {"file_role": "../R1"}):
            with self.subTest(changes=changes), self.assertRaises(t.Blocked):
                t.target_path({**pair()[0], **changes}, policy())

    def test_mates_cannot_have_different_roles_or_modalities(self):
        for changes in ({"file_role": "single"}, {"modality": "single_cell"}, {"specimen": "other"}):
            with self.subTest(changes=changes):
                rows = pair()
                rows[1].update(changes)
                with self.assertRaises(t.Blocked):
                    t.validate_rows(mapped(rows, policy()), "practice", policy())

    def test_mixed_repository_roots_and_modality(self):
        p = policy("KRA", mixed=True)
        rows = mapped(pair("R", "R", "single_cell"), p)
        self.assertTrue(rows[0]["destination_relative"].startswith("Example_KRA_makeup_single_cell/"))
        t.validate_rows(rows, "practice", p)
        with self.assertRaises(t.Blocked):
            t.target_path(rows[0], policy("KEA", mixed=True))

    def test_matrix_companions_keep_relative_structure(self):
        p = policy("GEO", mixed=True)
        rows = [{"source_relative": "cell01/filtered/" + name,
                 "size": 0, "reason": "Synthetic", "evidence": "Synthetic", "repository": "GEO",
                 "study": "Study01", "modality": "single_cell", "modality_evidence": "Synthetic protocol",
                 "data_role": role} for name, role in
                [("matrix.mtx.gz", "expression_matrix"), ("barcodes.tsv.gz", "matrix_barcodes"),
                 ("features.tsv.gz", "matrix_features")]]
        rows = mapped(rows, p)
        t.validate_rows(rows, "practice", p)
        self.assertEqual({str(Path(r["destination_relative"]).parent).replace(os.sep, "/") for r in rows},
                         {"Example_GEO_makeup_single_cell/Study01/cell01/filtered"})

    def test_bam_is_not_automatically_kea(self):
        self.assertEqual(t.classify("WES/a.bam"), ("alignment_requires_review", "review"))
        row = {**pair()[0], "source_relative": "RNA/aligned.bam", "repository": "KEA",
               "data_role": "alignment"}
        p = policy("KEA", mixed=True)
        with self.assertRaises(t.Blocked):
            t.target_path(row, p)
        row["data_role"] = "processed_functional_genomics"
        self.assertEqual(t.target_path(row, p), "Example_KEA_makeup_bulk/Study01/RNA/aligned.bam")

    def test_trio_detection_does_not_label_unlinked_fastq(self):
        paths = ["cell/" + n for n in ("matrix.mtx.gz", "barcodes.tsv.gz", "features.tsv.gz", "sample_R1.fastq.gz")]
        paths += ["other/matrix.mtx", "incomplete/barcodes.tsv", "incomplete/features.tsv"]
        rows = [{"source_relative": p} for p in paths]
        t.annotate_matrix_candidates(rows)
        self.assertTrue(all(r.get("modality_candidate") == "single_cell" for r in rows[:3]))
        self.assertTrue(all("modality_candidate" not in r for r in rows[3:]))
        for name in ("matrix.mtx.gz", "barcodes.tsv.gz", "features.tsv.gz", "gene_counts.tsv.gz"):
            self.assertEqual(t.classify(name)[1], "GEO")

    def test_tsv_fallback_agrees_with_archive_candidates(self):
        for path in ("reads/sample_R1.fastq.gz", "filtered/a.fastq.gz", "WES/a.bam", "genes.tsv",
                     "matrix.mtx.gz", "barcodes.tsv.gz", "gene_counts.tsv.gz", "a.vcf", "a.fa", "unknown.txt"):
            with self.subTest(path=path):
                self.assertEqual(fallback.candidate(path), t.classify(path))

    def test_candidate_evidence_cannot_replace_confirmed_evidence(self):
        rows = [{"source_relative": n} for n in ("matrix.mtx", "barcodes.tsv", "features.tsv")]
        t.annotate_matrix_candidates(rows)
        row = {**rows[0], "repository": "GEO", "study": "Study01", "modality": "single_cell",
               "data_role": "expression_matrix", "reason": "Synthetic", "evidence": "Synthetic"}
        with self.assertRaises(t.Blocked):
            t.target_path(row, policy("GEO"))

    def test_different_specimens_cannot_merge_experiment(self):
        rows = pair() + pair("D")
        for row in rows:
            row["experiment"] = "MergedLibrary"
        with self.assertRaises(t.Blocked):
            t.validate_rows(mapped(rows, policy()), "practice", policy())

    def test_different_pairs_cannot_merge_run(self):
        rows = pair() + pair()
        for row in rows[2:]:
            row["source_relative"] = row["source_relative"].replace("batch/ID001", "batch2/ID002")
        with self.assertRaises(t.Blocked):
            t.validate_rows(mapped(rows, policy()), "practice", policy())

    def test_collision_and_path_escape_remain_blocked(self):
        rows = pair() + pair()
        for row in rows[2:]:
            row["source_relative"] = row["source_relative"].replace("batch/", "batch2/")
        with self.assertRaises(t.Blocked):
            t.validate_rows(mapped(rows, policy()), "practice", policy())
        with self.assertRaises(t.Blocked):
            t.target_path({**pair()[0], "sample": "../../escape"}, policy())
        with self.assertRaises(t.Blocked):
            t.validate_layout_policy({**policy(), "destination_root": "/other/Example_makeup"})

    def test_legacy_layout_still_validates(self):
        rows = pair()
        legacy = {k: v for k, v in policy().items() if k not in ("layout_version", "repository_scope")}
        rows = mapped(rows, legacy)
        self.assertTrue(rows[0]["destination_relative"].startswith("KRA/Study01/ID001/"))
        t.validate_rows(rows, "practice", legacy)

    def test_streamed_new_policy_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            path.write_text(json.dumps(policy()), encoding="utf-8")
            self.assertEqual(t.decode_json(remote.encoded_local_json(path, "policy"), "policy"), policy())
            args = argparse.Namespace(local_tool=str(ROOT / "skills/kbds-data-organizer/scripts/toolkit.py"),
                                      remote_tool=None, local_policy=str(path), policy=None, plan=None,
                                      decisions=None, action="inventory")
            command = remote.remote_command(args)
            self.assertLess(len(command), remote.MAX_REMOTE_COMMAND)
            self.assertIn("--policy-data", command)

    def test_example_decisions_match_example_policy(self):
        p = json.loads((ROOT / "config/policy.example.json").read_text())
        d = json.loads((ROOT / "config/decisions.example.json").read_text())
        rows = [{"source_relative": rel, "size": 0, **row} for rel, row in d["files"].items()
                if row["action"] == "include"]
        t.validate_rows(mapped(rows, p), "practice", p)

    @unittest.skipIf(t.FILESYSTEM_SUPPORTED, "Windows-specific guard")
    def test_windows_cannot_execute_filesystem_operations(self):
        with self.assertRaises(t.Blocked), t.directory("/srv/Example", create=True):
            pass

    @unittest.skipUnless(t.FILESYSTEM_SUPPORTED, "Linux filesystem integration required")
    def test_layout2_real_copy_and_unknown_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            p = {**policy(), "source_root": str(base / "Example"),
                 "destination_root": str(base / "Example_makeup"), "workspace_root": str(base / "work")}
            rows = pair() + pair("D") + pair("R", "R", "single_cell")
            decisions = {"files": {}}
            for row in rows:
                path = Path(p["source_root"]) / row["source_relative"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch()
                decisions["files"][row["source_relative"]] = {k: v for k, v in row.items()
                                                               if k not in ("source_relative", "size")}
            bad = copy.deepcopy(decisions)
            next(iter(bad["files"].values())).pop("modality")
            self.assertEqual(t.make_plan(p, bad, "unresolved")["status"], "WAITING_FOR_USER")
            plan = t.make_plan(p, decisions, "ready")
            self.assertEqual(plan["status"], "READY_FOR_APPROVAL")
            with self.assertRaises(FileNotFoundError):
                html_report.build_verified_report(base / "work" / "ready" / "plan.json")
            self.assertFalse((base / "work" / "ready" / "report.html").exists())
            t.apply(p, plan, plan["plan_sha256"])
            t.verify(p, plan)
            report = html_report.build_verified_report(base / "work" / "ready" / "plan.json")
            self.assertTrue(report.is_file())
            self.assertIn("data:image/svg+xml;base64,", report.read_text(encoding="utf-8"))
            self.assertEqual(len(list(Path(p["destination_root"]).rglob("*.fastq.gz"))), 6)
            self.assertEqual(len(list(Path(p["source_root"]).rglob("*.fastq.gz"))), 6)
            mapping = Path(p["destination_root"]) / "audit/file_mapping.tsv"
            self.assertNotIn("modality_evidence", mapping.read_text().splitlines()[0])
            mapping.write_text(mapping.read_text().replace("Synthetic specimen/library record", "Unapproved evidence"))
            with self.assertRaises(t.Blocked):
                t.verify(p, plan)
            with self.assertRaisesRegex(ValueError, "Stored report differs"):
                html_report.build_verified_report(base / "work" / "ready" / "plan.json")


if __name__ == "__main__":
    unittest.main()
