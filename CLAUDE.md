# CLAUDE.md — Topic Modeling ver3.0.1 작업 정책

이 리포에서 작업할 때의 규칙. 전역 `~/.claude/CLAUDE.md` 위에 프로젝트 규칙을 더한다.
설계 전반은 [`PLAN-v2.md`](./PLAN-v2.md), 사용법은 [`README.md`](./README.md).

> **ver3.0.1** = v2 CLI(`topic-pipeline`)를 정제 복사한 베이스라인.
> 방향: 토픽모델링 완성도↑ · 범용 tool화 · 다양한 주제(corpus) 대응 · 결과 표현 유연화.
> 미해결 이슈·개선 후보는 [`Docs/KNOWN_LIMITATIONS.md`](./Docs/KNOWN_LIMITATIONS.md), [`Docs/NEXT_PLAN.md`](./Docs/NEXT_PLAN.md).

## 0. 가드레일 (불변, 최우선)

- **시크릿은 환경변수만.** `ANTHROPIC_API_KEY`(s5 필수), `NCBI_API_KEY`·`NCBI_EMAIL`(s1 선택)은
  **config·코드·로그·HTML 리포트에 절대 기입·커밋 금지.** `default_config.yaml`의 `ncbi_*`는 빈 문자열
  placeholder로 유지(비면 env 참조). 해결 패턴 = "config 값이 있으면 그것, 없으면 env".
- **코드 중심 리포.** 대용량·재현가능 산출물은 추적 금지(`.gitignore`): `outputs/`, `*.npy`·`*.tar.xz`·`*.pptx`,
  `DATA/예시데이터/`. 소형 입력 PMID CSV와 코드·문서만 커밋.
- **불변 계약 — 깨지면 다운스트림이 조용히 붕괴하므로 리팩터 시 반드시 보존:**
  - 한국어 config 키: `project.주제`, `project['데이터 출처']`.
  - `s5_label-relevance.md`의 마크다운 표 포맷, 특히 **Topic 컬럼 = 정수만.** s6/s7이 3곳에서 regex로
    재파싱하므로 `Topic 5` 같은 LLM 포맷 드리프트는 정렬·색상을 침묵 속에 깬다.
  - 산출물 `sN_` 파일명 규약 — 단계 간 유일한 통신 수단(file-based IPC).
- **조용한 누락 금지.** 행 drop(빈 abstract), outlier(-1) 처리, sweep 탈락 등은 반드시 로그로 명시한다.
- 공개 repo (코드 MIT, 학습·포트폴리오). **실제 데이터·시크릿·사내 자료는 절대 커밋 금지.**

## 1. 문서 운영 (계획 먼저, 코드 나중)

| 파일 | 역할 | 갱신 시점 |
|---|---|---|
| `README.md` | 외부 시점 요약(설치·사용·9 step·출력) | 스택/구조 변화 시 |
| `CLAUDE.md` (이 파일) | 작업 정책 | 규칙이 바뀌면 **여기 먼저** |
| `PLAN-v2.md` | 마스터 설계(결정표·CLI·config·리포트·Phase 순서 등 15절) | 설계 결정이 바뀔 때 |
| `PLAN-v2-trend.md` | s6 키워드 트렌드 분석 서브 설계 | 트렌드 로직 변경 시 |
| `TODO.md` | Phase 진행 로그(완료·commit hash) | Phase 완료마다 |
| `Docs/KNOWN_LIMITATIONS.md` | 런타임 발견 이슈 추적(append-only) | 발견·해결마다 |
| `Docs/NEXT_PLAN.md`·`REVISED_PLAN.md`·`v2_pilot_*.md` | v3 방향·결정 로그 | 수시 |
| `Docs/NEW_ENV_SETUP.md` | 새 환경/CI 세팅 절차 | 의존성·설치 변화 시 |
| `depricated/` *(오타가 실제 폴더명)* | v1 설계·config 보존(참고용) | 손대지 않음 |

**순서: 계획을 먼저 문서화 → 그 다음 구현.** 코드가 문서를 앞서지 않는다.
`KNOWN_LIMITATIONS.md`는 append-only — 해결 시 `## ✅ 해결됨` 표시, 취소된 계획 항목은 삭제하지 말고
표시만 남긴다(provenance 보존).

## 2. 작업 단위(Phase/이슈) 주도

실작업은 작업 단위로 끊어서:

