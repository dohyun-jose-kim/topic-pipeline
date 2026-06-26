"""topic-pipeline CLI entry point.

Phase 6 부터 loguru 로깅 + step 실패 처리 + step 타이밍 추가 (PLAN §15-3, §15-4).
"""

from __future__ import annotations

import argparse
import copy
import importlib
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml
from loguru import logger

STEPS = ["fetch", "embed", "cluster", "enrich", "label", "label-relevance", "timeseries", "report"]

STEP_MODULES: dict[str, str | None] = {
    "fetch": "topic_pipeline.steps.s1_fetch",            # Phase 4
    "embed": "topic_pipeline.steps.s2_embed",            # Phase 5a
    "cluster": "topic_pipeline.steps.s3_cluster",        # Phase 5b
    "enrich": "topic_pipeline.steps.s4_enrich",          # Phase 3a
    "label": "topic_pipeline.steps.s5_label",            # Phase 3b
    "label-relevance": "topic_pipeline.steps.s5_label_relevance",  # NEXT_PLAN §C
    "timeseries": "topic_pipeline.steps.s6_timeseries",  # Phase 3c
    "report": "topic_pipeline.steps.s7_report",          # Phase 3d
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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    selected = args.steps or STEPS
    cfg = _apply_overrides(_load_cfg(args.config), args)

    output_dir = _resolve_output_dir(cfg)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = _setup_logging(output_dir)

    logger.info(f"topic-pipeline start — config={args.config}")
    logger.info(f"log: {log_path}")
    logger.info(f"steps: {selected}")

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
