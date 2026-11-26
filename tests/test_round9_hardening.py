"""Round 9 (0.7.0): five gaps closed inside the Judge, each reproduced first on 0.6.0.

For every gap there is the input that 0.6.0 got wrong (now a stricter verdict), the corrected reason, and legitimate
evidence of the same shape that still gets its old verdict.

1. A file inside a folder whose name starts with `.ghost` was ordinary code (0.6.0: ACCEPT). Now harm, like a
   `.ghost_*` file. Was KNOWN DEFECTS 3 in 0.6.0.
2. Edits into `.hg`, `.svn`, `__pycache__`, `.mypy_cache` and `.pytest_cache`, which Warden refuses, were ACCEPTed. Now
   harm, like `.git`.
3. A path with look-alike letters from another script (a Cyrillic `е` in `tests/`) escaped every list (ACCEPT). Now held
   for a named human. Was part of KNOWN DEFECTS 4 in 0.6.0.
4. A suite marked `text_only` beside an exit code was ACCEPTed. Now held as a contradiction. Was part of KNOWN DEFECTS 4 in 0.6.0.
5. The CNS connector digested one reading of the evidence and judged another. A mapping whose `items` and `get` disagree
   got PASS while carrying the digest of a record that is TERMINAL_BREACH. Now the Judge decides the frozen copy the
   digest was computed from.
"""

import dataclasses
import re
from pathlib import Path

import cns.gate as gate
import pytest
from cns.suite import SuiteRun
from test_strict_evidence import _d, _ev, _suite

from judge import seat
from judge.cns_connector import JudgeGate

ROOT = Path(__file__).resolve().parent.parent
SEAT = (ROOT / "judge" / "seat.py").read_text(encoding="utf-8")


# 1. nested Ghost folders

@pytest.mark.parametrize("path", [
    ".ghost_cache/data.json", "a/.ghost_ledger/b/c.json", ".GHOST_cache/x.json", ".ghost_cache\\data.json",
    "./.ghost_cache/x.json", ".ghost_cache /x.json",
])
def test_a_file_inside_a_ghost_folder_is_harm(path):
    v = _d(changed=((path, "write"),))
    assert v.decision == "REJECT", path
    assert "Ghost's baseline or another .ghost_ file was changed" in " ".join(v.reasons)


@pytest.mark.parametrize("path", ["docs/ghost_story.md", "ghost/notes.py", "src/myghost/x.py", "pkg/ghost.py"])
def test_a_path_that_only_mentions_ghost_is_still_ordinary(path):
    assert _d(changed=((path, "write"),)).decision == "ACCEPT", path


def test_a_link_into_a_ghost_folder_is_harm(tmp_path):
    (tmp_path / ".ghost_cache").mkdir()
    (tmp_path / ".ghost_cache" / "data.json").write_text("{}")
    (tmp_path / "data").symlink_to(tmp_path / ".ghost_cache")
    v = _d(target=str(tmp_path), changed=(("data/data.json", "write"),))
    assert v.decision == "REJECT"


# 2. version-control and cache folders

@pytest.mark.parametrize("path", [".hg/hgrc", ".svn/entries", "pkg/__pycache__/a.cpython-313.pyc", ".mypy_cache/x.json",
                                  ".pytest_cache/v/cache/lastfailed", "sub/.HG/store"])
def test_an_edit_into_a_folder_warden_refuses_is_harm(path):
    v = _d(changed=((path, "write"),))
    assert v.decision == "REJECT", path
    assert "reached outside the project" in " ".join(v.reasons)


@pytest.mark.parametrize("path", ["src/hg_tools.py", "cache/x.py", "pkg/pycache.py", "svn_export.py"])
def test_a_folder_that_only_looks_like_one_is_still_ordinary(path):
    assert _d(changed=((path, "write"),)).decision == "ACCEPT", path


# 3. look-alike letters

@pytest.mark.parametrize("path", [
    "tеsts/helper.py",          # Cyrillic e: tests/
    ".ghοst_cache/x.json",      # Greek omicron: .ghost_cache/
    ".gіt/config",              # Cyrillic i: .git/
    "pkg/сonftest.py",          # Cyrillic s: conftest.py
    "TEЅTS/helper.py",          # Cyrillic capital S, after lower-casing: tests/
])
def test_a_look_alike_of_a_protected_path_is_held_for_a_named_human(path):
    v = _d(changed=((path, "write"),))
    assert v.decision == "INSUFFICIENT", path
    assert "look like Latin ones" in " ".join(v.reasons)


def test_the_latin_spelling_is_judged_as_before():
    assert _d(changed=(("tests/helper.py", "write"),)).decision == "INSUFFICIENT"
    assert _d(changed=((".ghost_cache/x.json", "write"),)).decision == "REJECT"


@pytest.mark.parametrize("path", ["docs/привет.md", "src/данные.py",
                                  "src/café.py", "docs/日本語.md"])
def test_a_path_in_another_script_that_reads_as_nothing_protected_is_still_ordinary(path):
    assert _d(changed=((path, "write"),)).decision == "ACCEPT", path


