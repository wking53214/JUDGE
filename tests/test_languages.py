"""Test files, folders and build files of other languages are held like Python's (0.10.0, was KNOWN DEFECTS 2).

Up to 0.9.0 the Judge recognised Python's test conventions only, and its "some tests did not run" rule looked only at
`.py` files. A repository in another language could change its tests, or change code while tests were skipped, and be
ACCEPTed. For each language there is a path that is now held, the shape of a path that is still ordinary code, and the
skipped-tests rule applied to it.
"""

import pytest
from test_strict_evidence import _d, _suite

HELD = "tests or test settings were changed"

TEST_FILES = [
    "web/app.test.js", "web/App.test.jsx", "web/app.spec.ts", "web/app.spec.tsx", "lib/util.test.mjs",
    "pkg/foo_test.go",
    "src/main/java/FooTest.java", "src/FooTests.java", "app/FooTest.kt", "src/FooSpecTest.scala",
    "Lib/FooTests.cs", "Sources/FooTests.swift", "src/FooTest.php",
    "lib/foo_spec.rb", "lib/foo_test.rb",
    "src/parser_test.rs", "src/tests.rs",
    "lib/foo_test.exs",
    # 0.14.0
    "src/parser_test.cc", "src/parser_unittest.cpp", "src/FooTest.cpp", "src/foo_test.c", "Tests/FooTests.m",
    "test/widget_test.dart", "test/FooSpec.hs", "src/FooSpec.hs", "tests/testthat/test-model.R", "R/test-model.R",
    "src/foo_spec.lua",
    # 0.17.0
    "src/solver_test.f90", "src/solver_tests.F90", "src/solver.pf", "lib/parser_test.ml",
    "lib/parser_tests.mli", "src/ParserTests.fs", "src/ParserTest.fsx", "src/app/core_test.clj",
    "src/app/core_test.cljs", "src/app/core_test.cljc", "src/calc_tests.erl", "src/calc_test.erl", "src/calc_SUITE.erl",
    "t/basic.t", "src/calc_spec.cr", "src/calc_test.v", "src/calc-test.adb", "src/calc_tests.ads", "src/calc.cut",
    "scripts/install.bats", "src/Calc.Tests.ps1",
    # 0.18.0
    "src/ParserTest.elm", "src/ParserTests.elm", "src/parser_test.gleam", "src/parser-test.rkt", "src/parser_tests.scm",
    "src/parser-test.ss", "src/parser_test.sld", "src/parser-tests.sls", "src/parser-tests.lisp", "src/parser-test.lsp",
    "src/parser_test.cl", "src/test-parser.rkt", "src/tests-parser.scm", "src/test-parser.lisp", "src/calc.plt",
    "src/CalcTests.pas", "src/CalcTest.pp", "src/CalcTests.dpr", "src/CalcTests.lpr", "src/calc.test",
    "src/CalcTests.vb",
    # 0.19.0, found by the outside check
    "modules/json/json.testsuite", "modules/struct/matrix.testsupport",
    "modules/math/calculus.testscript", "modules/htmlparse/htmlparse.tree_testsuite", "modules/base64/yencode.test.data",
    "modules/base64/yencode.test.out", "build/test.tcl", "clients/mail-test.tcl",
]
TEST_FOLDERS = ["spec/models/user.rb", "specs/a.js", "e2e/login.ts", "cypress/support/commands.js",
                # 0.19.0, folder shapes found by the outside check of 2026-11-28
                "HashLib.Tests/src/Utils/Loader.pas", "HashLib.Tests/Data/Crypto/Vectors.csv",
                "src/PrimeService.Tests/Helpers.vb", "core-tests/src/Main.java", "pkg/unit_test/a.go",
                "modules/png/test-assets/basn0g01.png", "lib/test_helpers/util.rb", "tests.d/run.sh"]
