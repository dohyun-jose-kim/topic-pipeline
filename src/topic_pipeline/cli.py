"""topic-pipeline CLI entry point.

Phase 6 부터 loguru 로깅 + step 실패 처리 + step 타이밍 추가 (PLAN §15-3, §15-4).
"""

from __future__ import annotations

import argparse
import copy
import importlib
import posixpath
import sys
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

import yaml
from loguru import logger

STEPS = ["fetch", "preprocess", "embed", "cluster", "enrich", "label", "label-relevance", "timeseries", "report"]

STEP_MODULES: dict[str, str | None] = {
    "fetch": "topic_pipeline.steps.s1_fetch",            # Phase 4
    "preprocess": "topic_pipeline.steps.s0_preprocess",  # M6 T1-2 (기본 off)
    "embed": "topic_pipeline.steps.s2_embed",            # Phase 5a
    "cluster": "topic_pipeline.steps.s3_cluster",        # Phase 5b
    "enrich": "topic_pipeline.steps.s4_enrich",          # Phase 3a
    "label": "topic_pipeline.steps.s5_label",            # Phase 3b
    "label-relevance": "topic_pipeline.steps.s5_label_relevance",  # NEXT_PLAN §C
    "timeseries": "topic_pipeline.steps.s6_timeseries",  # Phase 3c
    "report": "topic_pipeline.steps.s7_report",          # Phase 3d
}

# step 별 선행 산출물(output_dir 내) — 사전 검증용 (T2-8). fetch 는 input CSV 를 별도 확인.
STEP_REQUIRES: dict[str, list[str]] = {
    "fetch": [],
    "preprocess": ["s1_meta.csv"],
    "embed": ["s1_meta.csv"],
    "cluster": ["s2_embeddings.npy", "s2_meta_for_embed.csv"],
    "enrich": ["s3_selected_model.txt", "s3_labels.csv", "s2_meta_for_embed.csv"],
    "label": ["s4_keywords_comparison.csv"],
    "label-relevance": ["s5_labels.csv"],
    "timeseries": ["s5_labels.csv", "s5_label-relevance.md", "s2_meta_for_embed.csv", "s3_labels.csv"],
    "report": ["s2_embeddings.npy", "s5_labels.csv", "s5_label-relevance.md",
               "s2_meta_for_embed.csv", "s3_labels.csv", "s4_keywords_comparison.csv"],
}

# step 별 주요 산출물 — "같은 run 의 앞 step 이 생성" 판정용.
STEP_PRODUCES: dict[str, list[str]] = {
    "fetch": ["s1_meta.csv"],
    "preprocess": ["s0_meta_clean.csv"],
    "embed": ["s2_embeddings.npy", "s2_meta_for_embed.csv"],
    "cluster": ["s3_labels.csv", "s3_selected_model.txt", "s3_metrics.csv"],
    "enrich": ["s4_keywords_comparison.csv"],
    "label": ["s5_labels.csv"],
    "label-relevance": ["s5_label-relevance.md"],
    "timeseries": ["s6_topics_over_time.csv"],
    "report": ["s7_report.html"],
}


_DEFAULT_CONFIG_NAME = "default_config.yaml"