1. **단위 선언** — 작업 1개 = 목표 + 검증 기준(완료 조건)을 먼저 적는다(`TODO.md`/`Docs/` 노트 또는 이슈).
2. **커밋** — 작업하며 커밋, 메시지에 작업 단위를 참조한다.
3. **검증 후 완료** — 검증 기준 충족을 확인하고 `TODO.md` 진행 로그에 결과 + commit hash를 남긴다.

기존 규율: **한 Phase = 한 클린 커밋, 단계 건너뛰지 않기, 진행 전 기준 검증.**
remote(GitHub) 연결 시 작업 단위를 이슈로 승격하고 `Closes #N` 규약을 더한다.
정책·문서 부트스트랩(이 CLAUDE.md 등)은 이 규칙의 예외다.

## 3. 디렉터리 컨벤션

```
src/topic_pipeline/        # src-layout 패키지 (console-script: topic-pipeline)
  cli.py                   # argparse 디스패처 — STEPS(순서), STEP_MODULES(name→module)
  steps/sN_<verb>.py       # 단계별 단일 진입점  def run(cfg: dict) -> None
  shared/                  # 공통 유틸: pubmed · convention · colors · relevance · fonts · html_common
DATA/                      # 입력 PMID CSV + fetch_pmids.py  (예시데이터/는 비추적)
Docs/                      # 설계·결정·한계 기록 + diagram/(*.drawio)
depricated/                # v1 보존 (참고용)
default_config.yaml  pyproject.toml  requirements.txt  README.md  PLAN-v2*.md  TODO.md
outputs/                   # 런타임 산출물 (비추적; 단계 간 sN_ 파일로만 통신)
```

- **단계 = `sN_` 접두사** (파일·산출물 모두). CLI step 이름은 접두사 제거(`fetch`, `embed`, … `report`).
  s5는 모듈 2개(`s5_label`, `s5_label_relevance`)가 `s5_` 산출물 접두사를 공유한다.
- 그림은 `sN_figures/` 하위. 새 단계 추가 시 `cli.py`의 `STEPS`/`STEP_MODULES`에 등록(미구현은 값 `None`).

## 4. 커밋 규칙

- 한 커밋 = 한 논리 변경. **버그픽스 / 리팩터 / 새 기능 / 문서는 섞지 말고 쪼개서 커밋**한다.
- 커밋 메시지 끝에 `Co-Authored-By: Claude ...` 라인.
- 초기엔 `main`에 직접. 협업/리뷰가 필요해지면 그때 브랜치를 도입한다.
- Phase 완료 커밋은 `TODO.md` 로그에 hash를 남긴다.

## 5. 코드 컨벤션 (작업 시 준수)

- **step 계약:** 모든 step은 `def run(cfg: dict) -> None` 하나만 노출. 단계 간 통신은 `output_dir`의
  `sN_` 파일뿐 — 교차 경로/머지는 `shared/convention.py`를 통한다(하드코딩 금지). `cli.py`에 step별 특수처리 없음.
- **config 레이어링:** `default_config.yaml`(섹션 네임스페이스) → `_apply_overrides`가 CLI 플래그를
  `cfg.setdefault` 패턴으로 덮어씀(값이 `None`이 아닐 때만) → 병합된 `cfg` dict만 step에 전달.
  step은 `cfg.get(section, {}).get(key, default)`로 방어적으로 읽는다.
- **무거운 의존성은 지연 import** (torch·bertopic·umap·sklearn은 `run()`/헬퍼 내부에서). shared 모듈은
  `from __future__ import annotations` + PEP604 제네릭(`X | None`) + `_smoke_test()` 관례를 따른다.
- **로깅:** cli는 loguru(파일 DEBUG + stderr INFO, `=== step: X start/done ===`). step 내부 진행 표시는
  `[sN]` 태그 `print()`. CSV는 `utf-8-sig`(엑셀 한글) + `index=False`. 실패가 부분 산출물을 남기지 않도록
  `.tmp`→move 원자적 쓰기.
- **중복 주의(건드리면 통합):** `_call_claude`(s5_label·s5_label_relevance), 색상 맵(s6·s7),
  기본 embed 모델 문자열(s2·s4), 버전 문자열(`__init__.py`·`pyproject.toml`).
- **언어:** 주석·docstring·로그·LLM 프롬프트·리포트 본문은 한국어, 코드 식별자·축 라벨은 영어(혼용 규약 유지).
