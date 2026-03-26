from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_service_app_module(
    service_dir: str,
    module_name: str,
    *,
    package_name: str | None = None,
    reload_modules: bool = False,
):
    app_dir = REPO_ROOT / "services" / service_dir / "app"
    if service_dir == "gateway-service":
        parent_dir = str(app_dir.parent)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)

    resolved_package = package_name or f"{service_dir.replace('-', '_')}_app"

    app_dir_str = str(app_dir)
    if app_dir_str not in sys.path:
        sys.path.insert(0, app_dir_str)

    if reload_modules:
        for name in list(sys.modules):
            if name == resolved_package or name.startswith(f"{resolved_package}."):
                sys.modules.pop(name, None)

    if resolved_package not in sys.modules:
        package = types.ModuleType(resolved_package)
        package.__path__ = [app_dir_str]
        sys.modules[resolved_package] = package

    full_name = f"{resolved_package}.{module_name}"
    if full_name in sys.modules:
        return sys.modules[full_name]

    file_path = app_dir / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(full_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module from {file_path}")

    module = importlib.util.module_from_spec(spec)
    # Set __package__ for submodules so relative imports work
    if "/" in module_name:
        parent_pkg = ".".join([resolved_package] + module_name.split("/")[:-1])
        module.__package__ = parent_pkg
    else:
        module.__package__ = resolved_package
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module