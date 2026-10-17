"""Every GitHub Action in the workflow is pinned to a full commit, and the lint tools to exact versions."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"
PYPROJECT = ROOT / "pyproject.toml"


def test_every_action_is_pinned_to_a_full_commit_with_its_tag_in_a_comment():
    uses = re.findall(r"^\s*-?\s*uses:\s*(\S.*)$", WORKFLOW.read_text(encoding="utf-8"), flags=re.M)
    assert uses, "the workflow uses no actions; this test has nothing to check"
    for item in uses:
        pinned = re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}\s+#\s*v\d+\.\d+\.\d+", item)
        assert pinned, f"not pinned by full SHA with a tag comment: {item!r}"


def test_the_lint_tools_are_pinned_to_exact_versions():
    lint = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["optional-dependencies"]["lint"]
    names = sorted(re.split(r"[=<>!~ ]", d)[0] for d in lint)
    assert names == ["mypy", "ruff"], lint
    for dep in lint:
        assert re.fullmatch(r"[a-z]+==\d+\.\d+\.\d+", dep), f"not an exact version: {dep!r}"
