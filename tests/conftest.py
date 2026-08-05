from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from environmental_growth.config import load_config


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def analysis_config():
    return deepcopy(load_config(REPOSITORY_ROOT / "config" / "analysis.yaml"))
