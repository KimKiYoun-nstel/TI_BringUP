"""공식 standalone Python 모듈을 수정 없이 불러오는 repo 연결 계층."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

OFFICIAL_PYTHON = Path(__file__).resolve().parents[1] / "official" / "python"

# 공식 모듈은 같은 폴더의 uart_api/uart_runtime을 절대 import한다.
# 이 경로를 우선해 CLI/MCP와 테스트가 모두 같은 배포본을 사용한다.
sys.path.insert(0, str(OFFICIAL_PYTHON))


def load_module(name: str) -> Any:
    return importlib.import_module(name)


uart_api = load_module("uart_api")
