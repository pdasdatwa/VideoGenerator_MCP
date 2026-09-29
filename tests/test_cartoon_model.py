"""Project mode, the character record, and character asset wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.errors import MarketingError
from app.renderer.cartoon.resolve import resolve_character_asset
from tests.cartoonkit import cartoon_project, register_character, write_svg


def test_projects_default_to_standard_mode_and_refuse_character_tools(ctx, tmp_path: Path):
    project = ctx.projects.create("Plain", preset="square", fps=12)
    assert project["mode"] == "standard"

    with pytest.raises(MarketingError) as excinfo:
        ctx.characters.create(project["project_id"], {"character_id": "raj", "name": "Raj"})
    assert excinfo.value.code == "CARTOON_MODE_REQUIRED"
    assert "mode='cartoon'" in excinfo.value.message


def test_a_project_can_be_switched_into_cartoon_mode(ctx, tmp_path: Path):
    project = ctx.projects.create("Switch", preset="square", fps=12)
    project_id = project["project_id"]
    updated = ctx.projects.update(project_id, {"mode": "cartoon"})
    assert updated["mode"] == "cartoon"
    ctx.characters.create(project_id, {"character_id": "raj", "name": "Raj"})
    assert ctx.characters.list_characters(project_id)["characters"][0]["character_id"] == "raj"


def test_character_record_keeps_identity_and_marks_text_as_unverified(ctx, tmp_path: Path):
    project_id = cartoon_project(ctx, tmp_path)
    character = register_character(ctx, project_id, tmp_path, "raj")

    assert character["name"] == "Raj"
    assert character["traits"] == ["sarcastic"]
    assert character["default_anchor"] == {"x": 0.5, "y": 1.0}
    assert "not verified" in character["metadata_note"]
    assert character["assets"]["base"] == "raj_base"
    assert character["assets"]["expressions"]["angry"] == "raj_angry"
    assert character["assets"]["poses"]["standing"] == "raj_standing"


def test_character_assets_resolve_in_the_documented_order(ctx, tmp_path: Path):
    project_id = cartoon_project(ctx, tmp_path)
    register_character(ctx, project_id, tmp_path, "raj")
    variant = write_svg(tmp_path / "imports" / "raj_sitting_angry.svg", "#804030")
    ctx.characters.register_asset(
        project_id,
        "raj",
        str(variant),
        role="character_pose",
        key="sitting:angry",
        asset_id="raj_sitting_angry",
    )
    character = ctx.characters.get(project_id, "raj")

    assert character.assets.variants["sitting:angry"] == "raj_sitting_angry"
    assert resolve_character_asset(character, "sitting", "angry") == "raj_sitting_angry"
    assert resolve_character_asset(character, "standing", "angry") == "raj_angry"
    assert resolve_character_asset(character, "standing", None) == "raj_standing"
    assert resolve_character_asset(character, None, None) == "raj_base"


def test_character_assets_are_ordinary_assets_carrying_a_role(ctx, tmp_path: Path):
    project_id = cartoon_project(ctx, tmp_path)
    register_character(ctx, project_id, tmp_path, "raj")

    asset = ctx.assets.get(project_id, "raj_angry")
    assert asset.semantic_type == "character_expression"
    assert asset.character_id == "raj"
    assert asset.technical_metadata["width"] > 0
    assert any(item["id"] == "raj_angry" for item in ctx.assets.list_assets(project_id))


def test_unknown_part_names_warn_instead_of_failing(ctx, tmp_path: Path):
    project_id = cartoon_project(ctx, tmp_path)
    register_character(ctx, project_id, tmp_path, "raj")
    path = write_svg(tmp_path / "imports" / "raj_tail.svg", "#333333")
    result = ctx.characters.register_asset(
        project_id, "raj", str(path), role="character_part", key="tail", asset_id="raj_tail"
    )
    assert result["warnings"]
    assert ctx.characters.get(project_id, "raj").assets.parts["tail"] == "raj_tail"


def test_character_cannot_reference_an_unregistered_asset(ctx, tmp_path: Path):
    project_id = cartoon_project(ctx, tmp_path)
    with pytest.raises(MarketingError) as excinfo:
        ctx.characters.create(
            project_id,
            {"character_id": "ghost", "name": "Ghost", "assets": {"base": "nobody"}},
        )
    assert excinfo.value.code == "INVALID_ASSET_REFERENCE"


def test_a_character_used_by_a_scene_cannot_be_deleted(ctx, tmp_path: Path):
    project_id = cartoon_project(ctx, tmp_path)
    register_character(ctx, project_id, tmp_path, "raj")
    ctx.scenes.create(
        project_id,
        {"scene_id": "s1", "duration": 2, "cartoon": {"characters": [{"character_id": "raj"}]}},
    )

    with pytest.raises(MarketingError) as excinfo:
        ctx.characters.delete(project_id, "raj", ctx.character_users(project_id, "raj"))
    assert excinfo.value.code == "CHARACTER_IN_USE"

    ctx.scenes.delete(project_id, "s1")
    assert ctx.characters.delete(project_id, "raj", ctx.character_users(project_id, "raj"))["deleted"] == "raj"
    # The artwork survives the character, because it is an ordinary asset.
    assert ctx.assets.get(project_id, "raj_base").id == "raj_base"


def test_get_character_assets_reports_what_a_scene_may_name(ctx, tmp_path: Path):
    project_id = cartoon_project(ctx, tmp_path)
    register_character(ctx, project_id, tmp_path, "raj", parts=("mouth_open", "mouth_closed"))
    report = ctx.characters.get_assets(project_id, "raj")

    assert set(report["expressions"]) == {"angry", "happy"}
    assert report["poses"] == ["standing"]
    assert set(report["parts"]) == {"mouth_open", "mouth_closed"}
    assert report["resolution_order"][0].startswith("assets.variants")
