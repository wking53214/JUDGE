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
]
TEST_FOLDERS = ["spec/models/user.rb", "specs/a.js", "e2e/login.ts", "cypress/support/commands.js"]
BUILD_FILES = [
    "Cargo.toml", "build.rs", "rust-toolchain.toml", ".cargo/config.toml", "go.mod", "go.work", "pom.xml",
    "build.gradle", "build.gradle.kts", "settings.gradle.kts", "gradle.properties", "Gemfile", "Rakefile", ".rspec",
    "jest.config.js", "vitest.config.ts", "karma.conf.js", "playwright.config.ts", ".mocharc.json", "tsconfig.json",
    "CMakeLists.txt", "meson.build", "justfile", ".gitignore", ".azure-pipelines/ci.yml",
]
ORDINARY = ["web/app.js", "web/App.tsx", "pkg/foo.go", "src/main/java/Foo.java", "lib/foo.rb", "src/parser.rs",
            "lib/foo.ex", "src/Foo.cs", "web/testimony.js", "pkg/protest_utils.go"]


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
