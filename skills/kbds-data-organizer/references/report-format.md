# HTML 보고서 기본양식

기본 산출물은 단일 HTML 파일이다. 외부 이미지·CSS·폰트를 참조하지 않아 오프라인에서
열 수 있고, 브라우저의 **PDF로 저장 / 인쇄** 버튼으로 PDF를 내보낼 수 있다.

내용 순서:

1. 맨 위에 보고서 제목.
2. 바로 아래에 원본 및 생성 폴더의 전체 경로를 우측 정렬. 생성 폴더가 여러 개면 모두 표시.
3. 실제 생성·검증된 Study → Sample → Experiment → Run → 파일 역할 구조 이미지.
   각 가지의 개수를 기입하고, 그룹 수와 개별 ID·검체 수를 혼동하지 않는다.
   확인된 B/D/R은 Sample에서 분리하고, 각 paired Run의 파일 역할은 R1/R2로 표시한다.
4. **조사 결과**: 파일·폴더 수, 용량, 형식, 분류·복사·검증 상태, 제외·미해결 항목과 한계.
5. **구조상 확인된 관계**: ID·R1/R2·batch 등의 관계와 그 근거. 확인 사실, 이번 작업의
   임시 가정, 미확정 해석을 구별한다.

미실행 구조는 반드시 `예정`이라 표시한다. 기존 결과를 새 규칙으로 재배치하지 않았다면
새 구조를 생성 결과처럼 그리지 않는다. 정보가 없는 항목은 0으로 채우지 않는다.
연습용 가정은 비공개 작업 기록과 해당 보고서에서만 설명하고 재사용 가능한 기본값으로 두지 않는다.

## 생성 및 검토

서버에서 승인된 계획을 `apply`한 뒤 저장소 루트에서
`python3 scripts/kbds.py report --plan <private-workspace>/<plan-name>/plan.json`을 실행한다.
OpenCode의 `kbds-stage`에서만 이 명령을 승인 요청할 수 있다. `kbds-review`는 대화 보고서만 쓴다.
독립 스킬을 다른 에이전트에서 쓰면 `<skill-dir>/scripts/build_html_report.py --plan ...`이 같은 기능이다.
생성기는 layout_version 2 계획의 `verify`를 수행한 뒤 같은 계획 폴더에 새 `report.html`을 만든다.
기존 보고서를 덮어쓰지 않는다. 구조 이미지는 계획의 확인된 가지별 Study, B/D/R
Sample, Experiment, Run 및 파일 역할의 개수를 인라인 SVG로 생성한다. 다른 저장소는
원본 매핑에 없는 Sample·Experiment·Run 관계를 표시하지 않는다. 보고서는 서버의
비공개 작업공간에 남기며, 외부 반출은 사용자 승인이 필요하다.

기존 로컬 수동 양식은 다음 명령을 사용한다:
`python <skill-dir>/scripts/build_html_report.py --data <private-report.json> --output <new-report.html>`

두 생성 방식은 Python 표준 라이브러리만 사용하며 별도 설치가 없다. 수동 JSON 필수 필드:
`title`, `source_path`, `destination_paths`, `structure_image`, `results`, `relationships`.
뒤의 세 문자열 목록 중 `destination_paths`, `results`, `relationships`는 비어 있으면 안 된다.
`structure_image`는 JSON 기준 상대 경로 또는 절대 경로의 PNG다.
`image_caption`, `image_alt`, `destination_label`은 선택이다. 실제 내용은 Git에서 제외된
`local_reports/<source-name>_report.html`에 저장한다. 자동 방식은 서버의 비공개 계획 폴더에
저장한다. 전체 매핑과 계획 해시 등 상세 기록은 기존 비공개 계획/로그에 둔다.

완성 후 HTML의 제목·경로·그림·본문 순서와 글자 인코딩을 확인한다.
서버에 브라우저가 없으면 화면·인쇄 미리보기를 완료했다고 주장하지 않는다.
사용자가 승인된 방법으로 파일을 가져온 뒤 브라우저에서 가독성과 인쇄 잘림을 확인한다.
PDF는 사용자가 원할 때 내보낸다.
