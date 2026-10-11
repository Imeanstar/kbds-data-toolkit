import base64
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "skills/kbds-data-organizer/scripts/build_html_report.py"
SPEC = importlib.util.spec_from_file_location("build_html_report", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class HtmlReportTest(unittest.TestCase):
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