def _load_default_cfg_for_help() -> dict:
    """help 표시용으로 default_config.yaml 을 best-effort 로 읽음. 실패 시 {}."""
    try:
        p = Path(_DEFAULT_CONFIG_NAME)
        if p.is_file():
            with p.open(encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    except Exception:
        pass
    return {}


def _cfg_def(cfg: dict, *keys: str, fallback: str = "<config>", max_len: int = 60) -> str:
    """중첩 dict 에서 값 꺼내 help 용 display string. 긴 값은 잘라서 표시."""
    d = cfg
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return fallback
        d = d[k]
    if d is None:
        return "null (자동 합성)"
    s = str(d)
    if len(s) > max_len:
        s = s[: max_len - 3] + "..."
    return s


def build_parser() -> argparse.ArgumentParser:
    cfg = _load_default_cfg_for_help()

    parser = argparse.ArgumentParser(
        prog="topic-pipeline",
        description="토픽 모델링 파이프라인 (PMID → 임베딩 → 클러스터 → 라벨 → 리포트)",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "steps",
        nargs="*",
        choices=STEPS,
        metavar="STEP",
        help=f"실행할 step(s). 비우면 전체. 선택: {', '.join(STEPS)}",
    )
    parser.add_argument(
        "--config",
        default=_DEFAULT_CONFIG_NAME,
        help=f"config YAML 경로 (default: ./{_DEFAULT_CONFIG_NAME})",
    )
    parser.add_argument(
        "--run-id", metavar="NAME",
        help="[paths.run_id] 산출물을 output_dir/<NAME>/ 로 격리\n"
             "(default: 없음 → output_dir 직접; 'auto'=타임스탬프 run_YYYYmmdd_HHMMSS)",
    )
    parser.add_argument(
        "--list-steps", action="store_true",
        help="step 목록 + 모듈 + 필요/생성 산출물 출력 후 종료",
    )
    parser.add_argument(
        "--from", dest="from_step", choices=STEPS, metavar="STEP",
        help="이 step 부터 끝(또는 --to)까지 실행 (positional STEP 미지정 시)",
    )
    parser.add_argument(
        "--to", dest="to_step", choices=STEPS, metavar="STEP",
        help="처음(또는 --from)부터 이 step 까지 실행",
    )
    parser.add_argument(
        "--init", metavar="NAME",
        help="<NAME>.yaml config 를 프리셋으로 스캐폴딩 후 종료 (--preset 으로 도메인 선택)",
    )
    parser.add_argument(
        "--preset", metavar="P",
        help="--init 프리셋 (biomedical | general; 기본 general=무키·CSV)",
    )
    parser.add_argument(
        "--serve", action="store_true",
        help="output_dir 를 정적 서빙(127.0.0.1, logs/ 차단) — s7_report.html / s7_results.json",
    )
    parser.add_argument(
        "--port", type=int, default=8000, metavar="N",
        help="--serve 포트 (default 8000)",
    )

    # ── domain (도메인 바꿀 때) ─────────────────────────
    g_dom = parser.add_argument_group("domain")
    g_dom.add_argument(
        "--input-pmid", metavar="FILE",
        help=f"[paths.input_pmid_csv] 도메인 CSV 교체\n(default: {_cfg_def(cfg, 'paths', 'input_pmid_csv')})",
    )
    g_dom.add_argument(
        "--project-theme", metavar="TEXT",
        help=f"[project.주제] 리포트 헤드라인\n(default: {_cfg_def(cfg, 'project', '주제')}"
             " — null 이면 런타임 자동: '<input_pmid stem> 의 <relevance_criterion> 관련 연구 동향')",
    )
    g_dom.add_argument(
        "--project-source", metavar="TEXT",
        help=f"[project.데이터 출처] 리포트 meta\n(default: {_cfg_def(cfg, 'project', '데이터 출처')}"
             " — null 이면 런타임 자동: 'PubMed (<s1_meta year min>~<max>)')",
    )

    # ── cluster ──────────────────────────────────────────
    g_clu = parser.add_argument_group("cluster")
    g_clu.add_argument(
        "--umap-dim", type=int, metavar="N",
        help=f"[cluster.umap_n_components] UMAP 투영 차원 (default: {_cfg_def(cfg, 'cluster', 'umap_n_components')})",
    )
    g_clu.add_argument(
        "--min-topic-size", type=int, metavar="N",
        help=f"[cluster.min_topic_size] (default: {_cfg_def(cfg, 'cluster', 'min_topic_size')}"
             " — 숫자 지정 시 sweep 생략 직행)",
    )
    g_clu.add_argument(
        "--seed", type=int, metavar="N",
        help=f"[cluster.seed] 재현성 (default: {_cfg_def(cfg, 'cluster', 'seed')})",
    )
    g_clu.add_argument(
        "--force-retrain", action="store_true",
        help="[cluster] 캐시 무시하고 재학습 (default: off; flag 있으면 on)",
    )

    # ── model (embed / label LLM) ────────────────────────
    g_mdl = parser.add_argument_group("model")
    g_mdl.add_argument(
        "--embed-model", metavar="TEXT",
        help=f"[embed.model_name] SentenceTransformer 모델 (default: {_cfg_def(cfg, 'embed', 'model_name')})",
    )
    g_mdl.add_argument(
        "--label-model", metavar="TEXT",
        help=f"[label.model] LLM 모델 (default: {_cfg_def(cfg, 'label', 'model')})",
    )

    # ── trend / label 기타 ───────────────────────────────
    g_trd = parser.add_argument_group("trend / etc")
    g_trd.add_argument(
        "--trend-top-n", type=int, metavar="N",
        help=f"[timeseries.trend.top_n_keywords] 토픽당 추세 KW 수 (default: {_cfg_def(cfg, 'timeseries', 'trend', 'top_n_keywords')})",
    )
    g_trd.add_argument(
        "--relevance-criterion", metavar="TEXT",
        help=f"[label.relevance_criterion] (default: {_cfg_def(cfg, 'label', 'relevance_criterion')})",
    )

    return parser


def _load_cfg(path: str) -> dict:
    cfg_path = Path(path)
    if not cfg_path.is_file():
        print(f"[error] config 파일 없음: {cfg_path}", file=sys.stderr)
        sys.exit(1)
    with cfg_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _apply_overrides(cfg: dict, args: argparse.Namespace) -> dict:
    if args.umap_dim is not None:
        cfg.setdefault("cluster", {})["umap_n_components"] = args.umap_dim
    if args.min_topic_size is not None:
        cfg.setdefault("cluster", {})["min_topic_size"] = args.min_topic_size
    if args.force_retrain:
        cfg.setdefault("cluster", {})["force_retrain"] = True
    if args.relevance_criterion is not None:
        cfg.setdefault("label", {})["relevance_criterion"] = args.relevance_criterion
    if args.input_pmid is not None:
        cfg.setdefault("paths", {})["input_pmid_csv"] = args.input_pmid
    if args.run_id is not None:
        cfg.setdefault("paths", {})["run_id"] = args.run_id
    if args.project_theme is not None:
        cfg.setdefault("project", {})["주제"] = args.project_theme
    if args.project_source is not None:
        cfg.setdefault("project", {})["데이터 출처"] = args.project_source
    if args.seed is not None:
        cfg.setdefault("cluster", {})["seed"] = args.seed
    if args.trend_top_n is not None:
        cfg.setdefault("timeseries", {}).setdefault("trend", {})["top_n_keywords"] = args.trend_top_n
    if args.embed_model is not None:
        cfg.setdefault("embed", {})["model_name"] = args.embed_model
    if args.label_model is not None:
        cfg.setdefault("label", {})["model"] = args.label_model
    return cfg


def _setup_logging(output_dir: Path) -> Path:
    log_dir = output_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"run_{datetime.now():%Y%m%d_%H%M%S}.log"

    logger.remove()
    logger.add(sys.stderr, level="INFO", format="<level>{message}</level>")
    logger.add(log_path, level="DEBUG", rotation=None, retention=None,
               format="{time:YYYY-MM-DD HH:mm:ss} | {level: <7} | {message}")
    return log_path


def _resolve_output_dir(cfg: dict) -> Path:
    """paths.output_dir + (선택) paths.run_id 로 effective 산출물 디렉토리 계산.

    run_id == 'auto' 면 타임스탬프(run_YYYYmmdd_HHMMSS). cfg['paths']['output_dir'] 를
    effective 경로로 갱신 → 모든 step 이 동일 run 디렉토리를 본다. run_id 없으면 today 와 동일.
    """
    base = Path(cfg["paths"]["output_dir"])
    run_id = cfg.get("paths", {}).get("run_id")
    if run_id == "auto":
        run_id = f"run_{datetime.now():%Y%m%d_%H%M%S}"
    output_dir = base / run_id if run_id else base
    cfg["paths"]["output_dir"] = str(output_dir)
    return output_dir


def _select_steps(args: argparse.Namespace) -> list[str]:
    """positional steps > --from/--to 범위 > 전체."""
    if args.steps:
        return args.steps
    if args.from_step or args.to_step:
        i0 = STEPS.index(args.from_step) if args.from_step else 0
        i1 = STEPS.index(args.to_step) if args.to_step else len(STEPS) - 1
        return STEPS[i0:i1 + 1]
    return list(STEPS)


def _list_presets() -> list[str]:
    """패키지 동봉 프리셋 이름 목록 (presets/*.yaml)."""
    d = Path(__file__).parent / "presets"
    return sorted(p.stem for p in d.glob("*.yaml")) if d.is_dir() else []


def _init(name: str, preset: str | None) -> int:
    """<name>.yaml 을 프리셋 복사로 생성 (config 스캐폴딩)."""
    presets = _list_presets()
    preset = preset or "general"
    if preset not in presets:
        print(f"[init] 알 수 없는 preset: {preset!r} (가용: {', '.join(presets) or '없음'})", file=sys.stderr)
        return 1
    dst = Path(f"{name}.yaml")
    if dst.exists():
        print(f"[init] 이미 존재: {dst} — 덮어쓰지 않음", file=sys.stderr)
        return 1
    src = Path(__file__).parent / "presets" / f"{preset}.yaml"
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"[init] {dst} 생성 (preset={preset}).\n  편집 후 실행: topic-pipeline --config {dst}")
    return 0


