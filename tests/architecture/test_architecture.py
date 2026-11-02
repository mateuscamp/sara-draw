# SPDX-License-Identifier: GPL-3.0-only
"""Fitness functions: each test checks a decision in docs/adr/, not drawing behavior.

A failure here means the architecture was crossed, not that a feature broke. Every rule is
first shown catching a violation planted in a throwaway tree, then run on the real package:
a rule never seen failing could be passing because it checks nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import settings

from architecture_rules import (
    MAX_FILE_LINES,
    MAX_FUNCTION_LINES,
    PACKAGE_DIR,
    ROOT,
    attribute_violations,
    cycle_violations,
    import_violations,
    io_only_violations,
    license_problem,
    make_package,
    name_violations,
    python_files,
    size_violations,
    source_paths,
    spdx_violations,
    stray_configs,
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


@pytest.mark.parametrize(
    "name", ["pyrightconfig.json", "pytest.ini", "src/ai_draw/pixel/.ruff.toml"]
)
def test_stray_tool_config_is_flagged(tmp_path: Path, name: str) -> None:
    planted = tmp_path / name
    planted.parent.mkdir(parents=True, exist_ok=True)
    _ = planted.write_text("", encoding="utf-8")
    assert stray_configs(tmp_path) == [name]


def test_tools_read_their_settings_only_from_pyproject() -> None:
    assert stray_configs(ROOT) == []


def test_source_rule_sees_python_files_anywhere_in_the_repository(tmp_path: Path) -> None:
    # Regression (audit M9, 01/11): a .py at the root or in a new folder escaped SPDX and size.
    for relative in ("loose.py", "tools/make.py", ".venv/lib.py", "notes/private.py"):
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        _ = (tmp_path / relative).write_text("", encoding="utf-8")
    found = [path.relative_to(tmp_path).as_posix() for path in source_paths(tmp_path)]
    assert found == ["loose.py", "tools/make.py"]


def test_attribute_rule_flags_pillow_imageops(tmp_path: Path) -> None:
    source = "from PIL import ImageOps\n\nbig = ImageOps.scale(picture, 4)\n"
    package_dir = make_package(tmp_path, {"io/png.py": source})
    assert len(attribute_violations(python_files(package_dir))) == 2


def test_io_rule_flags_disk_and_dynamic_import_outside_io(tmp_path: Path) -> None:
    source = (
        "import importlib\n\n"
        "text = open('a').read()\n"
        "_ = path.write_text(text)\n"
        "module = importlib.import_module('x')\n"
        "other = __import__('y')\n"
    )
    package_dir = make_package(tmp_path, {"pixel/x.py": source, "io/y.py": source})
    found = io_only_violations(package_dir)
    assert len(found) == 4
    assert all("pixel/x.py" in line for line in found)


def test_only_io_touches_disk_or_imports_by_name() -> None:
    assert io_only_violations(PACKAGE_DIR) == []


def test_name_rule_flags_attributes_aliases_and_caught_errors(tmp_path: Path) -> None:
    # Regression (audit M9, 01/11): these three forms of naming escaped the rule.
    source = (
        "import json as data\n\n"
        "class Box:\n"
        "    def __init__(self) -> None:\n"
        "        self.info = 1\n\n"
        "try:\n    pass\nexcept ValueError as obj:\n    pass\n"
    )
    package_dir = make_package(tmp_path, {"grid/box.py": source})
    assert len(name_violations(python_files(package_dir))) == 3


def test_io_rule_flags_the_other_common_ways_to_touch_disk(tmp_path: Path) -> None:
    # Regression (review of M9, 01/11): these forms escaped the first list of names.
    source = (
        "from importlib import import_module\n\n"
        "module = import_module('x')\n"
        "handle = path.open('w')\n"
        "path.touch()\n"
        "os.remove(path)\n"
        "shutil.rmtree(path)\n"
        "np.save(path, array)\n"
    )
    package_dir = make_package(tmp_path, {"grid/x.py": source})
    assert len(io_only_violations(package_dir)) == 6


def test_property_tests_run_the_same_examples_and_keep_none() -> None:
    # ADR-0006: the profile in tests/conftest.py draws the same examples on every machine and
    # saves none between runs.
    active = settings.default
    assert active is not None
    assert active.derandomize
    assert active.database is None
