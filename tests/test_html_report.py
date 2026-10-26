import base64
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "skills/kbds-data-organizer/scripts/build_html_report.py"
SPEC = importlib.util.spec_from_file_location("build_html_report", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def example_plan(repository="KRA"):
    return {
        "policy": {"source_root": "/private/Study", "destination_root": "/private/Study_makeup", "mode": "practice"},
        "inventory": [{"source_relative": "batch/S_R1.fq.gz", "size": 0, "kind": "raw_fastq_candidate"},
                      {"source_relative": "batch/S_R2.fq.gz", "size": 0, "kind": "raw_fastq_candidate"}],
        "files": [{"repository": repository, "study": "Study", "modality": "bulk", "sample_group": "B",
                   "sample": "S", "specimen": "Specimen", "experiment": "E", "run": "Run1", "file_role": role,
                   "evidence": "Approved synthetic record", "modality_evidence": "Synthetic modality"}
                  for role in ("R1", "R2")],
        "excluded": [], "unresolved": [], "errors": [], "plan_sha256": "abc123",
        "approval_scope_sha256": "scope123",
    }


class HtmlReportTest(unittest.TestCase):
    def test_english_translates_generated_content_and_preserves_original_evidence(self):
        for repository in ("KRA", "GEO"):
            plan = example_plan(repository)
            original = copy.deepcopy(plan)
            data, branches = MODULE.plan_report_content(plan, "en")
            all_text = json.dumps(data, ensure_ascii=False) + str(branches) + MODULE.structure_svg(branches, "en")
            self.assertFalse(any("\uac00" <= char <= "\ud7a3" for char in all_text))
            self.assertIn("2 included files", all_text)
            self.assertIn("submission_ready=false", all_text)
            self.assertIn("zero-byte placeholders", all_text)
            self.assertIn("biological", all_text)
            self.assertIn("scope123", all_text)
            self.assertEqual(plan, original)
            if repository == "GEO":
                self.assertIn("Sample not recorded", all_text)
            else:
                self.assertIn("IDs 1 / specimens 1", all_text)
            plan["files"][0]["evidence"] = "<script>원본 기록</script>"
            data, branches = MODULE.plan_report_content(plan, "en")
            data["destination_label"] = '<img src=x onerror="alert(1)">'
            with tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / "report.html"
                MODULE.build_report(data, Path(tmp) / "plan.json", output,
                                    svg=MODULE.structure_svg(branches, "en"), language="en")
                html = output.read_text(encoding="utf-8")
                self.assertIn('<html lang="en">', html)
                self.assertIn("Save as PDF / Print", html)
                self.assertIn("Source folder", html)
                self.assertIn("&lt;script&gt;원본 기록&lt;/script&gt;", html)
                self.assertIn("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;", html)
                self.assertNotIn("<script>", html)
                self.assertNotIn('<img src=x', html)
                self.assertNotIn('src="http', html)
                with self.assertRaises(FileExistsError):
                    MODULE.build_report(data, Path(tmp) / "plan.json", output, svg="<svg/>", language="ko")

    def test_default_korean_and_explicit_korean_match_and_invalid_language_stops_early(self):
        plan = example_plan()
        self.assertEqual(MODULE.plan_report_content(plan), MODULE.plan_report_content(plan, "ko"))
        korean, _ = MODULE.plan_report_content(plan)
        self.assertIn("연습 모드", " ".join(korean["results"]))
        production = copy.deepcopy(plan)
        production["policy"]["mode"] = "production"
        english, _ = MODULE.plan_report_content(production, "en")
        self.assertNotIn("Practice mode", " ".join(english["results"]))
        self.assertIn("submission_ready=false", english["results"])
        with mock.patch.object(MODULE.importlib.util, "spec_from_file_location") as load:
            with self.assertRaisesRegex(ValueError, "language"):
                MODULE.build_verified_report("/missing/plan.json", "invalid")
            load.assert_not_called()

    def test_self_contained_report_and_escaping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tree.png").write_bytes(base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+XGZkAAAAASUVORK5CYII="
            ))
            data = {
                "title": "Example <Study>",
                "source_path": "/source & raw",
                "destination_paths": ["/output"],
                "destination_label": "생성 예정 폴더",
                "structure_image": "tree.png",
                "results": ["검증 <완료>"],
                "relationships": ["R1 & R2"],
            }
            data_path = root / "report.json"
            data_path.write_text(json.dumps(data), encoding="utf-8")
            output = root / "report.html"
            MODULE.build_report(data, data_path, output)
            html = output.read_text(encoding="utf-8")
            self.assertIn("Example &lt;Study&gt;", html)
            self.assertIn("/source &amp; raw", html)
            self.assertIn("생성 예정 폴더", html)
            self.assertIn("data:image/png;base64,", html)
            self.assertLess(html.index("<h1>"), html.index("class=\"paths\""))
            self.assertLess(html.index("<figure>"), html.index("id=\"results\""))
            self.assertLess(html.index("id=\"results\""), html.index("id=\"relationships\""))
            with self.assertRaises(FileExistsError):
                MODULE.build_report(data, data_path, output)
            english_output = root / "report-en.html"
            result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--data", str(data_path),
                                     "--output", str(english_output), "--language", "en"],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            english = english_output.read_text(encoding="utf-8")
            self.assertIn('<html lang="en">', english)
            self.assertIn("Save as PDF / Print", english)
            self.assertIn("검증 &lt;완료&gt;", english)

    def test_plan_report_uses_confirmed_mapping_and_embeds_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = {
                "policy": {"source_root": "/private/Study", "destination_root": "/private/Study_makeup", "mode": "practice"},
                "inventory": [{"source_relative": "batch/S_R1.fastq.gz", "size": 0, "kind": "raw_fastq_candidate"},
                              {"source_relative": "batch/S_R2.fastq.gz", "size": 0, "kind": "raw_fastq_candidate"}],
                "files": [{"repository": "KRA", "study": "Study<1>", "modality": "bulk", "sample_group": "B",
                           "sample": "S", "specimen": "Specimen", "experiment": "E", "run": "Run1", "file_role": role,
                           "evidence": "승인된 기록", "modality_evidence": "bulk 실험 기록"}
                          for role in ("R1", "R2")],
                "excluded": [], "unresolved": [], "errors": [], "plan_sha256": "abc123",
            }
            data, branches = MODULE.plan_report_content(plan)
            self.assertIn("B: 1 ID / 1 검체", branches[0])
            self.assertIn("1 Run", branches[0])
            self.assertIn("R1 1, R2 1", branches[0])
            svg = MODULE.structure_svg(branches)
            self.assertIn("Study&lt;1&gt;", svg)
            output = root / "report.html"
            MODULE.build_report(data, root / "plan.json", output, svg=svg)
            html = output.read_text(encoding="utf-8")
            self.assertIn("data:image/svg+xml;base64,", html)
            self.assertIn("생물학적 관계", html)
            self.assertIn("승인된 기록", html)


if __name__ == "__main__":
    unittest.main()
