"""Build a self-contained, printable local HTML report from reviewed JSON."""

import argparse
import base64
from collections import Counter, defaultdict
from html import escape
import importlib.util
import json
from pathlib import Path


def language_text(language):
    if language not in ("ko", "en"):
        raise ValueError("Report language must be ko or en")
    return lambda ko, en: ko if language == "ko" else en


def build_report(data, data_path, output, svg=None, language="ko"):
    say = language_text(language)
    required = ("title", "source_path", "destination_paths", "results", "relationships")
    if svg is None:
        required += ("structure_image",)
    for key in required:
        if not data.get(key):
            raise ValueError("Missing report field: " + key)
    for key in ("destination_paths", "results", "relationships"):
        if not isinstance(data[key], list) or not all(isinstance(x, str) and x.strip() for x in data[key]):
            raise ValueError(key + " must be a nonempty list of text")
    if svg is None:
        image_path = Path(data["structure_image"])
        if not image_path.is_absolute():
            image_path = data_path.parent / image_path
        if image_path.suffix.lower() != ".png" or not image_path.is_file():
            raise ValueError("structure_image must be an existing PNG")
        image_bytes, image_type = image_path.read_bytes(), "image/png"
    else:
        image_bytes, image_type = svg.encode("utf-8"), "image/svg+xml"
    output = Path(output)
    if output.exists():
        raise FileExistsError("Report exists; choose a new output or explicitly remove it")

    h = lambda value: escape(value, quote=True)
    paragraphs = lambda values: "\n".join(f"<p>{h(value)}</p>" for value in values)
    image = base64.b64encode(image_bytes).decode("ascii")
    paths = "\n".join(
        f'<div><span>{h(label)}</span><code>{h(value)}</code></div>'
        for label, value in [(say("원본 폴더", "Source folder"), data["source_path"])]
        + [(data.get("destination_label", say("생성 폴더", "Output folder")), value) for value in data["destination_paths"]]
    )
    document = f"""<!doctype html>
<html lang="{language}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{h(data['title'])}</title>
<style>
  :root {{ color-scheme: light; font-family: "Malgun Gothic", "Apple SD Gothic Neo", sans-serif; color: #1e293b; background: #f3f6fa; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; line-height: 1.68; }}
  main {{ max-width: 1060px; margin: 34px auto 60px; padding: 52px 60px; background: white; box-shadow: 0 10px 36px #1e293b17; }}
  h1 {{ margin: 0 0 21px; font-size: 30px; line-height: 1.35; letter-spacing: -.035em; }}
  h2 {{ margin: 38px 0 11px; padding-bottom: 7px; border-bottom: 2px solid #cbd5e1; font-size: 19px; }}
  p {{ margin: 0 0 10px; }}
  .paths {{ text-align: right; color: #475569; font-size: 12px; }}
  .paths div {{ margin: 3px 0; }}
  .paths span {{ display: inline-block; min-width: 75px; margin-right: 12px; font-weight: 700; }}
  .paths code {{ font-family: Consolas, monospace; overflow-wrap: anywhere; }}
  figure {{ margin: 28px 0 0; }}
  figure img {{ display: block; width: 100%; height: auto; border: 1px solid #dbe4ef; }}
  figcaption {{ margin-top: 8px; color: #64748b; font-size: 12px; }}
  .section p {{ padding-left: 13px; border-left: 3px solid #e2e8f0; }}
  .print {{ position: fixed; top: 18px; right: 22px; border: 0; border-radius: 8px; padding: 9px 14px; background: #1d4ed8; color: white; font: inherit; cursor: pointer; }}
  @media (max-width: 700px) {{ main {{ margin: 0; padding: 25px 18px; box-shadow: none; }} h1 {{ font-size: 24px; }} .paths {{ text-align: left; }} }}
  @media print {{ @page {{ size: A4; margin: 14mm; }} :root {{ background: white; }} main {{ width: 100%; max-width: none; margin: 0; padding: 0; box-shadow: none; font-size: 14px; line-height: 1.5; }} h1 {{ font-size: 26px; }} .print {{ display: none; }} .section:first-of-type {{ break-before: page; }} figure, h2 {{ break-after: avoid; }} .section p {{ break-inside: avoid; }} }}
</style>
</head>
<body>
<button class="print" type="button" onclick="window.print()">{say('PDF로 저장 / 인쇄', 'Save as PDF / Print')}</button>
<main>
  <h1>{h(data['title'])}</h1>
  <div class="paths">{paths}</div>
  <figure>
    <img src="data:{image_type};base64,{image}" alt="{h(data.get('image_alt', say('Study, Sample, Experiment, Run과 파일 수를 나타낸 폴더 구조', 'Folder structure with Study, Sample, Experiment, Run and file counts')))}">
    <figcaption>{h(data.get('image_caption', say('실제 생성된 폴더 구조', 'Created folder structure')))}</figcaption>
  </figure>
  <section class="section" aria-labelledby="results"><h2 id="results">{say('조사 결과', 'Results')}</h2>{paragraphs(data['results'])}</section>
  <section class="section" aria-labelledby="relationships"><h2 id="relationships">{say('구조상 확인된 관계', 'Relationships recorded in the mapping')}</h2>{paragraphs(data['relationships'])}</section>
</main>
</body>
</html>
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(document)


def plan_report_content(plan, language="ko"):
    """Summarize only mappings recorded in the approved plan; do not infer biology."""
    say = language_text(language)
    rows = plan["files"]
    groups = defaultdict(list)
    for row in rows:
        key = (row["modality"], row["study"], row["sample_group"] if row["repository"] == "KRA" else row["repository"])
        groups[key].append(row)
    branches, relationships = [], []
    for (modality, study, group), members in sorted(groups.items()):
        proofs = sorted({(r.get("evidence", ""), r.get("modality_evidence", "")) for r in members})
        shown = "; ".join(say(f"파일: {evidence} / 유형: {modality_evidence}",
                             f"File evidence: {evidence} / Modality evidence: {modality_evidence}")
                          for evidence, modality_evidence in proofs[:3])
        proof_note = say(f" 근거: {shown}.", f" Evidence: {shown}.") if shown else say(
            " 근거는 plan.json에 기록되어 있습니다.", " Evidence is recorded in plan.json.")
        if len(proofs) > 3:
            proof_note += say(f" 추가 근거 {len(proofs) - 3}건은 plan.json을 확인하십시오.",
                              f" See plan.json for {len(proofs) - 3} additional evidence records.")
        if members[0]["repository"] == "KRA":
            sample_ids = {r["sample"] for r in members}
            specimens = {r["specimen"] for r in members}
            experiments = {(r["sample"], r["experiment"]) for r in members}
            runs = {(r["sample"], r["experiment"], r["run"]) for r in members}
            roles = Counter(r["file_role"] for r in members)
            branches.append((f"{modality} / {study}", say(f"{group}: {len(sample_ids)} ID / {len(specimens)} 검체",
                                                        f"{group}: IDs {len(sample_ids)} / specimens {len(specimens)}"),
                             f"{len(experiments)} Experiment", f"{len(runs)} Run",
                             ", ".join(f"{role} {count}" for role, count in sorted(roles.items()))))
            relationships.append(say(f"{study} / {modality} / {group}: 승인된 매핑에 Sample ID {len(sample_ids)}개, "
                                 f"검체 {len(specimens)}개, "
                                 f"Experiment {len(experiments)}개, Run {len(runs)}개가 기록되어 있습니다. "
                                 f"파일 역할은 {', '.join(f'{role} {count}개' for role, count in sorted(roles.items()))}입니다.",
                                 f"{study} / {modality} / {group}: the approved mapping records Sample IDs: {len(sample_ids)}, "
                                 f"specimens: {len(specimens)}, Experiments: {len(experiments)}, Runs: {len(runs)}. "
                                 f"File roles: {', '.join(f'{role}: {count}' for role, count in sorted(roles.items()))}.")
                                 + proof_note)
        else:
            branches.append((f"{modality} / {study}", group, say("Sample 미기록", "Sample not recorded"),
                             say("Experiment·Run 미기록", "Experiment/Run not recorded"),
                             say(f"파일 {len(members)}개", f"{len(members)} files")))
            relationships.append(say(f"{study} / {modality} / {group}: 파일 {len(members)}개가 "
                                 "원본 상대 경로를 유지합니다. Sample·Experiment·Run 관계는 이 계획에 기록되지 않았습니다.",
                                 f"{study} / {modality} / {group}: {len(members)} files retain their source-relative paths. "
                                 "Sample, Experiment and Run relationships are not recorded in this plan.")
                                 + proof_note)
    inventory = plan["inventory"]
    kinds = Counter(r["kind"] for r in inventory)
    source_dirs = {str(parent) for r in inventory for parent in Path(r["source_relative"]).parents
                   if str(parent) != "."}
    results = [
        say(f"원본 목록: 파일 {len(inventory)}개, 파일 경로상 확인된 하위 폴더 {len(source_dirs)}개, "
            f"총 {sum(r['size'] for r in inventory):,}바이트.",
            f"Source inventory: {len(inventory)} files, {len(source_dirs)} subfolders represented by file paths, "
            f"{sum(r['size'] for r in inventory):,} bytes total."),
        say("확인된 파일 종류 후보: " + ", ".join(f"{kind} {count}개" for kind, count in sorted(kinds.items())) + ".",
            "File-type candidates: " + ", ".join(f"{kind}: {count}" for kind, count in sorted(kinds.items())) + "."),
        say(f"복사·검증 완료: 포함 {len(rows)}개, 제외 {len(plan['excluded'])}개, "
        f"미해결 {len(plan['unresolved'])}개, 목록 오류 {len(plan['errors'])}개. "
        f"검증 모드: {plan['policy']['mode']}. 계획 SHA-256: {plan['plan_sha256']}.",
        f"Copy and verification complete: {len(rows)} included files, {len(plan['excluded'])} excluded, "
        f"{len(plan['unresolved'])} unresolved, {len(plan['errors'])} inventory errors. "
        f"Validation mode: {plan['policy']['mode']}. Plan SHA-256: {plan['plan_sha256']}."),
        say("이 폴더는 제출용 임시 정리 결과입니다. 저장소 제출 가능 여부와 생물학적 동일성은 검증하지 않았습니다.",
            "This folder is a staging result. Archive submission eligibility and biological identity were not verified."),
        "submission_ready=false",
    ]
    if plan["policy"]["mode"] == "practice":
        results.append(say("연습 모드는 0바이트 자리표시자의 경로와 크기만 검사했습니다. 연습용 가정은 실데이터의 확인 사실이 아닙니다.",
                           "Practice mode checks only paths and sizes of zero-byte placeholders. Fictional practice assumptions are not verified facts about research data."))
    if plan.get("report_format_version", 1) == 3:
        results.append(say("audit/에는 복사와 검증에 필요한 실행 기록을 저장했습니다. 샘플·실험 메타데이터 표와 제출 서식은 생성하지 않았습니다. 해당 작업은 별도 도구에서 수행합니다.",
                           "The audit/ folder contains copy and verification records. No sample/experiment metadata tables or submission forms were generated. A separate tool handles that work."))
    if "approval_scope_sha256" in plan:
        results.append(say("승인된 범위 정책으로 계획·복사·검증을 자동 실행했습니다. 범위 SHA-256: ",
                           "Planning, copying and verification ran under an approved scoped policy. Scope SHA-256: ")
                       + plan["approval_scope_sha256"] + ".")
    relationships.append(say("위 관계는 승인된 파일 매핑의 구조입니다. 같은 ID의 생물학적 관계는 별도 근거 없이 확정하지 않았습니다.",
                             "These relationships describe the approved file mapping. Shared IDs do not establish biological relationships without separate evidence."))
    data = {"title": say(f"{Path(plan['policy']['source_root']).name} 데이터 정리 보고서",
                          f"{Path(plan['policy']['source_root']).name} data staging report"),
            "source_path": plan["policy"]["source_root"],
            "destination_paths": [plan["policy"]["destination_root"]],
            "image_caption": say("검증된 출력의 분류별 구조 요약. 숫자는 해당 가지에 포함된 고유 항목 또는 파일 수입니다.",
                                 "Verified output structure by category. Counts show unique entries or files in each branch."),
            "results": results, "relationships": relationships}
    return data, branches


def structure_svg(branches, language="ko"):
    """A small, self-contained Study → Sample → Experiment → Run diagram."""
    say = language_text(language)
    columns = ((20, 216), (250, 174), (458, 174), (666, 174), (874, 300))
    height = 66 + 94 * len(branches)
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}">',
             '<rect width="1200" height="100%" fill="#f8fafc"/>',
             '<style>text{font:16px sans-serif;fill:#172554}.small{font:12px sans-serif;fill:#475569}</style>',
             '<text x="20" y="31" class="small">' + say(
                 'Study / 유형 → Sample → Experiment → Run → 파일 역할',
                 'Study / modality → Sample → Experiment → Run → file roles') + '</text>']
    for index, branch in enumerate(branches):
        y = 47 + index * 94
        for col, (x, width) in enumerate(columns):
            title = escape(branch[col])
            lines += [f'<rect x="{x}" y="{y}" width="{width}" height="64" rx="9" fill="white" stroke="#94a3b8"/>',
                      f'<text x="{x+10}" y="{y+25}" textLength="{min(width-20, max(1, len(branch[col])*9))}" lengthAdjust="spacingAndGlyphs">{title}</text>']
            if col < 4:
                lines.append(f'<path d="M{x+width} {y+32}h{columns[col+1][0]-x-width-5}" stroke="#64748b" marker-end="url(#arrow)"/>')
    lines.insert(3, '<defs><marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="none" stroke="#64748b"/></marker></defs>')
    return "".join(lines) + "</svg>"


def build_verified_report(plan_path, language="ko"):
    """Write one new report beside a verified plan on the Linux data host."""
    language_text(language)
    script = Path(__file__).with_name("toolkit.py")
    spec = importlib.util.spec_from_file_location("kbds_report_toolkit", script)
    toolkit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(toolkit)
    plan_path = Path(plan_path).absolute()
    preview = toolkit.load_json(str(plan_path))
    plan = toolkit.read_plan(preview["policy"], str(plan_path))
    toolkit.require(plan["policy"].get("layout_version") == 2,
                    "Automatic HTML reports require a layout-version-2 plan")
    toolkit.verify(plan["policy"], plan)
    data, branches = plan_report_content(plan, language)
    output = plan_path.with_name("report.html")
    build_report(data, plan_path, output, svg=structure_svg(branches, language), language=language)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--data", help="Private local report JSON")
    source.add_argument("--plan", help="Verified plan.json on the Linux data host")
    parser.add_argument("--output", help="New private local HTML path; used with --data")
    parser.add_argument("--language", choices=("ko", "en"), default="ko", help="Report language; supplied evidence stays unchanged")
    args = parser.parse_args()
    if args.plan:
        if args.output:
            parser.error("--plan writes report.html beside the plan; omit --output")
        print(build_verified_report(args.plan, args.language))
    else:
        if not args.output:
            parser.error("--data requires --output")
        data_path = Path(args.data).resolve()
        build_report(json.loads(data_path.read_text(encoding="utf-8")), data_path, args.output, language=args.language)
