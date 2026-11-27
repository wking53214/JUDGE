"""A Rust edit that leaves the file's tests as they were in the last commit is not held (0.15.0, was KNOWN DEFECTS 2).

Most Rust files keep a `#[cfg(test)] mod tests` at the end, so since 0.11.0 nearly every Rust edit was held for a named
human: the file holds tests, and an edit to it may change them. Now the Judge reads the file as it was in the project's
last commit and compares the test module (from its `#[cfg(test)]` line to the end) and every doc comment. When both are
exactly as they were, and no changed code line mentions "test", the edit is ordinary code. Anything it cannot compare
keeps the hold.
"""

import os
import shutil
import subprocess

import pytest
from test_strict_evidence import _d

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="these tests build repositories with git")

HOLDS_TESTS = "also holds tests"

LIB = """/// Adds one.
///
/// ```
/// assert_eq!(mylib::inc(1), 2);
/// ```
pub fn inc(x: i32) -> i32 {
    x + 1
}

pub fn latest() -> i32 {
    7
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn inc_works() {
        assert_eq!(inc(1), 2);
    }
}
"""


def _git(cwd, *args):
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "-c", "init.defaultBranch=main", "-c", "commit.gpgsign=false", *args], cwd=cwd, env=env,
                   check=True, capture_output=True)


def _project(tmp_path, text=LIB, path="src/lib.rs"):
    root = tmp_path / "p"
    (root / path).parent.mkdir(parents=True)
    (root / path).write_text(text)
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "start")
    return root


def _edit(root, old, new, path="src/lib.rs"):
    f = root / path
    text = f.read_text()
    assert old in text, old
    f.write_text(text.replace(old, new, 1))
    return _d(target=str(root), changed=((path, "replace"),))


def _held(v):
    return v.decision == "INSUFFICIENT" and any(HOLDS_TESTS in r for r in v.reasons)


# ---- released -----------------------------------------------------------------------------------------------------------

def test_an_edit_above_an_unchanged_test_module_is_accepted(tmp_path):
    root = _project(tmp_path)
    v = _edit(root, "    x + 1\n", "    1 + x\n")
    assert v.decision == "ACCEPT", v.reasons


def test_a_changed_line_with_test_inside_a_word_is_held_which_errs_towards_holding(tmp_path):
    """The check is on the letters, not on meaning: renaming `latest` changes a line that holds them."""
    root = _project(tmp_path)
    assert _held(_edit(root, "pub fn latest()", "pub fn latest_value()"))


def test_an_edit_inside_a_function_whose_name_holds_test_is_accepted_when_that_line_is_unchanged(tmp_path):
    root = _project(tmp_path)
    v = _edit(root, "    7\n", "    8\n")
    assert v.decision == "ACCEPT", v.reasons


# ---- kept held ----------------------------------------------------------------------------------------------------------

def test_an_edit_inside_the_test_module_is_held(tmp_path):
    root = _project(tmp_path)
    assert _held(_edit(root, "assert_eq!(inc(1), 2);\n    }", "assert!(true);\n    }"))


def test_an_edit_to_a_doc_test_is_held(tmp_path):
    root = _project(tmp_path)
    assert _held(_edit(root, "/// assert_eq!(mylib::inc(1), 2);", "/// assert!(true);"))


def test_removing_the_test_module_is_held(tmp_path):
    root = _project(tmp_path)
    f = root / "src/lib.rs"
    f.write_text(LIB.split("#[cfg(test)]")[0] + "#[cfg(test)]\nmod tests {}\n")
    assert _held(_d(target=str(root), changed=(("src/lib.rs", "replace"),)))


@pytest.mark.parametrize("added", [
    "#![cfg_attr(test, allow(dead_code))]\n",   # an attribute that changes how tests build
    "mod tests_extra;\n",                        # a pointer to more tests elsewhere
    "my_test_macro! {}\n",                       # a macro that may make tests
])
def test_a_changed_code_line_that_mentions_test_is_held(tmp_path, added):
    root = _project(tmp_path)
    assert _held(_edit(root, "pub fn inc", added + "pub fn inc"))


@pytest.mark.parametrize("item", [
    "#[tokio::test]\nasync fn t() {}\n",
    "#[rstest]\nfn t() {}\n",
    "#[test_case(1)]\nfn t(x: i32) {}\n",
    "proptest! {\n}\n",
    "quickcheck! {\n}\n",
    "/** Block docs.\n```\nassert!(true);\n``` */\npub fn g() {}\n",
    "#[doc = \"x\"]\npub fn g() {}\n",
    "include!(\"more.rs\");\n",
])
def test_a_test_or_doc_form_above_the_module_keeps_the_hold_even_for_an_unrelated_edit(tmp_path, item):
    root = _project(tmp_path, LIB.replace("pub fn latest", item + "pub fn latest"))
    assert _held(_edit(root, "    x + 1\n", "    1 + x\n"))


def test_code_after_the_test_module_counts_as_part_of_it(tmp_path):
    root = _project(tmp_path, LIB + "\npub fn after() -> i32 {\n    1\n}\n")
    assert _held(_edit(root, "pub fn after() -> i32 {\n    1", "pub fn after() -> i32 {\n    2"))


def test_a_new_rust_file_with_tests_is_held(tmp_path):
    root = _project(tmp_path)
    (root / "src/new.rs").write_text(LIB)
    assert _held(_d(target=str(root), changed=(("src/new.rs", "write"),)))


def test_a_rust_file_in_a_folder_that_is_not_git_is_held(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/lib.rs").write_text(LIB)
    assert _held(_d(target=str(tmp_path), changed=(("src/lib.rs", "write"),)))


def test_other_languages_are_not_released(tmp_path):
    """Only Rust has a split; a Python file with tests stays held for any edit."""
    text = "def add(a, b):\n    return a + b\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    root = _project(tmp_path, text, "pkg/calc.py")
    assert _held(_edit(root, "return a + b", "return b + a", "pkg/calc.py"))
