"""A deleted code file is read as it was in the project's last commit (0.13.0, was KNOWN DEFECTS 2).

Before 0.13.0 a deleted file was not looked at: it is gone from the folder when the Judge runs, so a run that deleted
`src/lib.rs` and the `#[cfg(test)]` module inside it was ACCEPTed unless the pass counts dropped. Warden starts only on
a git folder with nothing uncommitted, so the file as it was before the run is in the commit HEAD names. The Judge reads
it from `.git` with the standard library (judge.lastcommit) and holds the run for a named human when it held tests. A
deleted code file whose committed copy cannot be read is a check that could not run, so it is held too.

These tests build real repositories with the git program and check the reader against `git show` byte for byte, for
loose objects and for packs with both kinds of delta.
"""

import os
import shutil
import subprocess

import pytest
from test_strict_evidence import _d

from judge import lastcommit

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="these tests build repositories with git")

DELETED_HELD = "a deleted code file held tests of its own in the last commit"
DELETED_UNREAD = "a deleted code file could not be read from the project's last commit"
RUST_WITH_TESTS = "pub fn f() -> i32 { 1 }\n#[cfg(test)]\nmod tests {\n    #[test]\n    fn t() {}\n}\n"
RUST_PLAIN = "pub fn g() -> i32 { 2 }\n"


def _git(cwd, *args):
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    return subprocess.run(["git", "-c", "init.defaultBranch=main", "-c", "commit.gpgsign=false", *args], cwd=cwd,
                          env=env, check=True, capture_output=True).stdout


def _repo(root, files):
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    for path, text in files.items():
        f = root / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "start")
    return root


def _delete(root, path):
    (root / path).unlink()


# ---- what the Judge decides -------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("path", "text"), [
    ("src/lib.rs", RUST_WITH_TESTS),
    ("pkg/calc.py", 'def add(a, b):\n    """\n    >>> add(1, 2)\n    3\n    """\n    return a + b\n'),
    ("web/sum.ts", "export const sum = 1\nif (import.meta.vitest) {}\n"),
])
def test_a_deleted_code_file_that_held_tests_is_held_for_a_named_human(tmp_path, path, text):
    root = _repo(tmp_path / "p", {path: text, "README.md": "x\n"})
    _delete(root, path)
    v = _d(target=str(root), changed=((path, "delete"),))
    assert v.decision == "INSUFFICIENT", v.reasons
    assert any(DELETED_HELD in r and path in r for r in v.reasons), v.reasons


def test_a_deleted_code_file_with_no_tests_is_still_accepted(tmp_path):
    root = _repo(tmp_path / "p", {"src/old.rs": RUST_PLAIN, "src/lib.rs": RUST_WITH_TESTS})
    _delete(root, "src/old.rs")
    v = _d(target=str(root), changed=(("src/old.rs", "delete"),))
    assert v.decision == "ACCEPT", v.reasons


def test_a_deleted_file_is_read_from_packs_with_both_kinds_of_delta(tmp_path):
    root = _repo(tmp_path / "p", {"src/lib.rs": RUST_PLAIN})
    for i in range(30):   # each version shorter than the one before, so git keeps an older one whole and the last as a delta
        (root / "src/lib.rs").write_text(RUST_WITH_TESTS + RUST_PLAIN * (80 - i) + f"// {i}\n")
        _git(root, "commit", "-qam", f"v{i}")
    oid = bytes.fromhex(_git(root, "rev-parse", "HEAD:src/lib.rs").decode().strip())
    for flag, kind in (("true", 6), ("false", 7)):   # offset deltas, then deltas that name their base by id
        _git(root, "-c", f"repack.useDeltaBaseOffset={flag}", "repack", "-adfq", "--depth=50", "--window=50")
        assert not any((root / ".git/objects").glob("??/*")), "every object should now be in a pack"
        (idx,) = (root / ".git/objects/pack").glob("*.idx")
        offset = lastcommit._find_offset(idx.read_bytes(), oid)
        assert offset is not None
        assert (idx.with_suffix(".pack").read_bytes()[offset] >> 4) & 7 == kind, "the file should be stored as that delta"
        assert lastcommit.committed_bytes(root, "src/lib.rs") == _git(root, "show", "HEAD:src/lib.rs")
    _delete(root, "src/lib.rs")
    v = _d(target=str(root), changed=(("src/lib.rs", "delete"),))
    assert any(DELETED_HELD in r for r in v.reasons), v.reasons


def test_the_reader_matches_git_for_every_file_of_a_packed_repository(tmp_path):
    files = {f"d{i % 3}/f{i}.py": "x = 1\n" * (i + 1) for i in range(40)}
    root = _repo(tmp_path / "p", files)
    for i in range(0, 40, 3):
        (root / f"d{i % 3}/f{i}.py").write_text("y = 2\n" + "x = 1\n" * (i + 1))
    _git(root, "commit", "-qam", "more")
    _git(root, "gc", "-q", "--aggressive")
    _git(root, "pack-refs", "--all")
    for path in files:
        assert lastcommit.committed_bytes(root, path) == _git(root, "show", f"HEAD:{path}"), path


