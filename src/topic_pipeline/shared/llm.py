"""Claude API 호출 단일 진입점 (M3 LLM-1).

s5_label / s5_label_relevance 에 byte-identical 로 중복돼 있던 _call_claude 를 통합.
원본 대비 추가: 일시적 오류(rate-limit / 네트워크 / 5xx)에 지수 backoff 재시도.

시크릿: anthropic SDK 가 ANTHROPIC_API_KEY 환경변수를 자동 로드 (config/코드 보관 금지).
실 API 호출이라 모듈 _smoke_test 는 두지 않음 — 단위 테스트는 client mock (tests/test_llm.py).
"""

from __future__ import annotations

import os
import time

DEFAULT_MAX_TOKENS = 8192


def call_claude(
    prompt: str,
    model: str,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    max_retries: int = 3,
    backoff: float = 2.0,
) -> str:
    """단일 user 메시지로 Claude 호출 → 첫 text 블록 반환.

    성공 경로는 원본과 동일(model/max_tokens/messages, response.content[0].text).
    일시적 오류(Connection/RateLimit/5xx)는 지수 backoff 로 max_retries 까지 재시도, 소진 시 RuntimeError.
    """
    import anthropic

    client = anthropic.Anthropic()
    print(f"[LLM] 모델: {model}")
    print("[LLM] 요청 중...")

    transient = (
        anthropic.APIConnectionError,   # 네트워크/타임아웃 (APITimeoutError 포함)
        anthropic.RateLimitError,       # 429
        anthropic.InternalServerError,  # 5xx
    )
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except transient as e:
            last_exc = e
            wait = backoff * (2 ** attempt)
            print(f"  [LLM retry {attempt + 1}/{max_retries}] {type(e).__name__}: {e} — {wait}s 대기")
            time.sleep(wait)
    raise RuntimeError(f"Claude 호출 {max_retries}회 재시도 소진: {last_exc}")


def call_local(
    prompt: str,
    model: str,
    *,
    base_url: str = "http://localhost:11434/v1",
    max_tokens: int = DEFAULT_MAX_TOKENS,
    max_retries: int = 3,
    backoff: float = 2.0,
) -> str:
    """OpenAI 호환 로컬 LLM 엔드포인트(Ollama/LM Studio/llama.cpp) chat/completions 호출.

    base_url 예: http://localhost:11434/v1 (Ollama), http://localhost:1234/v1 (LM Studio).
    로컬이라 보통 키 불필요 — 환경변수 LOCAL_LLM_API_KEY 가 있으면 Bearer 헤더로 전달.
    """
    import requests

    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    key = os.environ.get("LOCAL_LLM_API_KEY")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "stream": False,
    }
    print(f"[LLM] local: {url} (model={model})")

    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=300)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except requests.RequestException as e:
            last_exc = e
            wait = backoff * (2 ** attempt)
            print(f"  [LLM local retry {attempt + 1}/{max_retries}] {e} — {wait}s 대기")
            time.sleep(wait)
    raise RuntimeError(f"local LLM 호출 {max_retries}회 재시도 소진: {last_exc}")


def generate(prompt: str, cfg: dict) -> str:
    """label.provider 에 따라 LLM 호출 디스패치.

    'claude'(기본): anthropic API | 'local': OpenAI 호환 엔드포인트(label.base_url).
    'keywords' 는 LLM 을 쓰지 않으므로 step 에서 직접 처리(여기 도달 시 에러).
    """
    label = cfg.get("label", {}) or {}
    provider = label.get("provider", "claude")
    model = label.get("model", "")
    if provider == "claude":
        return call_claude(prompt, model)
    if provider == "local":
        return call_local(prompt, model, base_url=label.get("base_url", "http://localhost:11434/v1"))
    raise ValueError(
        f"label.provider={provider!r} 미지원 (claude|local|keywords). "
        "keywords 는 LLM 없이 step 에서 처리됩니다."
    )
