"""One version, from pyproject.toml, seen by the package, the command line, the README and the changelog."""

import re
import tomllib
from pathlib import Path

import judge
from judge import cli

ROOT = Path(__file__).resolve().parent.parent
VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]


def test_dunder_version_is_the_pyproject_version():
    assert judge.__version__ == VERSION


def test_the_verdict_names_the_running_version():
    assert judge.seat.NAME == f"judge {VERSION}"


def test_the_command_line_reports_the_same_version(capsys):
    assert cli.main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == f"judge {VERSION}"


def test_the_readme_states_the_same_version():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"Version `{VERSION}`" in readme
    assert re.findall(r"[Vv]ersion `(\d+\.\d+\.\d+)`", readme) == [VERSION]


def test_the_changelog_has_an_entry_for_this_version():
    log = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    releases = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", log, flags=re.M)
    assert releases and releases[0] == VERSION, f"newest changelog entry is {releases[:1]}, pyproject is {VERSION}"
    assert "## [Unreleased]" in log
