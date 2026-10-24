"""The README's evidence and ledger point at things that exist, and the README keeps the sections it promises.

A claim of "works" in the README names a test or a CI job. This file fails if a named test is gone, if the ledger cites a
version or date the CHANGELOG does not have, if a CI job the README names is not in the workflow, or if marketing words come back.
"""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")
CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
PYPROJECT_TEXT = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

REQUIRED_HEADINGS = (
    "## WHAT THIS IS",
    "## HOW TO INSTALL AND RUN",
    "## WHAT WORKS",
    "## WHAT DOES NOT WORK / NOT PROVEN",
    "## KNOWN DEFECTS",
    "## WHAT BROKE AND HOW IT WAS FIXED",
    "## SELF-HOSTING",
    "## CEILINGS CODE CANNOT FIX",
)
BANNED_WORDS = ("robust", "powerful", "production-ready", "production ready", "seamless", "comprehensive",
                "blazing", "enterprise", "battle-tested", "state-of-the-art")
LEDGER = "## WHAT BROKE AND HOW IT WAS FIXED"


def section(title_start: str) -> str:
    start = README.index(title_start)
    following = re.search(r"^## ", README[start + 1:], re.M)
    return README[start:start + 1 + following.start()] if following else README[start:]


def test_the_readme_keeps_the_sections_it_promises_in_order():
    positions = [README.index(heading) for heading in REQUIRED_HEADINGS]
    assert positions == sorted(positions)
    assert all(README.count(heading + "\n") == 1 for heading in REQUIRED_HEADINGS)


def test_every_test_the_readme_names_exists():
    named = set(re.findall(r"`(tests/test_\w+\.py)(?:::(\w+))?`", README))
    assert named, "the README names no tests"
    for path, function in named:
        source = (ROOT / path).read_text(encoding="utf-8")
        if function:
            assert re.search(rf"^\s*def {function}\(", source, re.M), f"{path}::{function} is named in the README"


def test_every_ledger_entry_cites_a_changelog_version_with_the_same_date():
    ledger = section(LEDGER)
    entries = re.findall(r"^\*\*(\d+\.\d+\.\d+)\*\* \((\d{4}-\d{2}-\d{2})", ledger, re.M)
    assert entries, "the ledger has no entries"
    headings = dict(re.findall(r"^## \[(\d+\.\d+\.\d+)\] - (\d{4}-\d{2}-\d{2})", CHANGELOG, re.M))
    for version, date in entries:
        assert headings.get(version) == date, (version, date, headings.get(version))
    mentioned = set(re.findall(r"\b0\.\d+\.\d+\b", ledger))
    assert mentioned <= set(headings), mentioned - set(headings)


def test_the_ledger_runs_newest_first():
    versions = [tuple(map(int, v.split("."))) for v in re.findall(r"^\*\*(\d+\.\d+\.\d+)\*\*", section(LEDGER), re.M)]
    assert versions == sorted(versions, reverse=True)


def test_every_ci_job_the_readme_names_is_in_the_workflow():
    named = set(re.findall(r"`(lint|pytest|warden)` job", README))
    assert named == {"lint", "pytest", "warden"}, named
    for job in named:
        assert re.search(rf"^  {job}:", WORKFLOW, re.M), job


def test_the_readme_uses_no_marketing_words():
    lowered = README.lower()
    found = [word for word in BANNED_WORDS if word in lowered]
    assert not found, found


def test_the_readme_and_changelog_use_no_em_dash():
    assert "—" not in README and "—" not in CHANGELOG


def test_the_readme_gives_the_cns_migration_note_and_the_pin_names_its_commit():
    assert "from `v1.9.0` to `v2.0.0`" in README
    assert "cns @ git+https://github.com/wking53214/CNS.git@v2.0.0" in PYPROJECT_TEXT
    assert "# v2.0.0 = b13e5d2f9e0e4291725f82794b89117c3d840ac1" in PYPROJECT_TEXT
    tomllib.loads(PYPROJECT_TEXT)


def test_the_readme_warns_off_the_bare_pypi_name_and_installs_from_git_or_a_checkout():
    assert "Do not run `pip install judge`" in README
    bare = re.findall(r"^\s*pip install (?!-e|git\+)\S+", README, re.M)
    assert not bare, bare


# Constants copied from the CNS repository's docs/evidence/SELFHOSTING_2026-10-23.md and its JUDGE.run1/run2 records.
SELFHOST_COMMIT = "c3001b8"
SELFHOST_SUITE = "green before and after with nothing skipped"  # the record says 1157 passed, 0 skipped; the README may not state a count
SELFHOST_GAPS = "7 gaps"
SELFHOST_GHOST_FINDINGS = "42 findings"


def test_self_hosting_cites_the_cns_evidence_and_says_what_it_does_and_does_not_mean():
    text = " ".join(section("## SELF-HOSTING").split())
    assert "docs/evidence/SELFHOSTING_2026-10-23.md" in text
    assert "on its branch `claude/horsemen-production-status-5wsndb`" in text
    assert "https://github.com/wking53214/CNS)" in text
    assert "FINISH_REJECTED (exit 1)" in text and "fixed in Burnish 0.3.12" in text
    assert "ended ACCEPT (exit 0)" in text
    for constant in (SELFHOST_COMMIT, SELFHOST_SUITE, SELFHOST_GAPS, SELFHOST_GHOST_FINDINGS):
        assert constant in text, constant
    assert "does not mean there are no secrets or weak tests" in text
    assert "The record covers commit `c3001b8`, not any later commit" in text
    assert "No fresh run on the current commits is recorded yet" not in text
    assert "STATUS" not in text


def test_self_hosting_keeps_the_older_registry_record_and_says_it_predates_the_current_rules():
    text = section("## SELF-HOSTING")
    assert "docs/REGISTRY.json" in text and "row 5" in text and "Row 6" in text
    assert "predate Warden 0.13.0" in text


def test_the_readme_does_not_say_whether_release_tags_exist():
    flat = " ".join(README.split())
    assert not re.search(r"\b(?:not tagged|untagged|no tags?|tags? exists?|tags? do(?:es)? not)\b", flat, re.I)
    assert not re.search(r"\btag `v0\.10\.0`", flat)
    assert "check the repository's tags and releases for what exists" in flat
