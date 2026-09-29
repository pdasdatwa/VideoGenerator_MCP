from __future__ import annotations

from pathlib import Path

import pytest

from app.errors import MarketingError
from app.storage.jail import resolve_allowed_file


def test_rejects_parent_segments(tmp_path: Path):
    root = tmp_path / "imports"
    root.mkdir()
    with pytest.raises(MarketingError) as caught:
        resolve_allowed_file(str(root / ".." / "secret.txt"), [root])
    assert caught.value.code == "PATH_NOT_ALLOWED"


def test_rejects_file_outside_root(tmp_path: Path):
    root = tmp_path / "imports"
    root.mkdir()
    outside = tmp_path / "secret.png"
    outside.write_bytes(b"nope")
    with pytest.raises(MarketingError) as caught:
        resolve_allowed_file(str(outside), [root])
    assert caught.value.code == "PATH_NOT_ALLOWED"


def test_allows_file_inside_root(tmp_path: Path):
    root = tmp_path / "imports"
    root.mkdir()
    target = root / "ok.png"
    target.write_bytes(b"png")
    assert resolve_allowed_file(str(target), [root]) == target.resolve()


def test_rejects_symlink_escape(tmp_path: Path):
    root = tmp_path / "imports"
    root.mkdir()
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"secret")
    link = root / "alias.png"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks are not permitted on this filesystem")
    with pytest.raises(MarketingError) as caught:
        resolve_allowed_file(str(link), [root])
    assert caught.value.code == "PATH_NOT_ALLOWED"
