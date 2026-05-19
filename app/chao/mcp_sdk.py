import importlib
import importlib.metadata
from typing import Any


def get_mcp_sdk_status() -> dict[str, Any]:
    try:
        version = importlib.metadata.version("mcp")
    except importlib.metadata.PackageNotFoundError:
        return {
            "installed": False,
            "package": "mcp",
            "version": None,
            "module": None,
        }

    module = importlib.import_module("mcp")

    return {
        "installed": True,
        "package": "mcp",
        "version": version,
        "module": module.__name__,
    }