def test_harm_beside_a_look_alike_still_rejects():
    v = _d(changed=(("tеsts/helper.py", "write"),), suite_after=_suite(failed=1))
    assert v.decision == "REJECT"
    assert "look like Latin ones" not in " ".join(v.reasons)


# 4. text_only beside an exit code

@pytest.mark.parametrize("which", ["suite_before", "suite_after"])
def test_a_suite_marked_text_only_that_gives_an_exit_code_is_held(which):
    run = _suite()
    object.__setattr__(run, "text_only", True)
    v = _d(**{which: run})
    assert v.decision == "INSUFFICIENT"
    assert "contradicts itself about where its counts came from" in " ".join(v.reasons)


def test_text_only_false_beside_an_exit_code_is_accepted_as_before():
    run = _suite()
    object.__setattr__(run, "text_only", False)
    assert _d(suite_after=run).decision == "ACCEPT"


def test_text_only_with_no_exit_code_is_held_as_before_without_the_contradiction():
    run = SuiteRun(ran=True, passed=10)
    object.__setattr__(run, "text_only", True)
    v = _d(suite_after=run)
    assert v.decision == "INSUFFICIENT"
    assert "contradicts itself" not in " ".join(v.reasons)


# 5. the connector judges exactly what it digested

class _TwoFaced(dict):
    """Shows one answer to whoever iterates it (the digest) and another to whoever calls get (the Judge)."""

    def items(self):
        return {**dict(self), "key_proven": False}.items()


def test_a_mapping_that_answers_two_ways_cannot_pass_under_the_digest_of_a_breach():
    honest_false = JudgeGate().check(_ev(assay={**_ev().assay, "key_proven": False}))
    two_faced = JudgeGate().check(_ev(assay=_TwoFaced(_ev().assay)))
    assert honest_false.outcome is gate.GateOutcome.TERMINAL_BREACH
    # 0.6.0: PASS, with honest_false's digest.
    assert two_faced.subject_digest == honest_false.subject_digest
    assert two_faced.outcome is honest_false.outcome


def test_an_attribute_on_the_class_is_digested_because_the_judge_reads_it():
    @dataclasses.dataclass(frozen=True)
    class ForgedRun(SuiteRun):
        forged = True  # not a field and not in the instance: 0.6.0 judged it but left it out of the digest

    plain = JudgeGate().check(_ev())
    flagged = JudgeGate().check(_ev(suite_after=ForgedRun(ran=True, passed=10, exit_code=0)))
    assert flagged.outcome is gate.GateOutcome.TERMINAL_BREACH
    assert flagged.subject_digest != plain.subject_digest


def test_an_attribute_that_answers_differently_each_time_is_read_once():
    class Flaky:
        def __init__(self):
            self._reads = 0

        @property
        def swizzle_proofs(self):
            self._reads += 1
            return self._reads == 1

    ev = _ev()
    flaky = Flaky()
    for f in dataclasses.fields(ev):
        if f.name != "swizzle_proofs":
            setattr(flaky, f.name, getattr(ev, f.name))
    for k in ("ghost_baseline_before", "ghost_baseline_after"):
        setattr(flaky, k, getattr(ev, k))
    result = JudgeGate().check(flaky)
    assert flaky._reads == 1
    assert result.outcome is gate.GateOutcome.PASS
    assert result.subject_digest == JudgeGate().check(ev).subject_digest


def test_the_judge_receives_a_frozen_copy_never_the_original():
    seen = []

    class Recorder:
        def decide(self, evidence):
            seen.append(evidence)
            return seat.Judge().decide(evidence)

    ev = _ev(assay=dict(_ev().assay))
    before = JudgeGate(Recorder()).check(ev)
    copy = seen[0]
    assert copy is not ev
    ev.assay["key_proven"] = False  # a later change to the original reaches neither the copy nor the bound digest
    assert copy.assay["key_proven"] is True
    with pytest.raises(AttributeError):
        copy.scope = "documentation"  # type: ignore[misc]
    assert seat.Judge().decide(copy).decision == "ACCEPT" and before.outcome is gate.GateOutcome.PASS


def test_every_attribute_the_judge_reads_is_copied_before_the_digest():
    literal = set(re.findall(r"getattr\(\w+(?:\.\w+)?, [\"'](\w+)[\"']", SEAT))
    fields = set(re.findall(r"_field\(e, \"(\w+)\"\)", SEAT))
    looped = set(seat._EXIT_NAMES) | set(seat._FORGED_NAMES) | set(seat._SUITE_COUNTS)
    read = literal | fields | looped
    assert read and read <= seat.ROW_ATTRIBUTES, read - seat.ROW_ATTRIBUTES


# housekeeping: the CNS comment in pyproject.toml names no other tag than the pin

def test_the_cns_comment_names_no_tag_but_the_pinned_one():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = text[text.index("# The runtime dependency is CNS"):text.index("[project.urls]")]
    pin = re.search(r"CNS\.git@(v\d+\.\d+\.\d+)", block).group(1)
    assert set(re.findall(r"v\d+\.\d+\.\d+", block)) == {pin}
