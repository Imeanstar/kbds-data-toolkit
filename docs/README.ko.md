# kbds-data-toolkit 한국어 사용 안내

[English guide and support matrix](../README.md)

파일 실행은 Linux에서만 지원합니다. Windows 시험은 순수 로직만 확인합니다.
HTML 보고서는 한국어와 영어를 지원합니다. PDF·HWP·Excel 내용 분석과 실제 등록은 지원하지 않습니다.
연습 파일 시험의 성공이 실데이터의 과학적 정확성이나 모든 저장장치의 호환성을 보장하지는 않습니다.

선택한 시퀀싱 데이터를 조사하고, 승인된 새 폴더에 복사하고, 결과를 검증하는 도구입니다.
원본 이름과 내용을 보존합니다. K-BDS 또는 GEO에 실제 제출하는 기능은 없습니다.

기본 에이전트는 읽기 전용 `kbds-review`입니다.
파일 정리는 사용자가 요청한 `kbds-stage`에서 수행합니다.
두 모드는 같은 로컬 Qwen 모델을 사용합니다.

## kbds-data-organizer guide

이 가이드는 **데이터가 있는 Linux 서버에서 Qwen과 OpenCode를 함께 실행**하는 경우입니다.
SSH를 쓰면 먼저 사용자가 서버에 로그인합니다. 이후 아래 명령은 서버 터미널에서 실행합니다.
모델만 설치하면 파일 작업은 할 수 없습니다. OpenCode가 모델과 파일 도구를 연결합니다.

### 1. 실행 환경 준비

다음 항목이 필요합니다.

- Linux와 Python 3.10 이상.
- Git, OpenCode, llama.cpp의 `llama-server`.
- 도구 호출을 지원하는 Qwen GGUF 모델과 호환되는 채팅 템플릿.
- 원본 읽기 권한. 실행 모드에는 새 출력 폴더와 작업공간을 만들 권한도 필요합니다.

