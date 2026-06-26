# 신규 환경에서 topic-pipeline 돌리기

완전히 새 머신 또는 새 env 에서 `topic-pipeline` 을 처음 세팅하는 5 단계.

> 깨끗한 환경(새 머신·다른 파이썬·CI·동료 배포)에서 `pip install -e .` 로 세팅한다.

---

## ① Python 준비 — 3.11 이상

`pyproject.toml` 이 `requires-python = ">=3.11"` 로 고정. 아래 중 하나:

```bash
# (a) pyenv
pyenv install 3.12.7 && pyenv local 3.12.7

# (b) Homebrew
brew install python@3.12

# (c) conda / miniconda
conda create -n tp python=3.12 -y && conda activate tp
```

---

## ② venv 생성 (conda 쓰면 건너뛰기)

```bash
cd <repo>          # 예: 01_Topic_Modeling_ver3.0.1
python3.12 -m venv .venv
source .venv/bin/activate
```

---

## ③ 패키지 설치 — 두 갈래

```bash
# (A) 일반 설치 — pyproject.toml 의 dependencies 가 자동 해결되어 latest-compatible 로 깔림
pip install -e .

# (B) 재현 가능한 lock 버전 — 원본 개발 환경과 동일 버전 고정 (권장)
pip install -r requirements.txt
pip install -e . --no-deps
```

**(B) 권장 이유**: BERTopic / sentence-transformers / umap-learn / scipy 는 버전 변동이 잦아서 latest 로 깔면 미묘하게 동작이 달라질 수 있음. lock 버전으로 시작해 재현성 확보 후, 필요시 업그레이드.

설치 시간 5–15 분 (torch, transformers, bertopic 이 무거움).

---

## ④ API 키 환경변수

```bash
export ANTHROPIC_API_KEY="sk-ant-..."    # 필수 — s5 label + label-relevance
export NCBI_API_KEY="..."                # 권장 — s1 fetch 10 req/s (없으면 3 req/s)
export NCBI_EMAIL="you@example.com"      # 선택 — NCBI 예의
```

`.env` 자동 로더는 없음 (현재 CLI 는 `os.environ` 직독). shell export 로 주입해야 함.

---

## ⑤ 검증 + 첫 실행

```bash
# activate 된 상태라면 엔트리포인트 직접 호출 가능
topic-pipeline --help

# 또는 -m 방식
python -m topic_pipeline.cli --help

# 동작 확인용 smoke test — 샘플 데이터 + fetch 단계만
topic-pipeline --input-pmid DATA/sleep_quality-9999.csv fetch
# → outputs/s1_meta.csv 생성되면 OK
```

---

## 주의사항

- **Apple Silicon (M1~M4)**: 대부분 arm64 whl 제공. `scipy`, `numba` (umap-learn 의존) 도 py3.12 부터는 문제 없음. py3.11 에선 간혹 build-from-source 로 빠지기도.
- **CUDA/GPU**: embed 단계 (`sentence-transformers`) 는 CPU 로 5,000 건 기준 3~10 분. GPU 사용 시 `pip install -e .[gpu]` (또는 플랫폼에 맞는 `torch` 빌드) 로 가속.
- **의존성 범위**: pyproject 는 floor+major-cap (`>=x,<x+1`) 로 고정되어 latest 자동설치 breakage 위험이 줄었음. 정확한 재현은 여전히 (B) `requirements.txt` 핀 권장.