def _serve_blocked(path: str) -> bool:
    """serve 시 차단할 경로 (logs/ — DEBUG 로그 노출 방지, 시크릿 가드레일).

    translate_path 와 동일하게 unquote→정규화한 뒤 'logs' 세그먼트가 경로 어디에든
    있으면 차단한다. 가드와 파일 resolver 가 같은 문자열을 보게 하여 퍼센트 인코딩
    (`/%6Cogs/`, `/logs%2f`)·dot-segment(`/./logs/`, `/foo/../logs/`)·하위 run-id
    (`/exp1/logs/`)·대소문자(case-insensitive FS) 우회를 모두 막는다.
    """
    decoded = urllib.parse.unquote(path.split("?", 1)[0].split("#", 1)[0])
    parts = [seg for seg in posixpath.normpath(decoded).split("/") if seg not in ("", ".", "..")]
    return any(seg.lower() == "logs" for seg in parts)


def _serve(output_dir: Path, port: int) -> int:
    """output_dir 를 stdlib http.server 로 정적 서빙(127.0.0.1). opt-in, 파이프라인 외 affordance."""
    import functools
    import http.server
    import socketserver

    directory = str(output_dir)
    if not Path(directory).is_dir():
        print(f"[serve] output_dir 없음: {directory} — 먼저 파이프라인 실행", file=sys.stderr)
        return 1

    class _Handler(http.server.SimpleHTTPRequestHandler):
        def send_head(self):
            # GET·HEAD 공통 진입점 → 한 곳에서 차단. 한글 메시지는 reason phrase(latin-1)가
            # 아니라 explain 본문(UTF-8)으로 전달해 send_response_only 의 인코딩 크래시를 피한다.
            if _serve_blocked(self.path):
                self.send_error(403, "Forbidden", "logs 디렉터리 접근 차단")
                return None
            return super().send_head()

    handler = functools.partial(_Handler, directory=directory)
    with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
        print(f"[serve] http://127.0.0.1:{port}/  (root={directory}; report.html / results.json, logs/ 차단)")
        print("[serve] Ctrl-C 로 종료.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[serve] 종료")
    return 0


