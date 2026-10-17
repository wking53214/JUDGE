"""Shared test setup.

Warden is a test-time extra, not a runtime dependency: the Judge imports none of it. The tests that seat the
Judge in the real Warden loop need it. Without Warden they are skipped, with a stated reason, unless
JUDGE_REQUIRE_WARDEN=1 is set (CI's Warden job sets it), in which case a missing Warden is a failure,
never a silent skip.
"""

import importlib.util
import os

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
