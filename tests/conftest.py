"""Shared test setup.

Warden is a test-time extra, not a runtime dependency: the Judge imports none of it. The tests that seat the
Judge in the real Warden loop need it. Without Warden they are skipped, with a stated reason, unless
JUDGE_REQUIRE_WARDEN=1 is set (CI's Warden job sets it), in which case a missing Warden is a failure,
never a silent skip.
"""

import atexit
import importlib.util
import os
import shutil
import tempfile
from pathlib import Path

import pytest

REQUIRE_WARDEN = os.environ.get("JUDGE_REQUIRE_WARDEN") == "1"
HAVE_WARDEN = importlib.util.find_spec("warden") is not None


def need_warden() -> None:
    """Call at the top of a module that imports Warden, before the import."""
    if HAVE_WARDEN:
        return
    if REQUIRE_WARDEN:
        raise RuntimeError("JUDGE_REQUIRE_WARDEN=1 but Warden is not installed: install the pin from pyproject (extra 'warden')")
    pytest.skip("Warden is not installed (extra 'warden'); the real-loop tests are skipped", allow_module_level=True)


def pytest_report_header(config: pytest.Config) -> str:
    state = "installed" if HAVE_WARDEN else "NOT installed"
    return f"warden: {state}; JUDGE_REQUIRE_WARDEN={'1' if REQUIRE_WARDEN else '0'}"


# A real, empty project folder for hand-made evidence. Since 0.8.0 the Judge holds a run with edits when the folder named
# in `target` is not on the machine (it cannot follow symbolic links there), so evidence that should be ACCEPTed names
# a folder that exists. Created once per test session and removed at exit.
PROJECT_DIR = tempfile.mkdtemp(prefix="judge-project-")
atexit.register(shutil.rmtree, PROJECT_DIR, ignore_errors=True)


def place_listed_files(base: dict) -> dict:
    """Put an empty file in the shared project folder for each written or replaced edit the evidence lists, as a real
    Warden run leaves them. Since 0.13.0 a listed code file that is not in the folder is held (the owner's ruling of
    2026-11-27), and these helpers build evidence that is meant to be judged on something else. Only evidence aimed at
    PROJECT_DIR is touched, only plain relative paths inside it, and an existing file is left as it is. Returns `base`."""
    if base.get("target") != PROJECT_DIR or not isinstance(base.get("changed"), (tuple, list)):
        return base
    root = Path(PROJECT_DIR).resolve()
    for edit in base["changed"]:
        if not (isinstance(edit, (tuple, list)) and len(edit) == 2 and all(isinstance(x, str) for x in edit)):
            continue
        path, kind = edit
        if kind.strip().lower() not in {"write", "replace"} or not path or "\0" in path:
            continue
        f = root / path.replace("\\", "/")
        try:
            if f.resolve().is_relative_to(root) and f.resolve() != root and not f.exists() and not f.is_symlink():
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_bytes(b"")
        except (OSError, ValueError):
            pass
    return base


def with_project(data: dict) -> dict:
    """A copy of decoded evidence whose `target` is the real project folder above, holding the files it lists."""
    return place_listed_files({**data, "target": PROJECT_DIR})


def label_edits(base: dict) -> dict:
    """Give hand-made evidence the `edit_sources` labels a Warden on CNS 4.2.0 would write, when the installed CNS declares
    the field and the test did not set them: the applied cycles in order, the last one taking any further edits. Without
    labels the Judge holds a run in which a cycle applied an edit (0.9.0), and these helpers build evidence that is meant
    to be judged on something else. A record with no applied cycle, or fewer edits than applied cycles, is left unlabelled,
    so the contradiction the test is about is the one the Judge sees."""
    from cns.seat import Evidence

    place_listed_files(base)
    if "edit_sources" not in Evidence.__dataclass_fields__ or "edit_sources" in base:
        return base
    cycles, changed = base.get("cycles") or (), base.get("changed") or ()
    if not isinstance(cycles, (tuple, list)) or not isinstance(changed, (tuple, list)):
        return base
    applied = [c[0] for c in cycles if isinstance(c, (tuple, list)) and len(c) == 2 and c[1] == "APPLIED"]
    if not applied or len(changed) < len(applied):
        return base
    return {**base, "edit_sources": tuple(applied + [applied[-1]] * (len(changed) - len(applied)))}
