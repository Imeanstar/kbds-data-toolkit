"""Portable parsing checks and Linux copy regressions; synthetic records only."""
import contextlib
import copy
import csv
import gzip
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/kbds-data-organizer/scripts"))
import toolkit as t
import test_toolkit as fixtures


class ParsingTests(unittest.TestCase):
    def test_mixed_mate_conventions_do_not_form_a_pair(self):
        def rows(names):
            result = [{"source_relative": name, "size": 0, "repository": "KRA", "study": "Study",
                       "sample": "Sample", "experiment": "Library", "run": "Run", "layout": "PAIRED",
                       "raw_confirmed": True} for name in names]
            for row in result:
                row["destination_relative"] = t.target_path(row)
            return result
        for names in (("Sample_R1.fq", "Sample-2.fq"), ("Sample.R1.fq", "Sample_R2.fq"),
                      ("Sample_1.fq", "Sample-2.fq")):
            with self.subTest(names=names), self.assertRaisesRegex(t.Blocked, "Inconsistent mate"):
                t.validate_rows(rows(names), "practice")
        self.assertEqual(len(t.validate_rows(rows(("Sample_r1.FQ", "Sample_R2.fq")), "practice")), 1)

    def test_dot_mates_preserve_internal_replicate_tokens(self):
        for stem in ("Sample-R5", "Sample-R11", "Sample_R1_2", "Sample.1"):
            for extension in (".fq.gz", ".FASTQ", ".fastq.gz"):
                keys = [t.pair_key(f"batch/{stem}.R{mate}{extension}") for mate in (1, 2)]
                self.assertEqual(keys, [(f"batch/{stem}{extension.lower()}", "1"),
                                       (f"batch/{stem}{extension.lower()}", "2")])
        self.assertEqual(t.pair_key("batch/Sample.1.fq"), ("batch/Sample.fq", "1"))
        self.assertIsNone(t.pair_match(".R1.fq.gz"))

    def test_destination_aliases_and_prefix_conflicts_are_blocked_in_both_orders(self):
        for paths in (("Study/A/x.txt", "Study/a/y.txt"),
                      ("Study/caf\u00e9/x.txt", "Study/cafe\u0301/y.txt"),
                      ("Study/a", "Study/a/b.txt"), ("Study/A", "Study/a/b.txt"),
                      ("Study/x.txt", "Study/X.txt")):
            for ordered in (paths, paths[::-1]):
                with self.subTest(paths=ordered), self.assertRaisesRegex(t.Blocked, "collision"):
                    t.validate_output_paths(ordered)
        t.validate_output_paths(["Study/shared/x.txt", "Study/shared/y.txt", "Study/\uac80\uccb4.txt"])

    def test_nonportable_names_stop_without_renaming(self):
        names = ["CON", "nul.txt", "CON .txt", "NUL .fq", "CONIN$", "CONOUT$", "COM1.fq.gz", "LPT\u00b2.txt", "name.", "name ",
                 "a:b.txt", "a\\b.txt", "a?b.txt", "a*b.txt", "a\"b.txt", "a|b.txt", "a<b.txt",
                 "\uac00" * 86, "bad\udcff.txt"]
        for name in names:
            with self.subTest(name=repr(name)), self.assertRaises(t.Blocked):
                t.validate_output_paths(["Study/" + name])
        t.validate_output_paths(["Study/CON_sample.txt", "Study/normal name.txt", "Study/COM10.txt"])

    def reads(self, content, compressed=False):
        @contextlib.contextmanager
        def regular(*args, **kwargs):
            with io.BytesIO(content) as stream:
                yield stream
        with mock.patch.object(t, "regular", regular):
            return list(t.fastq_ids(None, {"source_relative": "sample.fq" + (".gz" if compressed else "")}))

    def test_iupac_bases_crlf_and_repeated_titles_are_supported(self):
        bases = b"ACGTURYSWKMBDHVNacgturyswkmbdhvn"
        record = b"@read/1 1:N:0:AC\r\n" + bases + b"\r\n+read/1 1:N:0:AC\r\n" + b"I" * len(bases) + b"\r\n"
        self.assertEqual(self.reads(record), [(b"read", "1")])
        compressed = gzip.compress(record) + gzip.compress(record.replace(b"read", b"other"))
        self.assertEqual(self.reads(compressed, True), [(b"read", "1"), (b"other", "1")])

    def test_invalid_bases_plus_titles_and_truncated_gzip_are_rejected(self):
        valid = b"@read/1\nACGT\n+\nIIII\n"
        for content in (valid.replace(b"ACGT", b"AC?T"), valid.replace(b"ACGT", b"A0.1"),
                        valid.replace(b"+\n", b"+other/1\n"), valid.replace(b"ACGT", b"A CG")):
            with self.subTest(content=content), self.assertRaises(t.Blocked):
                self.reads(content)
        with self.assertRaises((EOFError, OSError)):
            self.reads(gzip.compress(valid)[:-5], True)

    def test_header_controls_block_but_tab_metadata_is_supported(self):
        for control in (b"\x00", b"\x01", b"\x0b", b"\x1f", b"\x7f"):
            with self.subTest(control=control), self.assertRaisesRegex(t.Blocked, "control character"):
                self.reads(b"@read" + control + b"/1\nACGT\n+\nIIII\n")
        self.assertEqual(self.reads(b"@read/1\t1:N:0:AC\r\nACGT\r\n+read/1\t1:N:0:AC\r\nIIII\r\n"),
                         [(b"read", "1")])

    def test_versioned_tsv_quotes_formulas_and_keeps_original_json(self):
        text = " \t=1+2\nsecond line"
        plan = {"policy": {}, "inventory": [], "files": [], "unresolved": [], "errors": [],
                "excluded": [{"source_relative": "=1+2", "reason": text}]}
        legacy = t.report_bytes(plan)
        modern = t.report_bytes({**plan, "report_format_version": 2})
        parsed = lambda data: list(csv.DictReader(io.StringIO(data.decode()), delimiter="\t"))[0]
        self.assertEqual(parsed(legacy["excluded.tsv"]), plan["excluded"][0])
        self.assertEqual(parsed(modern["excluded.tsv"]), {"source_relative": "'=1+2", "reason": "'" + text})
        self.assertEqual(json.loads(modern["plan.json"])["excluded"], plan["excluded"])
        for prefix in ("=", "+", "-", "@", "\t=", "\r=", "\n="):
            value = prefix + "example"
            result = t.tsv_bytes([{"value": value}], ["value"], spreadsheet_safe=True)
            self.assertEqual(parsed(result)["value"], "'" + value)
        with self.assertRaisesRegex(t.Blocked, "report_format_version"):
            t.report_bytes({**plan, "report_format_version": 99})

    def test_v2_tsv_quotes_cr_but_preserves_embedded_line_endings_and_legacy_bytes(self):
        rows = [{"a": "line\rreturn", "b": "normal"}, {"a": "plain", "b": "line\r\nbreak"}]
        modern = t.tsv_bytes(rows, ["a", "b"], spreadsheet_safe=True)
        self.assertEqual(modern, b'a\tb\n"line\rreturn"\tnormal\nplain\t"line\r\nbreak"\n')
        self.assertEqual(list(csv.DictReader(io.StringIO(modern.decode(), newline=""), delimiter="\t")), rows)
        legacy = io.StringIO(newline="")
        writer = csv.DictWriter(legacy, ["a", "b"], delimiter="\t", extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        self.assertEqual(t.tsv_bytes(rows, ["a", "b"]), legacy.getvalue().encode())

    def test_v3_exports_file_audit_without_sample_metadata(self):
        row = {"source_relative": "source_R1.fq", "destination_relative": "copy/source_R1.fq",
               "size": 0, "sha256": None, "repository": "KRA", "file_role": "R1",
               "reason": "Approved copy", "evidence": "=user supplied evidence",
               "study": "Study", "sample_group": "D", "sample": "Sample", "specimen": "Specimen",
               "assay": "Assay", "experiment": "Library", "run": "Run", "layout": "PAIRED",
               "modality": "bulk", "modality_evidence": "Approved only for naming"}
        plan = {"report_format_version": 3, "policy": {"layout_version": 2}, "inventory": [],
                "files": [row], "unresolved": [], "errors": [], "excluded": []}
        reports = t.report_bytes(plan)
        self.assertEqual(set(reports), {"plan.json", "inventory.tsv", "file_mapping.tsv",
                                       "unresolved.tsv", "excluded.tsv"})
        parsed = list(csv.DictReader(io.StringIO(reports["file_mapping.tsv"].decode()), delimiter="\t"))
        self.assertEqual(list(parsed[0]), ["source_relative", "destination_relative", "size", "sha256",
                                          "repository", "file_role", "reason", "evidence"])
        self.assertEqual(parsed[0]["evidence"], "'=user supplied evidence")
        self.assertEqual(json.loads(reports["plan.json"])["files"], [row])
        self.assertEqual(t.audit_prefix(plan), "audit/")
        legacy = t.report_bytes({**plan, "report_format_version": 2})
        self.assertEqual(legacy["sample_mapping.tsv"],
                         b"study\tsample_group\tsample\tspecimen\tassay\texperiment\tmodality\n"
                         b"Study\tD\tSample\tSpecimen\tAssay\tLibrary\tbulk\n")
        self.assertIn(b"\trun\tlayout\tmodality\t", legacy["file_mapping.tsv"].splitlines()[0])


@unittest.skipUnless(t.FILESYSTEM_SUPPORTED, "Linux no-follow filesystem integration required")
class CopyRegressionTests(unittest.TestCase):
    def setUp(self):
        # Reuse the synthetic fixture, without inheriting/rerunning its entire suite.
        self.fixture = fixtures.ToolkitTests(methodName="test_copy_and_verify_preserve_source")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_legacy_tsv_package_still_verifies_and_new_package_detects_tampering(self):
        fixture = self.fixture
        for decision in fixture.decisions["files"].values():
            decision["evidence"] = "=1+2"
        plan = fixture.plan()
        self.assertEqual(plan["report_format_version"], 3)
        t.apply(fixture.policy, plan, plan["plan_sha256"])
        self.assertIn("'=1+2", (fixture.dest / "audit/file_mapping.tsv").read_text())
        t.verify(fixture.policy, plan)
        # Simulate old approved packages, never upgrade their bytes in place.
        for version in (1, 2):
            with self.subTest(legacy_version=version):
                legacy = copy.deepcopy(plan)
                if version == 1:
                    del legacy["report_format_version"]
                else:
                    legacy["report_format_version"] = version
                output = fixture.base / f"legacy-{version}"
                legacy["policy"]["destination_root"] = str(output)
                legacy["plan_sha256"] = t.digest({k: v for k, v in legacy.items() if k != "plan_sha256"})
                with self.assertRaisesRegex(t.Blocked, "Create a new plan"):
                    t.apply(legacy["policy"], legacy, legacy["plan_sha256"])
                self.assertFalse(output.exists())
                # A historical fixture is created directly; the engine must not emit old metadata.
                for row in legacy["files"]:
                    target = output / row["destination_relative"]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes((fixture.src / row["source_relative"]).read_bytes())
                records = output / "metadata"
                records.mkdir()
                for name, data in t.report_bytes(legacy).items():
                    (records / name).write_bytes(data)
                events = [t.copy_event(index, row, len(legacy["files"]))
                          for index, row in enumerate(legacy["files"], 1)]
                (records / "events.jsonl").write_text("".join(json.dumps(event) + "\n" for event in events))
                (records / "COMPLETE.json").write_bytes(t.json_bytes(t.completion_record(legacy)))
                before = {p.name: p.read_bytes() for p in (output / "metadata").iterdir()}
                t.verify(legacy["policy"], legacy)
                self.assertEqual(before, {p.name: p.read_bytes() for p in (output / "metadata").iterdir()})
                self.assertEqual(len(before), 8)
                self.assertIn("sample_mapping.tsv", before)
                self.assertFalse((output / "audit").exists())
                self.assertIn("\t=1+2" if version == 1 else "\t'=1+2",
                              before["file_mapping.tsv"].decode())
        path = fixture.dest / "audit/file_mapping.tsv"
        path.write_text(path.read_text().replace("'=1+2", "=1+2"))
        with self.assertRaisesRegex(t.Blocked, "Stored report differs"):
            t.verify(fixture.policy, plan)

    def test_invalid_fastq_is_blocked_before_output_creation(self):
        fixture = self.fixture
        fixture.production()
        path = fixture.src / "example_R1.fastq.gz"
        content = gzip.decompress(path.read_bytes()).replace(b"ACGT", b"A?GT")
        path.write_bytes(gzip.compress(content))
        plan = fixture.plan()
        with self.assertRaisesRegex(t.Blocked, "nucleotide"):
            t.apply(fixture.policy, plan, plan["plan_sha256"])
        self.assertFalse(fixture.dest.exists())

    def test_copy_returns_separate_monotonic_phase_timings(self):
        fixture = self.fixture
        plan = fixture.plan()
        timings = t.apply(fixture.policy, plan, plan["plan_sha256"])
        self.assertEqual(set(timings), {"preflight", "copy_and_metadata", "verification", "total"})
        self.assertTrue(all(value >= 0 for value in timings.values()))
        self.assertAlmostEqual(sum(value for key, value in timings.items() if key != "total"), timings["total"])


if __name__ == "__main__":
    unittest.main()
