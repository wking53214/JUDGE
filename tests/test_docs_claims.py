"""The documents say only what the code does: dependencies, imports and numbers."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
DOCS = {name: (ROOT / name).read_text(encoding="utf-8") for name in ("README.md", "STACK.md")}


def test_no_document_claims_the_judge_imports_or_depends_on_warden_alone():
    for name, text in DOCS.items():
        flat = " ".join(text.split())
        assert "warden.roles" not in flat, name
        assert not re.search(r"depends on Warden[^.]*and (on )?nothing else", flat), name
        assert not re.search(r"imports? Warden's data shapes", flat), name


def test_the_runtime_dependencies_the_readme_names_are_the_real_ones():
    assert [d.split()[0] for d in PYPROJECT["dependencies"]] == ["cns"]
    assert "one runtime dependency is [CNS]" in DOCS["README.md"]


def test_no_document_hardcodes_a_test_count_or_a_pin():
    for name, text in DOCS.items():
        assert not re.search(r"\b\d{2,4} (tests|passed)\b", text), f"{name} states a test count that will drift"
        assert not re.search(r"\b[0-9a-f]{40}\b", text), f"{name} restates a pinned SHA; refer to pyproject.toml instead"
        assert not re.search(r"Warden (tag )?`?v\d+\.\d+\.\d+", text), f"{name} restates a Warden version"


def test_the_exit_codes_are_documented():
    readme = DOCS["README.md"]
    for line in ("| 0 | ACCEPT", "| 1 | Anything else", "| 2 | Usage error"):
        assert line in readme
