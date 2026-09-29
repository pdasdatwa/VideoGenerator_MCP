from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.errors import MarketingError
from app.renderer.validator import parse_scene


def _scene(**overrides):
    payload = {
        "scene_id": "scene_01",
        "duration": 4,
        "layers": [
            {
                "id": "headline",
                "type": "text",
                "content": "Hello",
                "start": 0,
                "duration": 4,
                "position": {"x": 0.5, "y": 0.2},
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_valid_scene_parses():
    scene = parse_scene(_scene())
    assert scene.scene_id == "scene_01"


def test_invalid_animation():
    payload = _scene()
    payload["layers"][0]["animation"] = {"type": "explode"}
    with pytest.raises(MarketingError) as caught:
        parse_scene(payload)
    assert caught.value.code == "INVALID_ANIMATION"


def test_invalid_coordinates():
    payload = _scene()
    payload["layers"][0]["position"] = {"x": 1.4, "y": 0.2}
    with pytest.raises(MarketingError) as caught:
        parse_scene(payload)
    assert caught.value.code == "INVALID_COORDINATES"


def test_invalid_timing():
    payload = _scene()
    payload["layers"][0]["start"] = 5
    with pytest.raises(MarketingError) as caught:
        parse_scene(payload)
    assert caught.value.code == "INVALID_DURATION"


def test_missing_asset_reference_on_image_layer():
    payload = _scene(
        layers=[{"id": "product", "type": "image", "start": 0, "duration": 2}]
    )
    with pytest.raises(MarketingError) as caught:
        parse_scene(payload)
    assert caught.value.code == "INVALID_LAYER"


def test_extra_field_rejected():
    payload = _scene()
    payload["layers"][0]["javascript"] = "alert(1)"
    with pytest.raises(MarketingError):
        parse_scene(payload)


def test_schema_model_rejects_bad_duration():
    with pytest.raises((MarketingError, ValidationError)):
        parse_scene(_scene(duration=0))