BUILD_FILES = [
    "Cargo.toml", "build.rs", "rust-toolchain.toml", ".cargo/config.toml", "go.mod", "go.work", "pom.xml",
    "build.gradle", "build.gradle.kts", "settings.gradle.kts", "gradle.properties", "Gemfile", "Rakefile", ".rspec",
    "jest.config.js", "vitest.config.ts", "karma.conf.js", "playwright.config.ts", ".mocharc.json", "tsconfig.json",
    "CMakeLists.txt", "meson.build", "justfile", ".gitignore", ".azure-pipelines/ci.yml",
    # 0.14.0
    "build.zig", "build.zig.zon", "dub.json", "dub.sdl", "pubspec.yaml", "foo.cabal", "cabal.project", "stack.yaml",
    "package.yaml", "Project.toml", "Manifest.toml", "DESCRIPTION", ".busted", "foo-1.0-1.rockspec", "foo.nimble",
    "conanfile.txt", "conanfile.py", "vcpkg.json", "CMakePresets.json",
    # 0.17.0
    "fpm.toml", "dune", "src/dune", "dune-project", "foo.opam", "Directory.Build.props", "Directory.Build.targets",
    "Directory.Packages.props", "global.json", "src/App/App.csproj", "src/App/App.fsproj", "src/App/App.vbproj",
    "App.sln", "project.clj", "deps.edn", "shadow-cljs.edn", "bb.edn", "tests.edn", "rebar.config", "erlang.mk",
    "mix.exs", "Makefile.PL", "Build.PL", "cpanfile", "dist.ini", "shard.yml", "v.mod", "alire.toml", "calc.gpr",
    # 0.18.0
    "elm.json", "elm-verify-examples.json", "gleam.toml", "info.rkt", "Akku.manifest", "pack.pl", "fpmake.pp",
    "all.tcl", "calc.egg", "calc.asd", "Calc.lpi", "Calc.lpk", "Calc.dproj", "Calc.dpk", "AZUCF001.bzucfg",
    "calc.mfu", "elm-tooling.json",  # elm-tooling.json: 0.19.0
]
ORDINARY = ["web/app.js", "web/App.tsx", "pkg/foo.go", "src/main/java/Foo.java", "lib/foo.rb", "src/parser.rs",
            "lib/foo.ex", "src/Foo.cs", "web/testimony.js", "pkg/protest_utils.go",
            # 0.14.0
            "src/parser.c", "src/parser.cpp", "include/parser.h", "src/main.zig", "source/app.d", "lib/app.dart",
            "src/Lib.hs", "src/Model.jl", "R/model.R", "src/util.lua", "src/app.nim",
            # 0.17.0
            "src/solver.f90", "lib/parser.ml", "src/Parser.fs", "src/app/core.clj", "src/calc.erl", "lib/Calc.pm",
            "bin/run.pl", "src/calc.cr", "src/calc.v", "src/calc.adb", "src/calc.cbl", "scripts/run.sh", "src/Calc.ps1",
            "src/protest.erl",
            # 0.18.0
            "src/Parser.elm", "src/parser.gleam", "src/parser.rkt", "src/parser.scm", "src/parser.lisp", "src/calc.pl",
            "src/Calc.pas", "src/calc.tcl", "src/Calc.vb", "src/Module1.bas", "src/calc.cob", "src/attest.rkt",
            # 0.19.0
            "lib/latest/a.c", "src/contest/a.c", "src/attestation/a.go", "src/testimony.tcl"]


@pytest.mark.parametrize("path", TEST_FILES + TEST_FOLDERS + BUILD_FILES)
def test_a_test_or_build_file_of_another_language_is_held_for_a_named_human(path):
    """0.9.0: ACCEPT for every one of these with scope code and a green suite."""
    v = _d(changed=((path, "write"),))
    assert v.decision == "INSUFFICIENT", path
    assert any(HELD in r for r in v.reasons), v.reasons


@pytest.mark.parametrize("path", ORDINARY)
def test_ordinary_source_of_another_language_is_still_accepted(path):
    assert _d(changed=((path, "write"),)).decision == "ACCEPT", path


@pytest.mark.parametrize("path", ORDINARY)
def test_a_change_to_any_code_file_is_held_when_tests_did_not_run(path):
    """0.9.0 held this only for .py files."""
    v = _d(changed=((path, "write"),), suite_before=_suite(skipped=1), suite_after=_suite(skipped=1))
    assert v.decision == "INSUFFICIENT", path
    assert any("some tests did not run" in r for r in v.reasons)


@pytest.mark.parametrize("path", ["README.md", "docs/guide.rst", "NOTES.txt"])
def test_prose_with_skipped_tests_is_still_accepted(path):
    assert _d(changed=((path, "write"),), suite_before=_suite(skipped=1), suite_after=_suite(skipped=1),
              scope="documentation").decision == "ACCEPT"


def test_a_name_that_only_looks_like_a_test_is_held_rather_than_waved_through():
    """`latest.java` ends in `test.java`: the patterns err towards holding, as the README says."""
    assert _d(changed=(("src/Latest.java", "write"),)).decision == "INSUFFICIENT"


def test_harm_still_outranks_the_hold():
    v = _d(changed=(("pkg/foo_test.go", "write"),), suite_after=_suite(failed=1))
    assert v.decision == "REJECT"
