"""The Judge is independent of CNS, and these tests hold whether or not CNS is
installed. Each one runs in a fresh interpreter in which ``cns`` is blocked
outright (``sys.modules['cns'] = None`` makes any import of it fail), so the
result does not depend on what the test environment happens to contain.

While the pinned Warden has no dependencies, blocking cns leaves the Judge whole. From Warden 0.11.4 on,
Warden imports cns itself, so these tests are expected to change when that pin moves.
"""

import ast
import re
import subprocess
import sys
import textwrap
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
BLOCK = "import sys; sys.modules['cns'] = None; sys.modules['cns.gate'] = None\n"
CNS_PIN = re.compile(r"^cns @ git\+https://github\.com/wking53214/cns\.git@(?P<ref>[0-9a-f]{40})$")


def _run(code: str) -> subprocess.CompletedProcess:
    # The interpreter's own site-packages stay on the path so warden imports; only cns is blocked.
    return subprocess.run([sys.executable, "-c", BLOCK + textwrap.dedent(code)], capture_output=True, text=True,
                          cwd=ROOT, timeout=60)


def test_judge_and_its_connector_import_with_cns_blocked():
    done = _run("import judge, judge.cns_connector; print('ok')")
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "ok"


def test_judge_still_decides_with_cns_blocked():
    done = _run(
        """
        import sys
        sys.path.insert(0, 'tests')
        from test_judge import _evidence
        from judge import Judge
        assert Judge().decide(_evidence()).decision == 'ACCEPT'
        assert Judge().decide(_evidence(suite_after=None)).decision == 'INSUFFICIENT'
        print('ok')
        """
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "ok"


def test_connector_says_what_is_missing_when_cns_is_blocked():
    done = _run(
        """
        from judge.cns_connector import CnsNotInstalled, JudgeGate, cns_available
        assert cns_available() is False
        try:
            JudgeGate()
        except CnsNotInstalled as exc:
            assert "pip install 'judge[cns]'" in str(exc)
            assert isinstance(exc, ImportError)
            print('ok')
        """
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "ok"


def test_importing_the_package_does_not_load_the_connector_or_cns():
    done = subprocess.run(
        [sys.executable, "-c", "import sys, judge; print('judge.cns_connector' in sys.modules, 'cns' in sys.modules)"],
        capture_output=True, text=True, cwd=ROOT, timeout=60)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "False False"


def test_no_module_imports_cns_by_statement():
    for p in (ROOT / "judge").rglob("*.py"):
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module or ""] if isinstance(node, ast.ImportFrom) and node.level == 0 else []
            assert not any(n.split(".")[0] == "cns" for n in names), f"{p.name} imports cns by statement"


def test_the_package_declares_no_runtime_dependency_on_cns():
    meta = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    assert not any(d.startswith("cns") for d in meta["dependencies"])


def test_the_cns_extra_is_pinned_to_a_full_commit():
    extra = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["optional-dependencies"]["cns"]
    assert len(extra) == 1 and CNS_PIN.match(extra[0]), f"cns must be pinned to a full commit, got {extra}"