def test_head_is_followed_to_the_branch_it_names(tmp_path):
    root = _repo(tmp_path / "p", {"src/lib.rs": RUST_PLAIN})
    _git(root, "checkout", "-qb", "feature")
    (root / "src/lib.rs").write_text(RUST_WITH_TESTS)
    _git(root, "commit", "-qam", "tests on the branch only")
    _delete(root, "src/lib.rs")
    v = _d(target=str(root), changed=(("src/lib.rs", "delete"),))
    assert any(DELETED_HELD in r for r in v.reasons), v.reasons


def test_a_project_that_is_a_subfolder_of_the_repository_is_read_from_the_right_place(tmp_path):
    repo = _repo(tmp_path / "r", {"crate/src/lib.rs": RUST_WITH_TESTS, "src/lib.rs": RUST_PLAIN})
    _delete(repo, "crate/src/lib.rs")
    v = _d(target=str(repo / "crate"), changed=(("src/lib.rs", "delete"),))
    assert any(DELETED_HELD in r for r in v.reasons), v.reasons


def test_a_linked_worktree_and_a_detached_head_are_followed(tmp_path):
    repo = _repo(tmp_path / "r", {"src/lib.rs": RUST_WITH_TESTS})
    _git(repo, "worktree", "add", "-q", "--detach", str(tmp_path / "wt"))
    wt = tmp_path / "wt"
    assert (wt / ".git").is_file()
    _delete(wt, "src/lib.rs")
    v = _d(target=str(wt), changed=(("src/lib.rs", "delete"),))
    assert any(DELETED_HELD in r for r in v.reasons), v.reasons


def test_a_deleted_file_in_a_folder_that_is_not_git_is_held(tmp_path):
    (tmp_path / "src").mkdir()
    v = _d(target=str(tmp_path), changed=(("src/lib.rs", "delete"),))
    assert v.decision == "INSUFFICIENT"
    assert any(DELETED_UNREAD in r and "not inside a git work tree" in r for r in v.reasons), v.reasons


def test_a_deleted_file_the_last_commit_does_not_have_is_held(tmp_path):
    root = _repo(tmp_path / "p", {"README.md": "x\n"})
    v = _d(target=str(root), changed=(("src/lib.rs", "delete"),))
    assert v.decision == "INSUFFICIENT"
    assert any(DELETED_UNREAD in r for r in v.reasons), v.reasons


def test_an_object_that_does_not_match_its_id_is_held(tmp_path):
    root = _repo(tmp_path / "p", {"src/lib.rs": RUST_WITH_TESTS})
    oid = _git(root, "rev-parse", "HEAD:src/lib.rs").decode().strip()
    obj = root / ".git/objects" / oid[:2] / oid[2:]
    obj.chmod(0o644)
    import zlib
    body = RUST_PLAIN.encode()
    obj.write_bytes(zlib.compress(b"blob %d\0" % len(body) + body))   # a plain file swapped in under the old id
    _delete(root, "src/lib.rs")
    v = _d(target=str(root), changed=(("src/lib.rs", "delete"),))
    assert v.decision == "INSUFFICIENT"
    assert any(DELETED_UNREAD in r and "does not match its id" in r for r in v.reasons), v.reasons


def test_a_sha256_repository_is_held_not_read(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    try:
        _git(root, "init", "-q", "--object-format=sha256")
    except subprocess.CalledProcessError:
        pytest.skip("this git cannot make a SHA-256 repository")
    (root / "src").mkdir()
    (root / "src/lib.rs").write_text(RUST_WITH_TESTS)
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "start")
    _delete(root, "src/lib.rs")
    v = _d(target=str(root), changed=(("src/lib.rs", "delete"),))
    assert v.decision == "INSUFFICIENT"
    assert any(DELETED_UNREAD in r and "SHA-1" in r for r in v.reasons), v.reasons


def test_a_deleted_test_file_gets_its_own_reason_not_two(tmp_path):
    root = _repo(tmp_path / "p", {"tests/test_a.py": "def test_a():\n    pass\n"})
    _delete(root, "tests/test_a.py")
    v = _d(target=str(root), changed=(("tests/test_a.py", "delete"),))
    assert v.decision == "INSUFFICIENT"
    assert not any(DELETED_HELD in r or DELETED_UNREAD in r for r in v.reasons), v.reasons


def test_harm_still_outranks_the_hold_for_a_deleted_file(tmp_path):
    root = _repo(tmp_path / "p", {"src/lib.rs": RUST_WITH_TESTS})
    _delete(root, "src/lib.rs")
    v = _d(target=str(root), scope="documentation", changed=(("src/lib.rs", "delete"),))
    assert v.decision == "REJECT"


def test_a_deleted_file_that_is_a_link_in_the_last_commit_is_held(tmp_path):
    root = tmp_path / "p"
    _repo(root, {"src/real.rs": RUST_PLAIN})
    (root / "src/alias.rs").symlink_to("real.rs")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "link")
    _delete(root, "src/alias.rs")
    v = _d(target=str(root), changed=(("src/alias.rs", "delete"),))
    assert v.decision == "INSUFFICIENT"
    assert any(DELETED_UNREAD in r and "link" in r for r in v.reasons), v.reasons
