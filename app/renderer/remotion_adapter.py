"""Call the Node Remotion renderer. Scene props are data, never code."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from app.config import Settings
from app.errors import MarketingError
from app.logsetup import get_logger
from app.renderer.version import RENDERER_VERSION

logger = get_logger(__name__)


class RemotionAdapter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._process: subprocess.Popen[str] | None = None

    def render_scene(self, props: dict, output: Path, *, progress_file: Path | None = None) -> None:
        output = output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        props_path = output.with_suffix(".props.json")
        props_path.write_text(json.dumps(props), encoding="utf-8")
        bundle = (self.settings.data_dir / "cache" / "remotion-bundle").resolve()
        bundle.parent.mkdir(parents=True, exist_ok=True)
        script = (self.settings.renderer_dir / "render-scene.mjs").resolve()
        if not script.exists():
            raise MarketingError(
                "RENDER_FAILURE",
                "Remotion render script is missing.",
                suggested_action="Install renderer dependencies with npm install inside renderer/.",
            )
        command = [
            self.settings.node_path,
            str(script),
            "--props",
            str(props_path),
            "--out",
            str(output),
            "--bundle",
            str(bundle),
            "--version",
            RENDERER_VERSION,
        ]
        if progress_file:
            command.extend(["--progress", str(progress_file)])
        logger.info(
            "remotion render start",
            extra={"scene_id": props.get("sceneId"), "cache_miss": True},
        )
        try:
            self._process = subprocess.Popen(
                command,
                cwd=str(self.settings.renderer_dir.resolve()),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = self._process.communicate(timeout=1800)
            code = self._process.returncode
        except subprocess.TimeoutExpired as exc:
            self.terminate()
            raise MarketingError(
                "RENDER_FAILURE",
                "Remotion render timed out.",
                suggested_action="Retry with the preview profile or a shorter scene.",
                scene_id=props.get("sceneId"),
            ) from exc
        finally:
            self._process = None
            if props_path.exists():
                props_path.unlink()
        if code != 0:
            log = stderr or stdout or ""
            raise MarketingError(
                "RENDER_FAILURE",
                "Remotion failed to render the scene.",
                suggested_action="Check that Node dependencies are installed and Chrome can launch.",
                scene_id=props.get("sceneId"),
                renderer_stderr=log[:2500],
            )

    def terminate(self) -> None:
        process = self._process
        if process is None or process.poll() is not None:
            return
        if process.pid:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                check=False,
                capture_output=True,
                text=True,
            )
        else:
            process.kill()
