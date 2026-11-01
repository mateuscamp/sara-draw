# SPDX-License-Identifier: GPL-3.0-only
"""Fitness functions: each test checks a decision in docs/adr/, not drawing behavior.

A failure here means the architecture was crossed, not that a feature broke. Every rule is
first shown catching a violation planted in a throwaway tree, then run on the real package:
a rule never seen failing could be passing because it checks nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from architecture_rules import (
    MAX_FILE_LINES,
    MAX_FUNCTION_LINES,
    PACKAGE_DIR,
    ROOT,
    attribute_violations,
    cycle_violations,
    import_violations,
    license_problem,
    make_package,
    name_violations,
    python_files,
    size_violations,
    source_paths,
    spdx_violations,
)

if TYPE_CHECKING:
    from pathlib import Path


# --- layers (ADR-0001, ADR-0002) -------------------------------------------------------


def test_import_rule_flags_layer_crossing(tmp_path: Path) -> None:
    package_dir = make_package(
        tmp_path, {"geometry/path.py": "import ai_draw.grid.canvas\n", "grid/canvas.py": ""}
    )
    violations = import_violations(package_dir)
    assert len(violations) == 1
    assert "geometry/path.py:1" in violations[0]


def test_import_rule_flags_pillow_outside_io(tmp_path: Path) -> None:
    package_dir = make_package(tmp_path, {"pixel/fill.py": "import math\nfrom PIL import Image\n"})
    violations = import_violations(package_dir)
    assert len(violations) == 1
    assert "pixel/fill.py:2" in violations[0]
    assert "PIL" in violations[0]


def test_import_rule_flags_test_only_package_in_src(tmp_path: Path) -> None:
    package_dir = make_package(tmp_path, {"smooth/coverage.py": "import fontTools.pens\n"})
    assert len(import_violations(package_dir)) == 1


def test_import_rule_flags_relative_import(tmp_path: Path) -> None:
    package_dir = make_package(tmp_path, {"pixel/line.py": "from ..smooth import coverage\n"})
    assert len(import_violations(package_dir)) == 1


def test_import_rule_flags_layer_missing_from_table(tmp_path: Path) -> None:
    package_dir = make_package(tmp_path, {"vector/shape.py": "import math\n"})
    violations = import_violations(package_dir)
    assert len(violations) == 1
    assert "vector" in violations[0]


def test_import_rule_accepts_allowed_imports(tmp_path: Path) -> None:
    package_dir = make_package(
        tmp_path,
        {
            "pixel/fill.py": "import math\nimport numpy as np\nfrom ai_draw.geometry import path\n",
            "io/png.py": "from PIL import Image\nimport ai_draw.grid.canvas\n",
            "cli.py": "from __future__ import annotations\nimport ai_draw.io.png\n",
        },
    )
    assert import_violations(package_dir) == []


def test_package_layers_hold() -> None:
    assert import_violations(PACKAGE_DIR) == []


def test_cycle_rule_flags_cycle(tmp_path: Path) -> None:
    package_dir = make_package(
        tmp_path,
        {
            "grid/canvas.py": "import ai_draw.grid.rows\n",
            "grid/rows.py": "import ai_draw.grid.canvas\n",
        },
    )
    violations = cycle_violations(package_dir)
    assert len(violations) == 1
    assert "ai_draw.grid.canvas" in violations[0]


def test_package_has_no_import_cycle() -> None:
    assert cycle_violations(PACKAGE_DIR) == []


# --- license (ADR-0003) ----------------------------------------------------------------


def test_spdx_rule_flags_missing_header(tmp_path: Path) -> None:
    package_dir = make_package(tmp_path, {"grid/canvas.py": '"""No header."""\n'})
    assert len(spdx_violations(python_files(package_dir))) == 1


def test_every_python_file_starts_with_spdx_header() -> None:
    assert spdx_violations(source_paths()) == []


def test_license_rule_flags_other_license(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    _ = pyproject.write_text('[project]\nname = "x"\nlicense = "MIT"\n', encoding="utf-8")
    assert license_problem(pyproject) is not None


def test_pyproject_declares_gpl3_only() -> None:
    assert license_problem(ROOT / "pyproject.toml") is None


# --- readability for agents (AGENTS.md) ------------------------------------------------


def test_size_rule_flags_long_function(tmp_path: Path) -> None:
    body = "".join(f"    x{n} = {n}\n" for n in range(MAX_FUNCTION_LINES))
    package_dir = make_package(tmp_path, {"grid/canvas.py": f"def long() -> None:\n{body}"})
    violations = size_violations(python_files(package_dir))
    assert len(violations) == 1
    assert "long()" in violations[0]


def test_size_rule_flags_long_file(tmp_path: Path) -> None:
    source = "".join(f"x{n} = {n}\n" for n in range(MAX_FILE_LINES + 1))
    package_dir = make_package(tmp_path, {"grid/canvas.py": source})
    assert len(size_violations(python_files(package_dir))) == 1


def test_sources_fit_size_limits() -> None:
    assert size_violations(source_paths()) == []


def test_name_rule_flags_vague_names(tmp_path: Path) -> None:
    source = "data = 1\n\ndef handler(item: int) -> int:\n    return item\n\nbase_color = 2\n"
    package_dir = make_package(tmp_path, {"grid/canvas.py": source})
    violations = name_violations(python_files(package_dir))
    assert len(violations) == 3
    assert not any("base_color" in violation for violation in violations)


def test_package_avoids_vague_names() -> None:
    assert name_violations(python_files(PACKAGE_DIR)) == []


def test_attribute_rule_flags_pillow_drawing(tmp_path: Path) -> None:
    source = "from PIL import ImageDraw\n\ndef grow(img):\n    return img.resize((2, 2))\n"
    package_dir = make_package(tmp_path, {"io/png.py": source})
    assert len(attribute_violations(python_files(package_dir))) == 2


def test_package_avoids_pillow_drawing() -> None:
    assert attribute_violations(python_files(PACKAGE_DIR)) == []


def test_every_layer_may_import_errors(tmp_path: Path) -> None:
    package_dir = make_package(
        tmp_path,
        {
            "errors/__init__.py": "",
            "pixel/fill.py": "from ai_draw.errors import SettingError\n",
            "grid/canvas.py": "import ai_draw.errors\n",
        },
    )
    assert import_violations(package_dir) == []


def test_errors_imports_no_other_layer(tmp_path: Path) -> None:
    package_dir = make_package(tmp_path, {"errors/__init__.py": "import ai_draw.grid.canvas\n"})
    violations = import_violations(package_dir)
    assert len(violations) == 1
    assert "imports 'ai_draw.grid.canvas'" in violations[0]
