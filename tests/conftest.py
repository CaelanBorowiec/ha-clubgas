"""Pytest configuration — load club_gas submodules without HA __init__.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
PKG_ROOT = ROOT / "custom_components" / "club_gas"


def _register_package(name: str, path: Path) -> ModuleType:
    """Register a package stub so __init__.py is not executed."""
    module = ModuleType(name)
    module.__path__ = [str(path)]  # type: ignore[attr-defined]
    module.__package__ = name
    sys.modules[name] = module
    return module


def _load_module(fullname: str, filepath: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(fullname, filepath)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {fullname} from {filepath}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[fullname] = module
    spec.loader.exec_module(module)
    return module


def pytest_configure() -> None:
    sys.path.insert(0, str(ROOT / "custom_components"))
    _register_package("club_gas", PKG_ROOT)
    _register_package("club_gas.api", PKG_ROOT / "api")

    for fullname, relative in (
        ("club_gas.const", "const.py"),
        ("club_gas.models", "models.py"),
        ("club_gas.api.helpers", "api/helpers.py"),
        ("club_gas.api.costco", "api/costco.py"),
        ("club_gas.api.sams", "api/sams.py"),
    ):
        _load_module(fullname, PKG_ROOT / relative)
