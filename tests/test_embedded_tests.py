"""Tests inside an ordinary source file are held like a test file (0.11.0, was KNOWN DEFECTS 2).

A test file is caught by its name. A test written inside an ordinary source file (a Rust `#[cfg(test)]` module, a
Python doctest, a Vitest in-source test) is not, so before 0.11.0 an edit to `src/lib.rs` beside its tests was ACCEPTed
like any code edit. The Judge now reads each written or replaced code file in the project folder and holds the run for
a named human when the file holds tests of its own.
"""

import pytest
from test_strict_evidence import _d

HOLDS_TESTS = "also holds tests"
UNREAD = "could not be read to check it for tests inside it"

#: (path, text holding a test of its own)
WITH_TESTS = [
    ("src/lib.rs", "pub fn f() {}\n#[cfg(test)]\nmod tests {}\n"),
    ("src/lib.rs", "#[test]\nfn works() {}\n"),
    ("src/lib.rs", "#[tokio::test]\nasync fn works() {}\n"),
    ("src/lib.rs", "/// ```\n/// assert_eq!(f(), 1);\n/// ```\npub fn f() -> i32 { 1 }\n"),
    ("pkg/calc.py", 'def add(a, b):\n    """\n    >>> add(1, 2)\n    3\n    """\n    return a + b\n'),
    ("pkg/calc.py", "def test_add():\n    assert 1 + 1 == 2\n"),
    ("pkg/calc.py", "import unittest\nclass TestAdd(unittest.TestCase):\n    pass\n"),
    ("web/sum.ts", "export const sum = (a: number, b: number) => a + b\nif (import.meta.vitest) {}\n"),
    ("web/sum.js", "Deno.test('sum', () => {})\n"),
    ("lib/calc.ex", 'defmodule Calc do\n  @doc """\n  iex> Calc.add(1, 2)\n  3\n  """\nend\n'),
    ("src/main/java/Foo.java", "import org.junit.jupiter.api.Test;\nclass Foo { @Test void t() {} }\n"),
    ("src/Foo.cs", "public class Foo { [Fact] public void T() {} }\n"),
    ("Sources/Foo.swift", "import XCTest\n"),
    ("src/Foo.php", "<?php class Foo extends \\PHPUnit\\Framework\\TestCase {}\n"),
    ("lib/foo.rb", "require 'minitest/autorun'\nclass FooCheck < Minitest::Test; end\n"),
]

#: (path, ordinary text with no test in it)
WITHOUT_TESTS = [
    ("src/lib.rs", "pub fn f() -> i32 { 1 }\n"),
    ("pkg/calc.py", "def add(a, b):\n    return a + b\n"),
    ("web/sum.ts", "export const sum = (a: number, b: number) => a + b\n"),
    ("lib/calc.ex", "defmodule Calc do\n  def add(a, b), do: a + b\nend\n"),
    ("src/main/java/Foo.java", "class Foo { int f() { return 1; } }\n"),
    ("src/Foo.cs", "public class Foo { public int F() => 1; }\n"),
    ("cmd/main.go", "package main\nfunc TestLooksLikeATest() {}\n"),   # Go tests live only in _test.go files
    ("config/app.yaml", "def test_not_code: true\n"),                  # no marks for an extension with no tests
]


def _write(root, path, text):
    f = root / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


@pytest.mark.parametrize("kind", ["write", "replace"])
@pytest.mark.parametrize(("path", "text"), WITH_TESTS, ids=[f"{p}:{i}" for i, (p, _) in enumerate(WITH_TESTS)])
def test_a_code_file_that_holds_its_own_tests_is_held_for_a_named_human(tmp_path, path, text, kind):
    _write(tmp_path, path, text)
    v = _d(target=str(tmp_path), changed=((path, kind),))
    assert v.decision == "INSUFFICIENT", path
    assert any(HOLDS_TESTS in r and path in r for r in v.reasons), v.reasons


@pytest.mark.parametrize(("path", "text"), WITHOUT_TESTS, ids=[p for p, _ in WITHOUT_TESTS])
def test_a_code_file_with_no_tests_inside_is_still_accepted(tmp_path, path, text):
    _write(tmp_path, path, text)
    v = _d(target=str(tmp_path), changed=((path, "write"),))
    assert v.decision == "ACCEPT", v.reasons


def test_a_deleted_file_is_not_read(tmp_path):
    """It is gone; losing its tests shows in the pass counts, which the Judge compares before and after."""
    assert _d(target=str(tmp_path), changed=(("src/lib.rs", "delete"),)).decision == "ACCEPT"


def test_a_listed_file_that_is_not_in_the_folder_is_not_looked_at(tmp_path):
    """Warden writes the files it lists; hand-made evidence may name one that is not there."""
    assert _d(target=str(tmp_path), changed=(("src/lib.rs", "write"),)).decision == "ACCEPT"


def test_a_listed_file_that_is_there_but_cannot_be_read_is_held(tmp_path):
    (tmp_path / "src" / "lib.rs").mkdir(parents=True)        # a folder where a file should be
    v = _d(target=str(tmp_path), changed=(("src/lib.rs", "write"),))
    assert v.decision == "INSUFFICIENT"
    assert any(UNREAD in r for r in v.reasons), v.reasons


def test_a_file_too_large_to_read_is_held(tmp_path, monkeypatch):
    from judge import seat
    monkeypatch.setattr(seat, "_EMBEDDED_READ_LIMIT", 10)
    _write(tmp_path, "src/lib.rs", "pub fn f() -> i32 { 1 }\n")
    v = _d(target=str(tmp_path), changed=(("src/lib.rs", "write"),))
    assert v.decision == "INSUFFICIENT"
    assert any(UNREAD in r for r in v.reasons), v.reasons


def test_a_file_already_judged_as_a_test_gets_one_reason_not_two(tmp_path):
    _write(tmp_path, "tests/test_a.py", "def test_a():\n    pass\n")
    v = _d(target=str(tmp_path), changed=(("tests/test_a.py", "write"),))
    assert v.decision == "INSUFFICIENT"
    assert not any(HOLDS_TESTS in r for r in v.reasons), v.reasons


def test_prose_is_not_read(tmp_path):
    _write(tmp_path, "docs/guide.md", ">>> add(1, 2)\n3\n")
    assert _d(target=str(tmp_path), scope="all", changed=(("docs/guide.md", "write"),)).decision == "ACCEPT"


def test_harm_still_outranks_the_hold(tmp_path):
    _write(tmp_path, "src/lib.rs", "#[cfg(test)]\nmod tests {}\n")
    v = _d(target=str(tmp_path), scope="documentation", changed=(("src/lib.rs", "write"),))
    assert v.decision == "REJECT"


def test_a_link_inside_the_project_is_read_where_it_lands(tmp_path):
    _write(tmp_path, "src/real.rs", "#[cfg(test)]\nmod tests {}\n")
    (tmp_path / "src" / "alias.rs").symlink_to(tmp_path / "src" / "real.rs")
    v = _d(target=str(tmp_path), changed=(("src/alias.rs", "write"),))
    assert v.decision == "INSUFFICIENT"
    assert any(HOLDS_TESTS in r for r in v.reasons), v.reasons
