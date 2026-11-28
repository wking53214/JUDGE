"""REVIEW.md, the guide for an outside reviewer, says only what the Judge does.

Its probe table is run here row by row, so a rule that changes makes the guide fail until the guide is corrected.
It also keeps the guide's pointers real and holds it to the README's wording rules.
"""

import copy
import json
import re
from pathlib import Path

import pytest

from judge import cli

ROOT = Path(__file__).resolve().parent.parent
GUIDE = (ROOT / "REVIEW.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
EXAMPLE = json.loads((ROOT / "examples" / "accept.json").read_text(encoding="utf-8"))


def _with_new_finding(evidence: dict, words: dict | None = None) -> None:
    evidence["ghost_after"].append("ghost-b")
    if words is not None:
        evidence["ghost_severity"] = words


def _attack(severity: str) -> object:
    return lambda e: e["attacks"].append({"scenario": "b", "severity": severity, "status": "violated"})


def _code_edit(evidence: dict, path: str) -> None:
    evidence.update(scope="code")
    evidence["changed"].append([path, "write"])
    evidence["edit_sources"].append(1)


def _a_named_test_replaced(evidence: dict) -> None:
    evidence["suite_before"].update(test_outcomes=[["t::a", "passed"], ["t::b", "passed"]], passed=2)
    evidence["suite_after"].update(test_outcomes=[["t::a", "passed"], ["t::c", "passed"]], passed=2)


PROBES = {
    "P1": lambda e: e.update(swizzle_proofs=False),
    "P2": lambda e: e["suite_after"].update(failed=1),
    "P3": _attack("low"),
    "P4": _attack("medium"),
    "P5": lambda e: e["assay"].update(floor=0, caught=0),
    "P6": lambda e: _with_new_finding(e),
    "P7": lambda e: _with_new_finding(e, {"ghost-a": "minor", "ghost-b": "minor"}),
    "P8": lambda e: (e["suite_after"].update(failed=1), e.update(target=5)),
    "P9": lambda e: e.update(cycles=[], changed=[], edit_sources=[]),
    "P10": lambda e: e["changed"].append(["../x.txt", "write"]),
    "P11": lambda e: e["suite_after"].update(passed=9),
    "P12": lambda e: e.update(target="/nonexistent-folder-for-the-probe"),
    "P13": lambda e: e["changed"].append(["tests/test_x.py", "write"]),
    "P14": lambda e: _code_edit(e, "tests/test_x.py"),
    "P15": _a_named_test_replaced,
    "P16": lambda e: e["suite_after"].update(text_only=True),
    "P17": lambda e: _code_edit(e, "t\u0435sts/x.py"),
    "P18": lambda e: _code_edit(e, "TESTS/x.py"),
    "P19": lambda e: e["ghost_baseline_after"].update(suppressed=1),
    "P20": lambda e: e["changed"].append([".git/hooks/pre-commit", "write"]),
    "P21": lambda e: e.update(unmeasured=["ghost"]),
    "P22": lambda e: e.update(attacks=[]),
    "P23": lambda e: e["suite_after"].update(forged=True),
}
ROWS = dict(re.findall(r"^\| (P\d+) \|[^|]*\| (ACCEPT|REJECT|INSUFFICIENT) \|", GUIDE, re.M))


def _decide(tmp_path, mutate, capsys) -> str:
    evidence = copy.deepcopy(EXAMPLE)
    evidence["target"] = str(tmp_path)
    mutate(evidence)
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(evidence), encoding="utf-8")
    cli.main(["decide", str(path)])
    return json.loads(capsys.readouterr().out)["decision"]


def test_the_guide_and_the_tests_name_the_same_probes():
    assert set(ROWS) == set(PROBES)


@pytest.mark.parametrize("probe", sorted(PROBES, key=lambda p: int(p[1:])))
def test_each_probe_in_the_guide_gets_the_verdict_the_guide_states(probe, tmp_path, capsys):
    assert _decide(tmp_path, PROBES[probe], capsys) == ROWS[probe]


def test_the_unchanged_example_is_accepted_as_the_guide_assumes(tmp_path, capsys):
    assert _decide(tmp_path, lambda e: None, capsys) == "ACCEPT"


def test_every_file_the_guide_names_exists():
    named = set(re.findall(r"`((?:judge|tests|examples)/[\w./-]+\.(?:py|json))`", GUIDE))
    assert named, "the guide names no files"
    for name in named:
        assert (ROOT / name).is_file(), name
    for name in ("README.md", "CHANGELOG.md", "pyproject.toml"):
        assert (ROOT / name).is_file()


def test_every_readme_section_the_guide_points_at_exists():
    for heading in ("ARCHITECTURAL STORY", "KNOWN DEFECTS", "ROAD TO 1.0.0", "WHAT WORKS",
                    "WHAT DOES NOT WORK / NOT PROVEN"):
        assert f"## {heading}\n" in README, heading
    assert "### What counts as a test, exactly\n" in README
    assert "### From the command line\n" in README


def test_the_guide_has_no_em_dash_no_banned_word_no_pinned_sha_and_no_test_count():
    dash = chr(0x2014)  # spelled by code point so this file holds no em dash itself
    assert dash not in GUIDE
    lowered = GUIDE.lower()
    for word in ("robust", "powerful", "production-ready", "production ready", "seamless", "comprehensive",
                 "blazing", "enterprise", "battle-tested", "state-of-the-art"):
        assert word not in lowered, word
    assert not re.search(r"\b[0-9a-f]{40}\b", GUIDE)
    assert not re.search(r"\b\d{2,4} (tests|passed)\b", GUIDE)


def test_the_readme_points_at_the_guide_and_says_no_review_has_been_made():
    assert "`REVIEW.md`" in README
    flat = " ".join(README.split()).lower()
    assert "no reviewer has been found" in flat and "no review has been made" in flat
    assert "Written 2026-11-28 for Judge" in GUIDE


def test_every_section_the_guide_points_at_exists():
    headings = set(re.findall(r"^## (\d+)\. ", GUIDE, re.M))
    pointed = set(re.findall(r"\bsection (\d+)\b", GUIDE))
    assert pointed and pointed <= headings, (pointed, headings)
