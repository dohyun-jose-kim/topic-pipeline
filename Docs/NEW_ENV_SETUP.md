# 신규 환경에서 90_CLI 돌리기

완전히 새 머신 또는 새 env 에서 `topic-pipeline` 을 처음 세팅하는 5 단계.

> 이 repo 본체는 `wk7trf_conda` env 를 재사용합니다 (README §설치 참고).
> 이 문서는 **그 env 를 못 쓰는 상황** — 새 머신, 다른 파이썬, CI, 동료 배포 — 을 위한 것.

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
cd /path/to/ifc_ojt_dh.kim/week_f/90_CLI
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
- **CUDA 없음**: embed 단계 (`sentence-transformers`) 는 CPU 로 5,000 건 기준 3~10 분. GPU 붙이려면 `torch` CUDA 빌드를 별도 설치해야 함 (`requirements.txt` 는 CPU 기준 가능성 큼 — 필요시 확인).
- **pyproject.toml 의존성 범위가 느슨함** (`>=` 만). (A) 로 깔면 몇 달 뒤 BERTopic 0.17 / sentence-transformers 3.x 가 들어와 깨질 수 있음. (B) 권장 이유.
