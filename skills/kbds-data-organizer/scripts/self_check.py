"""Exercise a real copy, verify and report using only synthetic /tmp files on Linux."""

from pathlib import Path
import tempfile

import build_html_report
import toolkit


def main():
    if not toolkit.FILESYSTEM_SUPPORTED:
        raise SystemExit("Self-check requires Linux")
    with tempfile.TemporaryDirectory(prefix="kbds-self-check-") as scratch:
        base = Path(scratch).resolve()
        source = base / "Example"
        source.mkdir()
        decisions = {"files": {}}
        for mate in ("R1", "R2"):
            filename = f"S_{mate}.fastq.gz"
            (source / filename).touch()
            decisions["files"][filename] = {
                "action": "include", "reason": "Synthetic self-check", "evidence": "Synthetic self-check",
                "repository": "KRA", "study": "Example", "sample_group": "B", "sample": "S",
                "specimen": "Specimen", "assay": "WES", "experiment": "Library", "run": "Run",
                "layout": "PAIRED", "file_role": mate, "raw_confirmed": True,
                "modality": "bulk", "modality_evidence": "Synthetic protocol", "data_role": "raw_reads",
            }
        policy = {"version": 1, "layout_version": 2, "repository_scope": "KRA", "mode": "practice",
                  "source_root": str(source), "destination_root": str(base / "Example_makeup"),
                  "workspace_root": str(base / "work"), "allow_practice_zero_bytes": True,
                  "reserve_bytes": 0}
        plan = toolkit.make_plan(policy, decisions, "test")
        if plan["status"] != "READY_FOR_APPROVAL":
            raise RuntimeError("Synthetic plan did not pass")
        # Only this isolated synthetic plan is approved by the self-check itself.
        toolkit.apply(policy, plan, plan["plan_sha256"])
        report = build_html_report.build_verified_report(base / "work" / "test" / "plan.json")
        if not report.is_file() or not all((source / name).is_file() for name in decisions["files"]):
            raise RuntimeError("Synthetic copy/report/source check failed")
    print("PASS: synthetic copy, verify, report; no research files accessed")


if __name__ == "__main__":
    main()
