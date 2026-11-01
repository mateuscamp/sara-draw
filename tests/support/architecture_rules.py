# SPDX-License-Identifier: GPL-3.0-only
"""The architecture rules that tests/architecture runs: each checks a decision in docs/adr/.

Kept apart from the tests so the rules and their tests each fit in one agent read.
"""

from __future__ import annotations

import ast
import sys
import tomllib
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "ai_draw"
PACKAGE_DIR = ROOT / "src" / PACKAGE
SPDX = "# SPDX-License-Identifier: GPL-3.0-only"
# Every Python file the repository ships: the package, its tests and the examples.
SOURCE_FOLDERS = (PACKAGE_DIR, ROOT / "tests", ROOT / "examples", ROOT / "docs" / "gallery")

# ADR-0001: the layers each layer may import. Modules right under ai_draw/ (cli.py,
# __init__.py) stitch the layers together and may import any of them.
LAYER_IMPORTS: dict[str, frozenset[str]] = {
    "geometry": frozenset(),
    "grid": frozenset(),
    "pixel": frozenset({"geometry", "grid"}),
    "smooth": frozenset({"geometry", "grid"}),
    "io": frozenset({"grid"}),
}
TOP_LEVEL = ""

# ADR-0002: third-party packages per layer. Pillow lives only in io/. Test-only packages
# (fontTools, freetype, skimage, pytest) are in no set, so src/ can never import them.
THIRD_PARTY: dict[str, frozenset[str]] = {
    "geometry": frozenset(),
    "grid": frozenset({"numpy"}),
    "pixel": frozenset({"numpy"}),
    "smooth": frozenset({"numpy"}),
    "io": frozenset({"numpy", "PIL"}),
    TOP_LEVEL: frozenset({"numpy"}),
}

MAX_FILE_LINES = 400  # AGENTS.md: a file fits in one agent read
MAX_FUNCTION_LINES = 40  # hard ceiling; AGENTS.md aims at 20
# AGENTS.md: names that say nothing. Matched as the whole identifier, so `base_color` (a
# palette term) stays legal and `data` does not.
BANNED_NAMES = frozenset(
    {"data", "info", "handler", "manager", "helper", "utils", "process", "base", "common"}
    | {"item", "obj"},
)
# ADR-0002: Pillow draws and resamples by its own rules; the pixel output must not inherit them.
BANNED_ATTRIBUTES = frozenset({"ImageDraw", "resize"})


# --- rules -----------------------------------------------------------------------------


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def where(path: Path, line: int) -> str:
    return f"{path.as_posix()}:{line}"


def layer_of(path: Path, package_dir: Path) -> str:
    parts = path.relative_to(package_dir).parts
    return parts[0] if len(parts) > 1 else TOP_LEVEL


def imported_names(tree: ast.Module) -> list[tuple[str, int]]:
    """Every import as (dotted name, line); a relative import keeps its leading dots."""
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name, node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.append(("." * node.level + (node.module or ""), node.lineno))
    return found


def internal_problem(layer: str, name: str) -> str | None:
    if layer == TOP_LEVEL:
        return None
    parts = name.split(".")
    target = parts[1] if len(parts) > 1 else TOP_LEVEL
    allowed = LAYER_IMPORTS[layer]
    if target in allowed | {layer}:
        return None
    return f"layer {layer!r} imports {name!r}; allowed: {sorted(allowed)} (ADR-0001)"


def import_problem(layer: str, name: str) -> str | None:
    if name.startswith("."):
        return f"relative import {name!r}; write the absolute ai_draw.<layer> path"
    top = name.split(".", maxsplit=1)[0]
    if top == PACKAGE:
        return internal_problem(layer, name)
    if top in sys.stdlib_module_names or top in THIRD_PARTY[layer]:
        return None
    allowed = sorted(THIRD_PARTY[layer])
    return f"layer {layer or 'top'!r} imports {top!r}; third-party allowed: {allowed} (ADR-0002)"


def import_violations(package_dir: Path) -> list[str]:
    violations: list[str] = []
    for path in python_files(package_dir):
        layer = layer_of(path, package_dir)
        if layer not in THIRD_PARTY:
            violations.append(f"{where(path, 1)}: layer {layer!r} is not in the ADR-0001 table")
            continue
        for name, line in imported_names(parse(path)):
            problem = import_problem(layer, name)
            if problem is not None:
                violations.append(f"{where(path, line)}: {problem}")
    return violations