def _print_steps() -> None:
    """step 목록 + 모듈 + 필요/생성 산출물."""
    print("topic-pipeline steps (실행 순서):")
    for i, s in enumerate(STEPS):
        mod = STEP_MODULES.get(s) or "(미구현)"
        reqs = ", ".join(STEP_REQUIRES.get(s, [])) or "—"
        prods = ", ".join(STEP_PRODUCES.get(s, [])) or "—"
        print(f"  {i}. {s:<16} → {mod}")
        print(f"       requires: {reqs}")
        print(f"       produces: {prods}")


# STEP_REQUIRES 의 convention 파일을 대체하는 step별 config override 키 (cfg[section][key]).
# override 경로가 명시되면 그 경로 존재로 판정하고 convention 파일은 보지 않는다. (issue #1)
_OVERRIDE_FOR: dict[str, dict[str, tuple[str, str]]] = {
    "timeseries": {
        "s2_meta_for_embed.csv": ("timeseries", "labeled_csv"),
        "s3_labels.csv": ("timeseries", "labeled_csv"),
        "s5_label-relevance.md": ("timeseries", "relevance_md"),
    },
    "report": {
        "s2_meta_for_embed.csv": ("report", "labeled_csv"),
        "s3_labels.csv": ("report", "labeled_csv"),
        "s5_label-relevance.md": ("report", "relevance_md"),
        "s4_keywords_comparison.csv": ("report", "keywords_csv"),
    },
}


