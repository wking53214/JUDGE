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
MISSING_FILE = "is listed but is not in the project folder"

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
    # 0.14.0
    ("src/parser.cc", "#include <gtest/gtest.h>\nint f() { return 1; }\n"),
    ("src/parser.cpp", "int f() { return 1; }\nTEST(Parser, Works) { EXPECT_EQ(f(), 1); }\n"),
    ("src/parser.cpp", "#include \"doctest.h\"\nint f() { return 1; }\nTEST_CASE(\"f\") { CHECK(f() == 1); }\n"),
    ("src/parser.c", "#include <cmocka.h>\n"),
    ("include/parser.hpp", "#include <catch2/catch_test_macros.hpp>\n"),
    ("Sources/Foo.m", "@import XCTest;\n"),
    ("src/main.zig", "pub fn add(a: i32, b: i32) i32 { return a + b; }\ntest \"add\" {\n}\n"),
    ("src/main.zig", "test {\n    _ = @import(\"x.zig\");\n}\n"),
    ("source/app.d", "int add(int a, int b) { return a + b; }\nunittest { assert(add(1, 2) == 3); }\n"),
    ("src/Lib.hs", "-- | Adds.\n--\n-- >>> add 1 2\n-- 3\nadd a b = a + b\n"),
    ("src/Lib.hs", "import Test.Hspec\n"),
    ("src/Model.jl", "using Test\n@testset \"m\" begin\n    @test 1 == 1\nend\n"),
    ("R/model.R", "library(testthat)\ntest_that(\"m\", { expect_true(TRUE) })\n"),
    ("src/util.lua", "local busted = require 'busted'\n"),
    ("lib/app.dart", "import 'package:test/test.dart';\n"),
    ("src/app.nim", "import std/unittest\n"),
    ("src/app.nim", "proc add*(a, b: int): int =\n  runnableExamples:\n    assert add(1, 2) == 3\n  a + b\n"),
    # 0.17.0: one entry for each new mark
    ("src/solver.f90", "module solver_tests\n  @Test\n  subroutine test_add()\n  end subroutine\nend module\n"),
    ("src/solver.F90", "program t\n  use PFUNIT\nend program\n"),
    ("lib/parser.ml", "let add a b = a + b\nlet%test \"add\" = add 1 2 = 3\n"),
    ("lib/parser.ml", "open Alcotest\n"),
    ("lib/parser.ml", "(* preprocess (pps ppx_inline_test) *)\n"),
    ("src/Parser.fs", "module Parser\n[<Fact>]\nlet ``adds`` () = ()\n"),
    ("src/Parser.fs", "open Expecto\n"),
    ("src/app/core.clj", "(ns app.core (:require [clojure.test :refer :all]))\n"),
    ("src/app/core.cljs", "(ns app.core (:require [cljs.test :refer-macros [is]]))\n"),
    ("src/app/core.cljc", "(deftest adds (is (= 3 (+ 1 2))))\n"),
    ("src/app/core.clj", "(with-test (defn add [a b] (+ a b)) (is (= 3 (add 1 2))))\n"),
    ("src/calc.erl", "-module(calc).\n-include_lib(\"eunit/include/eunit.hrl\").\n"),
    ("src/calc.erl", "-module(calc).\n-include_lib(\"common_test/include/ct.hrl\").\n"),
    ("src/calc.erl", "-module(calc).\n-include_lib(\"proper/include/proper.hrl\").\n"),
    ("src/calc.erl", "-module(calc).\nadd_test() -> 3 = add(1, 2).\n"),
    ("lib/Calc.pm", "package Calc;\nuse Test::More;\n"),
    ("bin/run.pl", "use Test2::V0;\n"),
    ("src/calc.cr", "require \"spec\"\n"),
    ("src/calc.adb", "with AUnit.Assertions;\n"),
    ("src/calc.ads", "with Ahven.Framework;\n"),
    ("scripts/run.sh", "#!/bin/sh\n. shunit2\n"),
    ("scripts/run.bash", "@test \"adds\" {\n  run add 1 2\n}\n"),
    ("scripts/run.sh", "load 'test_helper/bats-assert/load'\n"),
    ("src/Calc.ps1", "Import-Module Pester\n"),
    ("src/Calc.psm1", "Describe 'Calc' {\n  It 'adds' { 3 | Should -Be 3 }\n}\n"),
    # 0.18.0: one entry for each new mark
    ("src/Parser.elm", "module Parser exposing (add)\nimport Expect\n"),
    ("src/Parser.elm", "{-| Adds.\n\n    add 1 2 --> 3\n\n-}\nadd a b = a + b\n"),
    ("src/parser.gleam", "import gleeunit\n"),
    ("src/parser.rkt", "#lang racket\n(define (add a b) (+ a b))\n(module+ test\n  (check-equal? (add 1 2) 3))\n"),
    ("src/parser.rkt", "#lang racket\n(require rackunit)\n"),
    ("src/parser.scm", "(import (srfi 64))\n"),
    ("src/parser.scm", "(test-begin \"parser\")\n"),
    ("src/parser.ss", "(import (chicken base) test)\n"),
    ("src/parser.lisp", "(ql:quickload :fiveam)\n"),
    ("src/parser.lisp", "(defpackage parser (:use :cl :rove))\n"),
    ("src/parser.lisp", "(deftest adds (ok (= 3 (+ 1 2))))\n"),
    ("src/parser.lisp", "(test adds (is (= 3 (+ 1 2))))\n"),
    ("src/calc.pl", ":- begin_tests(calc).\n"),
    ("src/calc.pro", ":- use_module(library(plunit)).\n"),
    ("src/Calc.pas", "unit Calc;\nuses fpcunit, testregistry;\n"),
    ("src/Calc.pas", "type TCalcCheck = class(TTestCase)\n"),
    ("src/calc.tcl", "package require tcltest\n"),
    ("src/Calc.vb", "<TestMethod()>\nPublic Sub Adds()\nEnd Sub\n"),
    ("src/Calc.vb", "Imports NUnit.Framework\n"),
    ("src/Module1.bas", "'@TestModule\nOption Explicit\n"),
    ("src/calc.cbl", "       COPY \"mfunit.cpy\".\n"),
    ("src/calc.cob", "       entry MFU-TC-PREFIX & \"Adds\".\n"),
    ("src/calc.cbl", "           CALL 'AZUTCINI' USING TC-NAME\n"),
]

