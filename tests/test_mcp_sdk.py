import importlib.metadata
import tomllib
from pathlib import Path

from app.chao.mcp_sdk import get_mcp_sdk_status

ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_declares_official_mcp_dependency():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert "mcp>=1.0.0" in pyproject["project"]["dependencies"]


def test_mcp_sdk_status_shape_when_package_is_installed():
    status = get_mcp_sdk_status()

    if importlib.metadata.version("mcp"):
        assert status["installed"] is True
        assert status["package"] == "mcp"
        assert status["version"]
        assert status["module"] == "mcp"
