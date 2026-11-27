"""The README lists exactly what the Judge recognises as a test, and says plainly what it does not.

The lists in the README section "What counts as a test, exactly" are parsed here and compared with the constants in
``judge/seat.py``, so the README cannot drift from the code. The gap test below documents current behaviour for files of
other languages (a known defect listed in the README); it should fail, and the README be updated, when that changes.
"""

import re
from pathlib import Path

import pytest
from test_strict_evidence import _d, _suite

from judge import seat

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")


def _section() -> str:
    start = README.index("### What counts as a test, exactly")
    end = README.index("\n| module | owns |", start)
    return README[start:end]


def _items(label: str) -> list[str]:
    line = next(x for x in _section().splitlines() if x.startswith(f"- {label}"))
    return re.findall(r"`([^`]+)`", line)


def test_the_readme_lists_the_folders_the_code_recognises():
    assert set(_items("Folders")) == set(seat._JUDGING_DIRS)


def test_the_readme_lists_the_file_names_the_code_recognises():
    assert set(_items("File names")) == set(seat._JUDGING_NAMES)


def test_the_readme_lists_the_file_name_patterns_the_code_recognises():
    assert _items("File name patterns") == [p.pattern for p in seat._JUDGING_PATTERNS]


def test_the_readme_lists_the_outside_folders_and_prose_endings_the_code_uses():
    assert set(_items("Outside the project")) == set(seat._OUTSIDE_DIRS)
    assert tuple(_items("Prose")) == seat._PROSE


@pytest.mark.parametrize("name", sorted(seat._JUDGING_NAMES))
def test_every_file_name_the_readme_lists_is_rejected_when_edited(name):
    v = _d(changed=((f"pkg/{name}", "write"),))
    assert v.decision == "INSUFFICIENT", name


@pytest.mark.parametrize("folder", sorted(seat._JUDGING_DIRS))
def test_every_folder_the_readme_lists_is_rejected_when_edited(folder):
    v = _d(changed=((f"{folder}/x.dat", "write"),))
    assert v.decision == "INSUFFICIENT", folder


@pytest.mark.parametrize("path", [
    "web/app.test.js", "web/app.spec.ts", "pkg/foo_test.go", "src/FooTest.java", "spec/foo_spec.rb",
    "Cargo.toml", ".gitignore",
])
def test_files_of_other_languages_are_held_as_the_readme_says(path):
    """Was a KNOWN DEFECT (0.9.0: ACCEPT). Since 0.10.0 these are held for a named human, with or without skips."""
    v = _d(changed=((path, "write"),))
    assert v.decision == "INSUFFICIENT", path


def test_a_test_inside_an_ordinary_source_file_is_not_recognised_as_the_readme_says():
    """KNOWN DEFECTS 2: src/lib.rs may hold a #[cfg(test)] module, and the Judge reads names, not code."""
    assert _d(changed=(("src/lib.rs", "write"),)).decision == "ACCEPT"


def test_setup_cfg_is_rejected_as_the_readme_says():
    assert _d(changed=(("setup.cfg", "write"),)).decision == "INSUFFICIENT"


def test_a_java_test_in_a_test_folder_is_rejected_as_the_readme_says():
    assert _d(changed=(("src/test/java/FooTest.java", "write"),)).decision == "INSUFFICIENT"


def test_the_skipped_tests_rule_holds_a_change_to_any_file_that_is_not_prose():
    """0.9.0 looked only at .py files, so pkg/a.js went free."""
    for path in ("pkg/a.py", "pkg/a.js", "src/lib.rs", "cmd/main.go", "config/app.yaml"):
        v = _d(suite_before=_suite(skipped=1), suite_after=_suite(skipped=1), changed=((path, "write"),))
        assert v.decision == "INSUFFICIENT", path
    prose = _d(suite_before=_suite(skipped=1), suite_after=_suite(skipped=1), changed=(("docs/guide.md", "write"),))
    assert prose.decision == "ACCEPT"