#: (path, ordinary text with no test in it)
WITHOUT_TESTS = [
    ("src/lib.rs", "pub fn f() -> i32 { 1 }\n"),
    ("pkg/calc.py", "def add(a, b):\n    return a + b\n"),
    ("web/sum.ts", "export const sum = (a: number, b: number) => a + b\n"),
    ("lib/calc.ex", "defmodule Calc do\n  def add(a, b), do: a + b\nend\n"),
    ("src/main/java/Foo.java", "class Foo { int f() { return 1; } }\n"),
    ("src/Foo.cs", "public class Foo { public int F() => 1; }\n"),
    ("cmd/main.go", "package main\nfunc TestLooksLikeATest() {}\n"),
    ("src/parser.cpp", "int test_value = 1;\nint f() { return test_value; }\n"),
    ("src/main.zig", "const testing = 1;\npub fn f() i32 { return testing; }\n"),
    ("source/app.d", "int add(int a, int b) { return a + b; }\n"),
    ("src/Lib.hs", "-- | Adds.\nadd a b = a + b\n"),
    ("src/Model.jl", "f(x) = x + 1\n"),
    ("R/model.R", "f <- function(x) x + 1\n"),
    ("src/util.lua", "local M = {}\nreturn M\n"),
    ("lib/app.dart", "int add(int a, int b) => a + b;\n"),
    ("src/app.nim", "proc add*(a, b: int): int = a + b\n"),   # Go tests live only in _test.go files
    # 0.17.0
    ("src/solver.f90", "module solver\ncontains\n  subroutine add()\n  end subroutine\nend module\n"),
    ("lib/parser.ml", "let add a b = a + b\n"),
    ("src/Parser.fs", "module Parser\nlet add a b = a + b\n"),
    ("src/app/core.clj", "(ns app.core)\n(defn add [a b] (+ a b))\n"),
    ("src/calc.erl", "-module(calc).\nadd(A, B) -> A + B.\n"),
    ("lib/Calc.pm", "package Calc;\nsub add { $_[0] + $_[1] }\n1;\n"),
    ("src/calc.cr", "def add(a, b)\n  a + b\nend\n"),
    ("src/calc.adb", "package body Calc is\nend Calc;\n"),
    ("scripts/run.sh", "#!/bin/sh\necho testing\n"),
    ("src/Calc.ps1", "function Add($a, $b) { $a + $b }\n"),
    # 0.18.0
    ("src/Parser.elm", "module Parser exposing (add)\nadd a b = a + b\n"),
    ("src/parser.gleam", "pub fn add(a, b) { a + b }\n"),
    ("src/parser.rkt", "#lang racket\n(define (add a b) (+ a b))\n"),
    ("src/parser.scm", "(import (scheme base))\n(define (add a b) (+ a b))\n"),
    ("src/parser.lisp", "(defun add (a b) (+ a b))\n"),
    ("src/calc.pl", "add(A, B, C) :- C is A + B.\n"),
    ("src/Calc.pas", "unit Calc;\ninterface\nfunction Add(a, b: Integer): Integer;\n"),
    ("src/calc.tcl", "proc add {a b} { expr {$a + $b} }\n"),
    ("src/Calc.vb", "Public Module Calc\nEnd Module\n"),
    ("src/Module1.bas", "Public Function Add(a, b)\nEnd Function\n"),
    ("src/calc.cbl", "       IDENTIFICATION DIVISION.\n       PROGRAM-ID. CALC.\n"),
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


@pytest.mark.parametrize("kind", ["write", "replace"])
def test_a_listed_code_file_that_is_not_in_the_folder_is_held(tmp_path, kind):
    """The owner's ruling of 2026-11-27 (0.13.0): it could not be checked for tests inside it, so it is unknown.
    Up to 0.12.0 it was skipped. Real Warden writes the files it lists; hand-made evidence may name one that is not there."""
    v = _d(target=str(tmp_path), changed=(("src/lib.rs", kind),))
    assert v.decision == "INSUFFICIENT"
    assert any(MISSING_FILE in r and "src/lib.rs" in r for r in v.reasons), v.reasons


def test_a_listed_file_with_no_test_marks_for_its_kind_is_not_looked_for(tmp_path):
    """Only files the test-mark check would read are held when missing; a missing prose file is not."""
    v = _d(target=str(tmp_path), scope="all", changed=(("docs/guide.md", "write"),))
    assert v.decision == "ACCEPT", v.reasons


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
