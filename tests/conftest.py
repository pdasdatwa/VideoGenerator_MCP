from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.services import build_context


@pytest.fixture()
def ctx(tmp_path: Path):
    settings = Settings(
        data_dir=tmp_path / "data",
        asset_source_dirs=[tmp_path / "imports", tmp_path / "demos" / "assets"],
        renderer_dir=Path("renderer"),
    )
    (tmp_path / "imports").mkdir()
    return build_context(settings)
