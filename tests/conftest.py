"""pytest 공통 설정. matplotlib 은 headless(Agg) 로 고정 — fonts 테스트가 디스플레이를 요구하지 않도록."""

import os

os.environ.setdefault("MPLBACKEND", "Agg")