모델과 실행 환경은 서버 관리자가 승인한 방법으로 설치합니다.
OpenCode 설치 방법은 [공식 설치 가이드](https://opencode.ai/docs/#install)를 참고하세요.
검증에 사용한 OpenCode 버전은 1.18.35입니다. 공식 설치 스크립트로 설치합니다.

```bash
task_installer=$(mktemp)
curl -fsSL https://opencode.ai/install -o "$task_installer"
bash "$task_installer" --version 1.18.35
export PATH="$HOME/.opencode/bin:$HOME/.local/bin:$PATH"
opencode --version
python3 --version
```

llama.cpp 설치와 모델 호환성은 [llama.cpp 공식 문서](https://github.com/ggml-org/llama.cpp)
및 [서버 문서](https://github.com/ggml-org/llama.cpp/tree/master/tools/server)를 참고하세요.
이 저장소는 모델 가중치, GPU 드라이버, Python 패키지를 설치하지 않습니다.

### 2. 로컬 Qwen 서버 실행

이미 준비한 GGUF 파일의 경로를 아래 예시에 넣습니다.
모델이 없으면 [공식 Qwen3.8-27B GGUF](https://huggingface.co/ggml-org/Qwen3.8-27B-GGUF)를 받을 수 있습니다.
이 예시는 고정된 모델 리비전과 Q4_K_M 파일을 사용합니다.

```bash
mkdir -p "$HOME/models/Qwen3.8-27B"
cd "$HOME/models/Qwen3.8-27B"
curl -fL --output Qwen3.8-27B-Q4_K_M.gguf \
  https://huggingface.co/ggml-org/Qwen3.8-27B-GGUF/resolve/71bc7b627595dc8a91039addd9c791ae548d6747/Qwen3.8-27B-Q4_K_M.gguf
printf '%s  %s\n' \
  c600de0300ae8a0eb3a6c0b8b5561b8b96f16bd2c863c2a66c42de29d391a747 \
  Qwen3.8-27B-Q4_K_M.gguf | sha256sum -c -
```

[llama.cpp b11429 빌드 안내](https://github.com/ggml-org/llama.cpp/blob/b11429/docs/build.md)에 따라 CPU 또는 CUDA 실행 파일을 준비합니다.
OpenCode와 llama-server는 같은 서버에서 실행합니다.
모델 서버는 별도 터미널에 유지합니다.

```bash
llama-server --model /approved/models/Qwen-27B.gguf --alias qwen3.8-27b --host 127.0.0.1 --port 8080 --ctx-size 16384 --parallel 1 --jinja --fit off --gpu-layers 24
```

`qwen3.8-27b`는 이 저장소의 API 모델 별칭입니다.
이 이름이 실제 모델 파일의 제품명이나 버전을 확인해 주지는 않습니다.
실제 GGUF와 채팅 템플릿은 설치한 모델에 맞아야 합니다.
서버의 도구 호출이 작동해야 OpenCode가 파일을 조사할 수 있습니다.

프로필은 입력 컨텍스트 16,384, 출력 한도 2,048로 설정되어 있습니다.
모델 서버도 해당 컨텍스트를 지원해야 합니다.
8,192로 실행하면 스킬과 참고 문서를 읽은 뒤 요청이 거부될 수 있습니다.
GPU 사용 옵션은 서버 장비에 맞게 설정합니다. 검증 서버는 RAM 64 GB, VRAM 11 GB입니다.
위 예시는 24개 레이어를 GPU에 두고 나머지 가중치를 RAM에 둡니다.
값을 줄이면 RAM 비중이 커집니다. `--gpu-layers 0`은 CPU에서 실행합니다.
모델 파일은 약 19 GB입니다. 현재 목록·텍스트 기록 작업에는 vision projector가 필요하지 않습니다.
모델 터미널에서 Ctrl+C를 누르면 서버가 종료됩니다.

다음 응답에서 모델 ID가 `qwen3.8-27b`인지 확인합니다.

```bash
curl http://127.0.0.1:8080/v1/models
```

다른 ID를 사용하면 `opencode.json`의 기본 provider 모델 키, `model`, `small_model`,
두 작업 에이전트의 `model`을 모두 같은 ID로 수정합니다. 요약 별칭의 `id`도 같은 서버 모델 ID로 맞춥니다.
`agent.compaction.model`은 출력 상한이 있는 별칭을 유지합니다. 이후 OpenCode를 다시 시작합니다.
다른 컴퓨터에서 실행하는 OpenCode의 `127.0.0.1`은 연구 서버를 가리키지 않습니다.

이 프로젝트는 Qwen 요청의 thinking과 thinking 보존을 끕니다.
컨텍스트가 차면 짧게 요약하고 최근 기록의 보존량을 제한합니다. 요약 모델도 같은 로컬 Qwen입니다.
`qwen3.8-27b-compact`는 같은 서버 모델 ID를 가리키는 설정 별칭입니다. 다른 모델을 설치하거나 호출하지 않습니다.
이 별칭은 요약 출력만 최대 1,024토큰으로 제한합니다. 일반 작업의 출력 한도는 2,048토큰입니다.
이 프로필은 16K 입력 한도에서 4K를 여유로 둡니다. 모델의 입력·출력 한도를 바꾸면 이 여유도 확인합니다.
문서는 같은 버전에서 한 번 읽습니다. 요약 후에는 읽은 문서와 다음 작업을 이어 갑니다.
스킬의 첫 문서는 핵심 규칙만 담고, 승인 범위 실행과 개별 계획 실행 중 필요한 지침만 읽습니다.
내부 요약은 짧은 영어로 경로·승인·예외·다음 작업을 보존하도록 지시합니다. 사용자 보고서는 한국어로 작성할 수 있습니다.
`inventory --summary`와 계획 출력의 `inventory_summary`에는 전체 빈 파일 수와 분류 후보별 집계가 있습니다.
후보별 예시는 최대 2개입니다. 예시는 생물학적 사실이나 포함 승인으로 사용하지 않습니다.
큰 기록은 필요한 구간만 읽습니다. 조사 후 확인이 필요하면 질문하고 답을 기다립니다.
설정 파일은 작업이 중지된 상태에서 바꿉니다. 설정은 프로젝트 캐시를 갱신해 적용할 수 있습니다.
플러그인 코드를 바꿨다면 OpenCode 프로세스를 다시 시작합니다. Bun의 모듈 캐시는 프로젝트 캐시와 다릅니다.
설정 갱신은 이미 커진 대화를 지우거나 완료되지 않은 작업을 완료하지 않습니다.
전체 보고서는 사용자가 경로에서 검토합니다.

프로젝트의 `.opencode/plugins/kbds-session-guard.js`는 OpenCode가 자동으로 읽습니다.
배포할 때 이 폴더도 포함합니다. 별도 npm 패키지는 필요하지 않습니다.
OpenCode 1.18.35에서 같은 사용자 요청 안의 변경 없는 참고 문서 구간 재읽기를 차단합니다.
새 구간, 변경된 문서, 사용자 설정과 원본 자료 읽기는 차단하지 않습니다.
검증된 묶음 작업과 보고서 완료 후에는 도구 재실행을 막습니다. 실제 새 사용자 요청이 오면
새 단계가 시작됩니다. 자동 요약의 이어가기 메시지는 새 요청으로 취급하지 않습니다.
완료 뒤 요약 한 번은 실행될 수 있지만, 이어가기 훅이 같은 작업을 다시 시작하지 못하게 합니다.
이 기능은 승인을 자동 부여하거나 서버 파일 권한을 제한하는 보안 경계가 아닙니다.
OpenCode 버전이 다르면 훅 호환성을 다시 확인해야 합니다.

`--pure` 또는 `OPENCODE_PURE=true`를 사용하지 않습니다. 이 모드는 프로젝트 플러그인을 끕니다.
`/config`에 플러그인 경로가 보여도 실제 훅은 실행되지 않을 수 있습니다.
기본 제공 provider 플러그인만 끄려면 아래 예시처럼 `OPENCODE_DISABLE_DEFAULT_PLUGINS=true`를 사용합니다.
복사를 승인하기 전에 로컬 OpenCode 기록에서 완료된 스킬·참고 문서 읽기에
`kbds_reference` 메타데이터가 있는지 확인합니다. 경로 목록만으로 로딩 성공을 판단하지 않습니다.

많은 파일이 있는 기존 KRA 연습 폴더는 승인한 `practice_rule`로 파일별 결정을 생성할 수 있습니다.
[naming-policy.md](../skills/kbds-data-organizer/references/naming-policy.md)의 조건과 형식을 확인합니다.
이 규칙은 원본 목록의 해시에 연결됩니다. 새 파일이나 모호한 경로를 자동으로 처리하지 않습니다.
복사 진행 출력은 약 20회로 제한합니다. 모든 파일의 복사 기록은 결과 폴더의 `metadata/events.jsonl`에 남습니다.

요약이 반복되면 새 작업 메시지를 계속 추가하지 않습니다. 진행 기록을 보존하고
가드 플러그인과 적용 버전을 확인합니다. 완료된 복사·보고서를 다시 실행하지 않습니다.
완료 전 중단이었다면 기존 계획과 실제 진행 상태를 확인한 뒤 필요한 단계만 재개합니다.
진행 중인 요약에 새 제한을 전달한 것만으로 적용을 가정하지 않습니다.
범위 내 복사·검증·보고서 자동 실행과, 초기 분류 준비 중의 운영자 개입을 구분해 기록합니다.

### 3. 스킬을 포함한 브랜치 받기

모델 서버를 유지한 상태에서 새 서버 터미널을 엽니다.
개인 작업 디렉터리에서 다음 명령을 실행합니다.

```bash
git clone --branch codex/opencode-read-only-qwen-20261010 --single-branch https://github.com/Imeanstar/kbds-data-toolkit.git
cd kbds-data-toolkit
```

스킬의 원본 위치는 `skills/kbds-data-organizer/SKILL.md`입니다.
`opencode.json`의 `skills.paths`가 `./skills`를 읽도록 설정되어 있습니다.
스킬을 다른 숨김 폴더에 다시 복사할 필요는 없습니다.

OpenCode 설정을 확인합니다.

```bash
opencode debug config
opencode debug agent kbds-review
opencode debug agent kbds-stage
opencode debug skill
```

로컬 provider, 모델 ID, 스킬 경로와 권한 규칙이 보이는지 확인하세요.
전역 설정이나 실행 시 덮어쓰기 설정이 있으면 실제 적용 결과를 확인해야 합니다.
`skills.paths`를 모르는 오래된 OpenCode는 호환되는 버전으로 준비합니다.
이 저장소에는 이미 `AGENTS.md`가 있으므로 `/init`으로 다시 만들 필요가 없습니다.

### 4. 파일 작업 기능 시험

실데이터를 사용하기 전에 저장소 루트에서 다음 명령을 실행합니다.

```bash
python3 -B scripts/kbds.py self-check
```

새 임시 디렉터리에 합성 0바이트 FASTQ 두 개를 만듭니다.
계획, 복사, 검증, HTML 보고서 생성을 시험한 뒤 합성 시험 폴더만 제거합니다.
연구 파일은 읽지 않습니다. 성공하면 다음 문장이 나옵니다.

```text
PASS: synthetic copy, verify, report; no research files accessed
```

실패하면 실데이터 정리를 시작하지 말고 오류를 확인합니다.
이 시험의 성공은 Python 파일 작업 기능을 확인합니다.
실제 원본과 출력 경로의 권한, Qwen의 판단 정확도까지 보증하지는 않습니다.

### 5. 읽기 전용 조사 시작

저장소 루트에서 실행합니다.

```bash
OPENCODE_DISABLE_DEFAULT_PLUGINS=true opencode --agent kbds-review --model qwen-local/qwen3.8-27b
```

예시 요청입니다. 경로는 사용자가 선택한 실제 경로로 바꿉니다.

> kbds-data-organizer 스킬을 읽어.
> /srv/example/raw/Example 폴더의 파일 목록과 내가 지정한 기존 기록을 조사해.
> 파일은 만들거나 바꾸지 말고, 확인한 사실과 모르는 관계를 대화에 보고해.

이 모드는 bash, 파일 쓰기와 native grep을 차단합니다.
grep 권한은 검색식을 기준으로 판단하므로 read의 비밀 파일 차단 규칙을 대신하지 못합니다.
실행 모드에서도 native grep은 차단합니다. OpenCode의 세션 기록은 데이터 밖에 저장됩니다.
결과는 대화에 표시합니다. 전체 목록이 도구 한도를 넘으면 부분 조사라고 표시합니다.
기존 `COMPLETE.json`만 읽고 현재 복사가 검증되었다고 보고하지 않습니다.
보고서에는 허용된 도구와 실제 호출한 도구를 구분합니다.

### 6. 파일 정리와 HTML 보고서 시작

저장소 루트에서 실행 모드를 엽니다.

```bash
OPENCODE_DISABLE_DEFAULT_PLUGINS=true opencode --agent kbds-stage --model qwen-local/qwen3.8-27b
```

예시 요청입니다.

> kbds-data-organizer 스킬을 사용해.
> 원본은 /srv/example/raw/Example이야.
> 새 출력은 /srv/example/raw/Example_makeup으로 해.
> 작업공간은 /srv/example/work/job-001이야.
> 실데이터이므로 production 모드를 사용해.
> B/D/R 의미, 실험 종류, bulk/single-cell, 저장소 경로가 불명확하면 질문해.
> 목록을 조사하고 구체적인 복사 계획을 제시해.
> 내가 그 계획의 SHA-256을 승인하면 복사하고 검증해.
> 같은 작업공간에 HTML 보고서까지 만들어.

실행 흐름은 다음과 같습니다.

1. Qwen이 경로와 모드를 확인합니다. 승인된 범위의 답만 기록합니다.
2. 두 비공개 설정 파일을 생성하거나 수정합니다. OpenCode가 변경 내용을 보여 주고 승인을 요청합니다.
3. 조사용 계획을 만듭니다. `inventory.tsv`와 `unresolved.tsv`를 읽고 모르는 항목을 질문합니다.
4. 답을 반영해 새 이름의 계획을 만듭니다. 파일별 매핑, 제외 항목, 용량과 SHA-256을 제시합니다.
5. 사용자가 **그 계획**을 승인하면 복사합니다. 계획 승인과 도구 실행 허용은 별개입니다.
6. 보고서 명령이 출력을 검증하고 새 `report.html`을 만듭니다.

복사를 승인할 때는 실제 제시된 SHA-256을 붙여 “이 계획 승인”이라고 답합니다.
에이전트 전환이나 이전 계획 승인은 새 계획의 승인이 아닙니다.
`--auto`와 모든 명령을 허용하는 승인은 사용하지 않습니다.
질문과 승인에 답한 뒤 같은 대화에서 작업을 이어갑니다.
출력이나 원본이 바뀌면 새 계획이 필요합니다.

### 6-A. 승인한 범위에서 자동 실행

매번 계획을 승인하지 않으려면 원본·출력·작업공간, 실행 모드와 분류 규칙을 한 번 승인합니다.
Qwen은 같은 범위의 새 계획을 자동 생성하고 복사·검증·HTML 보고서까지 진행합니다.
새 파일이 승인된 규칙과 맞으면 처리합니다. 미확정 파일, 짝 누락, 충돌, 기존 출력은 예외로 멈춥니다.
이 기능은 사용자가 시작하는 작업입니다. 폴더를 계속 감시하는 서비스는 설치하지 않습니다.

1. Qwen이 선택한 폴더를 조사하고 불명확한 분류만 질문합니다.
2. 사용자 답을 반영한 policy.local.json과 decisions.local.json을 운영자가 확인합니다.
3. 운영자는 [scope.example.json](../config/scope.example.json) 형식으로 비공개 scope.local.json을 저장합니다.
   합성 예시의 경로·분류를 실제 자료에 그대로 쓰면 안 됩니다. Qwen에는 이 파일의 편집 권한이 없습니다.
4. 다음 명령으로 범위와 분류를 확인합니다. 출력된 scope_sha256은 파일 바이트의 해시가 아닌 정규화된 정책 해시입니다.

```bash
python3 scripts/kbds.py run --scope /absolute/repo/config/scope.local.json --inspect
```

사용자의 실제 범위 승인을 기록한 뒤, Qwen에게 승인된 scope_sha256을 알려 주고 아래 작업을 지시합니다.

> kbds-data-organizer의 승인 범위 실행을 사용해.
> 승인 파일은 /absolute/repo/config/scope.local.json이고 범위 해시는 APPROVED_SCOPE_SHA256이야.
> 새 계획 이름은 job-001로 해. 명령 제한 시간은 연습 자료 기준 600000ms 이상으로 설정해.
> 승인 범위에 맞으면 계획·복사·검증·HTML 보고서를 끝까지 진행하고, 예외만 질문해.

Qwen이 실행하는 명령은 다음과 같습니다. OpenCode는 이 묶음 작업의 실행 권한을 한 번 확인합니다.

```bash
python3 scripts/kbds.py run --scope /absolute/repo/config/scope.local.json --approve-scope APPROVED_SCOPE_SHA256 --name job-001
```

계획 해시는 매번 새로 기록됩니다. 범위 해시는 경로·모드·분류 규칙이 같으면 유지됩니다.
경로나 규칙을 바꾸면 범위 승인을 갱신합니다. 기존 출력에는 덮어쓰거나 이어 쓰지 않습니다.
예외를 임의로 제외하거나 PAIRED를 SINGLE로 바꾸어 통과시키지 않습니다.
자세한 규칙 형식과 중단 조건은 [scoped-execution.md](../skills/kbds-data-organizer/references/scoped-execution.md)에 있습니다.

### 7. 설정 파일과 분류 규칙

Qwen은 네이티브 편집 도구로 다음 두 파일만 수정할 수 있습니다.
두 파일은 Git에서 제외됩니다.

- `config/policy.local.json`: 범위, 모드, 저장소와 출력 정책.
- `config/decisions.local.json`: 각 파일의 포함·제외 결정과 확인 근거.

`config/*.example.json`은 합성 예시입니다. 실제 사실로 사용하지 않습니다.
실데이터 정책의 예시는 다음과 같습니다. 모든 경로를 승인된 경로로 바꿔야 합니다.

```json
{
  "version": 1,
  "layout_version": 2,
  "repository_scope": "KRA",
  "mode": "production",
  "source_root": "/srv/example/raw/Example",
  "destination_root": "/srv/example/raw/Example_makeup",
  "workspace_root": "/srv/example/work/job-001",
  "allow_practice_zero_bytes": false,
  "reserve_bytes": 104857600
}
```

원본은 존재해야 합니다. 출력은 원본의 형제 폴더이며 아직 존재하지 않아야 합니다.
원본, 출력, 작업공간은 서로 포함하지 않습니다. 출력과 작업공간의 부모 경로는 존재해야 합니다.
심볼릭 링크가 있으면 확인된 실제 경로를 사용합니다. 기존 출력에 병합하지 않습니다.

0바이트 연습 파일만 쓸 때는 `mode`를 `practice`,
`allow_practice_zero_bytes`를 `true`로 함께 설정합니다.
실제 데이터가 검증에 실패했다고 연습 모드로 바꾸면 안 됩니다.
이번 연습의 가정은 해당 결정 기록과 보고서에만 남깁니다.

새 KRA 출력은 다음 구조를 사용합니다.

```text
Example_makeup/
  Example_makeup_bulk/
    Study01/
      B/ID001/Library_B/Run_B/
        R1/original-B_1.fastq.gz
        R2/original-B_2.fastq.gz
      D/ID001/Library_D/Run_D/
        R1/original-D_1.fastq.gz
        R2/original-D_2.fastq.gz
      R/ID001/Library_R/Run_R/
        R1/original-R_1.fastq.gz
        R2/original-R_2.fastq.gz
  Example_makeup_single_cell/<확인된 Study/Sample/Experiment/Run 구조>
  metadata/
```

실제로 포함되는 bulk/single_cell 폴더만 생성합니다.
B/D/R은 각각 Sample 가지입니다. R1/R2는 파일 역할입니다.
B/D/R 의미와 검체·라이브러리 관계는 데이터마다 확인합니다. WES를 WGS로 바꾸지 않습니다.

FASTQ는 KRA 후보입니다. BAM은 원본·처리 이력과 실험 근거가 필요합니다.
확인된 기능유전체 처리 자료는 KEA로 분류할 수 있습니다. 정확한 이름은 KEA입니다.
발현 행렬은 이 워크플로의 GEO 후보입니다.
barcodes, matrix, features/genes 묶음은 single-cell 후보이며 FASTQ와의 연결도 확인합니다.
이름이나 확장자만으로 확정하지 않습니다.

여러 저장소에 나누는 경우 확인된 경로별로 `Example_KRA_makeup`,
`Example_KEA_makeup`, `Example_GEO_makeup`을 만듭니다.
각 출력에는 별도 정책과 계획이 필요합니다.
모든 원본 파일이 어느 계획에 포함되거나 명시적으로 제외되었는지 확인합니다.

### 8. HTML 보고서 확인과 PDF 저장

새 보고서는 승인된 계획 폴더의 `report.html`입니다.
예: `/srv/example/work/job-001/reviewed-001/report.html`.

기본 언어는 한국어입니다. `run` 또는 `report` 명령의 **마지막 옵션**에 `--language en`을
붙이면 생성 문장·화면·구조 그림의 표기를 영어로 만듭니다. `--language ko`는 한국어입니다.
근거 원문, 식별자, 경로와 수동 보고서의 입력 본문은 번역하지 않습니다.
언어 선택은 계획·범위 해시와 복사한 데이터에 영향을 주지 않습니다.
기존 `report.html`은 다른 언어를 선택해도 덮어쓰지 않으므로 생성 전에 언어를 정합니다.

```bash
python3 scripts/kbds.py report --plan /srv/example/work/job-001/reviewed-001/plan.json --language en
```

보고서에는 제목, 우측 정렬 원본·출력 경로, 구조 그림, 조사 결과,
확인된 구조 관계와 근거가 들어갑니다.
구조 그림에는 Study, B/D/R Sample ID·검체, Experiment, Run과 파일 역할의 개수가 표시됩니다.
외부 CSS, 이미지, 글꼴을 불러오지 않습니다. 기존 보고서는 덮어쓰지 않습니다.

승인된 방법으로 HTML 파일 하나를 PC로 가져와 브라우저에서 엽니다.
보고서의 “PDF로 저장 / 인쇄” 버튼에서 PDF로 저장할 수 있습니다.
머리 없는 서버에서는 화면이나 인쇄 미리보기를 검사했다고 보고하지 않습니다.

보고서 기능을 직접 실행하려면 저장소 루트에서 다음 명령을 사용합니다.

```bash
python3 scripts/kbds.py report --plan /srv/example/work/job-001/reviewed-001/plan.json
```

이 명령은 layout_version 2의 완료된 출력만 보고합니다.
현재 크기·체크섬, 계획·TSV의 내용, 복사 이벤트와 완료 표시의 모든 필드를 검증한 뒤 HTML을 만듭니다.
보고서가 필요 없으면 `scripts/kbds.py --policy ... verify --plan ...`로 검증합니다.

### 9. 실패 처리와 검증 범위

`WAITING_FOR_USER` 또는 종료 코드 2는 질문·오류 해결이 필요하다는 뜻입니다.
원본 변경, 누락된 짝, 접근 오류, 경로 충돌과 기존 출력은 실행을 막습니다.
복사 중 실패하면 부분 출력과 로그를 보존합니다. 자동 삭제·덮어쓰기·재시작은 하지 않습니다.
OpenCode의 `apply` 호출에는 bash 도구의 `timeout`을 명시합니다. 연습 복사는 최소
`600000`밀리초(10분)를 쓰고, 예상 작업이 더 길면 늘립니다. 검증·보고서 시간도 확보합니다.
기본값 `120000`밀리초(2분)는 느린 저장소에서 정상 복사를 중단할 수 있습니다.
시간 초과는 완료가 아닙니다. 부분 출력에 `apply`를 다시 실행하지 않습니다.
부분 출력은 보존하고, 새 출력 경로의 계획을 만든 뒤 그 계획 해시를 다시 승인받습니다.

연습 모드는 경로, 0바이트 크기와 짝 이름 문법을 검사합니다.
실데이터 모드는 SHA-256과 지원하는 4줄 KRA FASTQ/gzip 및 read pair를 검사합니다.
다른 저장소 파일은 바이트 무결성만 검사하고 `sha256_only`로 기록합니다.
별도 `verify`는 FASTQ를 다시 파싱하지 않습니다. 실제 호출의 검사와 패키지 완료 기록을 구분해 출력합니다.
잘못된 완료 표시나 변경된 TSV는 검증에 실패합니다. 검증이 기존 출력을 자동 수정하지는 않습니다.
KRA BAM/CRAM, 과학적 행렬 검증, PDF·HWP·Excel 내용 해석과 공식 제출 메타데이터는 구현되어 있지 않습니다.
모든 계획은 `submission_ready=false`입니다.

짝 파일의 끝부분은 `_R1/_R2`, `-R1/-R2`, `.R1/.R2`와 숫자 `_1/_2` 등의 구분자를 지원합니다.
파일명 중간의 숫자나 R 표시는 생물학적 관계로 해석하지 않습니다. lane/chunk가 여러 개면
승인된 Run 매핑을 분리합니다. 파일 합치기나 자동 이름 변경은 하지 않습니다.
출력 경로의 각 단계에서 대소문자·Unicode 표기 충돌과 파일/폴더 충돌을 검사합니다.
Windows 예약 이름, 경로 특수문자, 끝 공백·마침표, 255 UTF-8 바이트를 넘는 구성요소는
복사 전에 중단 사유가 됩니다. 원본 이름은 그대로 보존합니다.

새 계획은 `report_format_version: 2`를 사용합니다. TSV에서 수식으로 실행될 수 있는 문자열은
앞에 작은따옴표를 붙입니다. 정확한 원본 문자열은 `plan.json`에 있습니다.
자동 프로그램이 파일 경로를 읽을 때는 TSV의 표시값 대신 이 JSON을 사용합니다.

승인 범위 `run`의 `timings_seconds`는 범위 검사, 계획, 사전 검사, 복사·메타데이터,
검증, 보고서 검증·생성 시간을 측정합니다. Qwen 생성 시간과 OpenCode 승인 대기는 포함하지 않습니다.
전체 소요 시간은 세션 기록에서 별도로 계산합니다. 파일 수정 시각으로 단계별 시간을 확정하지 않습니다.

OpenCode 권한과 Python 검사는 서버 계정의 OS 권한을 대신하지 않습니다.
실제 실행 권한이 부족하면 서버 데이터 소유자와 해결합니다.
자세한 범위는 [docs/SAFETY.md](SAFETY.md)를 참고하세요.

## 테스트와 코드 위치

```bash
python3 -B -m unittest discover -s tests -v
python3 -B scripts/kbds.py self-check
```

테스트는 합성 파일만 사용합니다. 연구 서버나 모델 서비스에 접속하지 않습니다.
Linux에서는 실제 임시 파일 복사 테스트를 실행합니다.
Windows에서는 Linux 전용 테스트를 건너뛰고 분류·구조·보고서·프로필 테스트를 실행합니다.
GitHub Actions는 Linux의 Python 3.10·3.14에서 전체 시험을 실행합니다. Windows의 Python 3.14에서는 지원되는 순수 로직 시험만 실행합니다.

- `AGENTS.md`: 데이터 작업 규칙.
- `opencode.json`: Qwen 모델, 스킬 검색 경로와 두 에이전트의 권한.
- `skills/kbds-data-organizer/`: 스킬, 분류 규칙, 실행 엔진과 보고서 생성기.
- `scripts/kbds.py`: 저장소 루트의 공통 실행 명령.
- `scripts/remote_stage.py`: 별도 off-host 에이전트용 SSH 브리지.
  서버 Qwen에는 필요하지 않으며 번들 OpenCode 프로필에서는 허용하지 않습니다.

독립 스킬을 다른 에이전트에 넣으면 스킬 폴더의 `scripts/toolkit.py`,
`scripts/self_check.py`, `scripts/build_html_report.py`를 사용할 수 있습니다.
Qwen에서 자동으로 스킬을 찾지 못하면 SKILL.md 경로를 명시적으로 읽게 합니다.
에이전트에 읽기·명령 실행 도구가 있어야 합니다.

## 참고 문서

- [신뢰성 개선 내역과 검증 범위](reliability-review.md): 확인한 문제, 수정 내용과 남은 한계.

- [OpenCode 설정](https://opencode.ai/docs/config/), [권한](https://opencode.ai/docs/permissions/), [스킬](https://opencode.ai/docs/skills/)
- [llama.cpp 서버](https://github.com/ggml-org/llama.cpp/tree/master/tools/server)
- [K-BDS 제출 안내](https://kbds.re.kr/submission/navigation)
- [GEO 시퀀싱 제출](https://www.ncbi.nlm.nih.gov/geo/info/seq.html)