def module_name(path: Path, package_dir: Path) -> str:
    parts = path.relative_to(package_dir.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def import_targets(tree: ast.Module) -> set[str]:
    """Modules a file may load: `from a.b import c` can mean the module a.b.c."""
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            targets.add(node.module)
            targets.update(f"{node.module}.{alias.name}" for alias in node.names)
    return targets


def import_graph(package_dir: Path) -> dict[str, set[str]]:
    paths = {module_name(path, package_dir): path for path in python_files(package_dir)}
    return {
        name: {target for target in import_targets(parse(path)) if target in paths} - {name}
        for name, path in paths.items()
    }


def cycle_violations(package_dir: Path) -> list[str]:
    graph = import_graph(package_dir)
    cycles: set[str] = set()
    finished: set[str] = set()

    def visit(node: str, trail: list[str]) -> None:
        if node in trail:
            cycle = trail[trail.index(node) :]
            # Rotate so the same cycle found from another start reads the same.
            start = cycle.index(min(cycle))
            cycles.add(" -> ".join([*cycle[start:], *cycle[:start], min(cycle)]))
            return
        if node in finished:
            return
        for neighbor in sorted(graph[node]):
            visit(neighbor, [*trail, node])
        finished.add(node)

    for node in sorted(graph):
        visit(node, [])
    return sorted(cycles)


def spdx_violations(paths: list[Path]) -> list[str]:
    return [
        f"{where(path, 1)}: first line must be {SPDX!r} (ADR-0003)"
        for path in paths
        if not path.read_text(encoding="utf-8").startswith(f"{SPDX}\n")
    ]


def license_problem(pyproject: Path) -> str | None:
    config: dict[str, object] = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = cast("dict[str, object]", config.get("project", {}))
    declared = project.get("license")
    if declared == "GPL-3.0-only":
        return None
    return f"{pyproject.as_posix()}: license = {declared!r}, expected 'GPL-3.0-only' (ADR-0003)"


def long_functions(path: Path, tree: ast.Module) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            length = (node.end_lineno or node.lineno) - node.lineno + 1
            if length > MAX_FUNCTION_LINES:
                limit = f"ceiling {MAX_FUNCTION_LINES}"
                found.append(
                    f"{where(path, node.lineno)}: {node.name}() has {length} lines, {limit}"
                )
    return found


def size_violations(paths: list[Path]) -> list[str]:
    violations: list[str] = []
    for path in paths:
        lines = len(path.read_text(encoding="utf-8").splitlines())
        if lines > MAX_FILE_LINES:
            violations.append(f"{where(path, 1)}: {lines} lines, limit {MAX_FILE_LINES}")
        violations.extend(long_functions(path, parse(path)))
    return violations


def defined_names(tree: ast.Module) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            found.append((node.name, node.lineno))
        elif isinstance(node, ast.arg):
            found.append((node.arg, node.lineno))
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            found.append((node.id, node.lineno))
    return found


def name_violations(paths: list[Path]) -> list[str]:
    return [
        f"{where(path, line)}: vague name {name!r}; say what it holds (AGENTS.md)"
        for path in paths
        for name, line in defined_names(parse(path))
        if name.lower() in BANNED_NAMES
    ]


def attribute_uses(tree: ast.Module) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            found.append((node.attr, node.lineno))
        elif isinstance(node, ast.Import | ast.ImportFrom):
            found.extend((alias.name.split(".")[-1], node.lineno) for alias in node.names)
    return found


def attribute_violations(paths: list[Path]) -> list[str]:
    return [
        f"{where(path, line)}: {name!r} is banned; draw and enlarge in ai_draw (ADR-0002)"
        for path in paths
        for name, line in attribute_uses(parse(path))
        if name in BANNED_ATTRIBUTES
    ]


def python_files(directory: Path) -> list[Path]:
    return sorted(directory.rglob("*.py"))


def make_package(tmp_path: Path, files: dict[str, str]) -> Path:
    package_dir = tmp_path / PACKAGE
    for relative, source in files.items():
        path = package_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text(source, encoding="utf-8")
    return package_dir


def source_paths() -> list[Path]:
    return [path for folder in SOURCE_FOLDERS for path in python_files(folder)]
