"""Register, list, and describe assets. The LLM addresses them by asset_id."""

from __future__ import annotations

import hashlib
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import ALLOWED_EXTENSIONS, Settings
from app.errors import MarketingError
from app.ids import new_id, validate_client_id
from app.models.asset import Asset
from app.renderer.cartoon.names import ASSET_ROLES
from app.services.asset_inspection_service import AssetInspectionService
from app.services.asset_preview_service import AssetPreviewService
from app.services.project_service import ProjectService
from app.storage.filesystem import read_json, write_json
from app.storage.jail import resolve_allowed_file
from app.storage.paths import DataPaths

_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AssetService:
    def __init__(self, settings: Settings, projects: ProjectService) -> None:
        self.settings = settings
        self.projects = projects
        self.paths = DataPaths(settings.data_dir)
        self.inspector = AssetInspectionService()
        self.previews = AssetPreviewService(self.paths)

    def register(
        self,
        project_id: str,
        path: str,
        *,
        asset_id: str | None = None,
        replace: bool = False,
        semantic_type: str | None = None,
        character_id: str | None = None,
    ) -> dict[str, Any]:
        self.projects.get(project_id)
        if semantic_type is not None and semantic_type not in ASSET_ROLES:
            raise MarketingError(
                "INVALID_METADATA",
                f"semantic_type '{semantic_type}' is not a known role.",
                suggested_action=f"Use one of: {', '.join(ASSET_ROLES)}.",
            )
        source = resolve_allowed_file(path, self.settings.asset_source_dirs)
        suffix = source.suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise MarketingError(
                "UNSUPPORTED_FORMAT",
                f"Extension {suffix or '(none)'} is not supported.",
                suggested_action="Use PNG, JPEG, WebP, SVG, MP4, MOV, WebM, MP3, WAV, or AAC.",
            )
        asset_type = ALLOWED_EXTENSIONS[suffix]
        inspected = self.inspector.inspect(source, asset_type)
        digest = _sha256(source)
        blob_rel = Path("blobs") / digest[:2] / f"{digest}{suffix}"
        blob_abs = self.paths.root / blob_rel
        if not blob_abs.exists():
            blob_abs.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, blob_abs)
        chosen = asset_id or new_id("asset")
        validate_client_id(chosen, field="asset_id")
        existing_path = self.paths.asset_file(project_id, chosen)
        if existing_path.exists() and not replace:
            raise MarketingError(
                "ASSET_EXISTS",
                f"Asset {chosen} already exists.",
                suggested_action="Pass replace=true to swap the file, or omit asset_id to create a new one.",
                asset_id=chosen,
            )
        previous = Asset.model_validate(read_json(existing_path)) if existing_path.exists() else None
        filename = _FILENAME.sub("_", source.name).strip("._") or f"asset{suffix}"
        now = _now()
        asset = Asset(
            id=chosen,
            project_id=project_id,
            filename=filename,
            type=asset_type,  # type: ignore[arg-type]
            mime_type=inspected["mime_type"],
            file_size=source.stat().st_size,
            sha256=digest,
            blob_path=blob_rel.as_posix(),
            width=inspected.get("width"),
            height=inspected.get("height"),
            has_alpha=inspected.get("has_alpha"),
            duration=inspected.get("duration"),
            technical_metadata=_technical(inspected, source.stat().st_size, digest),
            semantic_metadata=None if previous is None else previous.semantic_metadata,
            semantic_type=semantic_type or (previous.semantic_type if previous else None),  # type: ignore[arg-type]
            character_id=character_id or (previous.character_id if previous else None),
            preview={},
            created_at=previous.created_at if previous else now,
            updated_at=now,
        )
        asset.preview = self.previews.generate(asset)
        write_json(self.paths.asset_file(project_id, asset.id), asset.model_dump(mode="json"))
        payload = self.public(asset)
        payload["replaced"] = previous is not None
        payload["deduplicated"] = blob_abs.exists()
        return payload

    def get(self, project_id: str, asset_id: str) -> Asset:
        self.projects.get(project_id)
        path = self.paths.asset_file(project_id, asset_id)
        if not path.exists():
            raise MarketingError(
                "ASSET_NOT_FOUND",
                f"Asset {asset_id} does not exist on project {project_id}.",
                suggested_action="Call list_assets and use an id from that list.",
                project_id=project_id,
                asset_id=asset_id,
            )
        return Asset.model_validate(read_json(path))

    def list_assets(self, project_id: str) -> list[dict[str, Any]]:
        self.projects.get(project_id)
        folder = self.paths.assets_dir(project_id)
        if not folder.exists():
            return []
        return [self.public(Asset.model_validate(read_json(path))) for path in sorted(folder.glob("*.json"))]

    def map_assets(self, project_id: str) -> dict[str, Asset]:
        folder = self.paths.assets_dir(project_id)
        if not folder.exists():
            return {}
        assets = [Asset.model_validate(read_json(path)) for path in folder.glob("*.json")]
        return {asset.id: asset for asset in assets}

    def update_metadata(self, project_id: str, asset_id: str, semantic: dict[str, Any]) -> dict[str, Any]:
        asset = self.get(project_id, asset_id)
        if not isinstance(semantic, dict):
            raise MarketingError(
                "INVALID_METADATA",
                "semantic metadata must be an object.",
                suggested_action="Pass a JSON object such as {description, subjects, recommended_usage}.",
                asset_id=asset_id,
            )
        asset.semantic_metadata = semantic
        asset.updated_at = _now()
        write_json(self.paths.asset_file(project_id, asset_id), asset.model_dump(mode="json"))
        return self.public(asset)

    def tag(
        self,
        project_id: str,
        asset_id: str,
        *,
        semantic_type: str | None = None,
        character_id: str | None = None,
    ) -> Asset:
        """Record the caller's role for an asset. The pixels are never inspected for this."""
        asset = self.get(project_id, asset_id)
        if semantic_type is not None:
            if semantic_type not in ASSET_ROLES:
                raise MarketingError(
                    "INVALID_METADATA",
                    f"semantic_type '{semantic_type}' is not a known role.",
                    suggested_action=f"Use one of: {', '.join(ASSET_ROLES)}.",
                    asset_id=asset_id,
                )
            asset.semantic_type = semantic_type  # type: ignore[assignment]
        if character_id is not None:
            asset.character_id = character_id
        asset.updated_at = _now()
        write_json(self.paths.asset_file(project_id, asset_id), asset.model_dump(mode="json"))
        return asset

    def delete(self, project_id: str, asset_id: str, referenced_by: list[str]) -> dict[str, Any]:
        self.get(project_id, asset_id)
        if referenced_by:
            raise MarketingError(
                "ASSET_IN_USE",
                f"Asset {asset_id} is used by {', '.join(referenced_by)}.",
                suggested_action="Remove the asset from those scenes, then delete it.",
                asset_id=asset_id,
                scene_ids=referenced_by,
            )
        self.paths.asset_file(project_id, asset_id).unlink()
        return {"deleted": asset_id}

    def keyframe_info(self, project_id: str, asset_id: str) -> dict[str, Any]:
        asset = self.get(project_id, asset_id)
        names = [name for name in asset.preview if name == "poster" or name.startswith("keyframe_") or name == "contact_sheet"]
        return {
            "asset_id": asset_id,
            "type": asset.type,
            "frames": [
                {"name": name, "resource": f"rendering://asset/{asset_id}/preview/{name}"}
                for name in names
            ],
            "index": f"rendering://asset/{asset_id}/keyframes",
        }

    def preview_info(self, project_id: str, asset_id: str) -> dict[str, Any]:
        asset = self.get(project_id, asset_id)
        resources = [f"rendering://asset/{asset_id}"]
        if asset.type in {"image", "svg"}:
            resources.append(f"rendering://asset/{asset_id}/preview/original")
        for name in asset.preview:
            resources.append(f"rendering://asset/{asset_id}/preview/{name}")
        return {
            "asset_id": asset_id,
            "type": asset.type,
            "technical_metadata": asset.technical_metadata,
            "semantic_metadata": asset.semantic_metadata,
            "semantic_metadata_note": asset.semantic_metadata_note,
            "preview_files": asset.preview,
            "resources": resources,
            "visual_access": (
                "Image resources are exposed for clients that can read MCP blobs. "
                "If your client cannot display them, you have not seen this asset. "
                "Do not invent a description. technical_metadata is measured. "
                "semantic_metadata is only present if you stored it earlier."
            ),
        }

    def public(self, asset: Asset) -> dict[str, Any]:
        payload = asset.model_dump(mode="json")
        payload.pop("blob_path", None)
        payload["resource"] = f"rendering://asset/{asset.id}"
        return payload


def _technical(inspected: dict[str, Any], file_size: int, digest: str) -> dict[str, Any]:
    metadata = dict(inspected["technical_metadata"])
    metadata["file_size"] = file_size
    metadata["sha256"] = digest
    metadata["mime_type"] = inspected["mime_type"]
    return metadata


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