def _fetch_input_path(cfg: dict) -> str | None:
    """fetch.source 별 로컬 입력 경로 (s1_fetch 어댑터와 동일 규칙). arxiv 는 네트워크라 None."""
    paths = cfg.get("paths", {}) or {}
    fetch = cfg.get("fetch", {}) or {}
    default = paths.get("input_pmid_csv")
    source = fetch.get("source", "pubmed")
    if source == "csv":
        return fetch.get("input_csv") or default
    if source == "jsonl":
        return fetch.get("input_jsonl") or fetch.get("input_csv") or default
    if source == "dir":
        return fetch.get("input_dir") or default
    if source == "arxiv":
        return None
    return default  # pubmed / 기타


def _validate_preconditions(
    selected: list[str], output_dir: Path, cfg: dict
) -> list[tuple[str, str, str]]:
    """선택 step 들을 순서대로 보며, 같은 run 의 앞 step 이 만들지 않고 config override 로도
    충족되지 않는 선행 산출물이 없으면 (step, 누락경로, 생성step) 수집. fetch 는 source 별
    입력 존재만 확인. heavy import 전에 호출되어 mid-step FileNotFoundError 대신 up-front 에러."""
    producer_of = {f: s for s, files in STEP_PRODUCES.items() for f in files}
    produced: set[str] = set()
    missing: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for step in selected:
        overrides = _OVERRIDE_FOR.get(step, {})
        for req in STEP_REQUIRES.get(step, []):
            if req in produced:
                continue
            ov = overrides.get(req)
            if ov:
                path = (cfg.get(ov[0], {}) or {}).get(ov[1])
                if path:  # override 명시 → 그 경로 존재로 판정 (convention 파일 무시)
                    if not Path(path).exists() and (step, str(path)) not in seen:
                        seen.add((step, str(path)))
                        missing.append((step, str(path), "(config override)"))
                    continue
            if not (output_dir / req).exists():
                missing.append((step, req, producer_of.get(req, "?")))
        produced |= set(STEP_PRODUCES.get(step, []))
    if "fetch" in selected:
        inp = _fetch_input_path(cfg)
        if inp and not Path(inp).exists():
            missing.append(("fetch", str(inp), "(입력)"))
    return missing


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_steps:
        _print_steps()
        return 0

    if args.init:
        return _init(args.init, args.preset)

    if args.serve:
        cfg = _apply_overrides(_load_cfg(args.config), args)
        return _serve(_resolve_output_dir(cfg), args.port)

    selected = _select_steps(args)
    if not selected:
        print("[error] 선택된 step 이 없습니다 (--from/--to 범위 확인).", file=sys.stderr)
        return 1

    cfg = _apply_overrides(_load_cfg(args.config), args)

    output_dir = _resolve_output_dir(cfg)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = _setup_logging(output_dir)

    logger.info(f"topic-pipeline start — config={args.config}")
    logger.info(f"log: {log_path}")
    logger.info(f"steps: {selected}")

    missing = _validate_preconditions(selected, output_dir, cfg)
    if missing:
        logger.error("사전 조건 미충족 — 필요한 선행 산출물이 없습니다:")
        for step, f, producer in missing:
            logger.error(f"  [{step}] 누락: {f}  (생성 step: {producer})")
        logger.error("선행 step 을 먼저 실행하거나 --from 으로 범위를 조정하세요.")
        return 1

    total_t0 = time.time()
    for step in selected:
        mod_path = STEP_MODULES.get(step)
        if mod_path is None:
            logger.warning(f"[skip] {step} — 미구현")
            continue

        t0 = time.time()
        logger.info(f"=== step: {step} start ===")
        try:
            mod = importlib.import_module(mod_path)
            mod.run(copy.deepcopy(cfg))
        except Exception as e:
            logger.exception(f"[fail] {step}: {type(e).__name__}: {e}")
            return 1

        elapsed = time.time() - t0
        logger.info(f"=== step: {step} done ({elapsed:.1f}s) ===")

    total_elapsed = time.time() - total_t0
    logger.info(f"topic-pipeline done — total {total_elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
