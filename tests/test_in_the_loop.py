"""Seated in Warden's loop, with the real Warden: the Judge accepts a clean run and turns away a harmful one."""

import sys
from pathlib import Path

import pytest
from conftest import need_warden

need_warden()

import warden.tagteam as tagteam  # noqa: E402
from warden.authorization import grant  # noqa: E402
from warden.tagteam import TagTeam  # noqa: E402

from judge import Judge  # noqa: E402

HELD = ({"scenario": "a", "severity": "high", "status": "held"},)
VIOLATED = ({"scenario": "a", "severity": "high", "status": "violated"},)


class Rewrites:
    """A stand-in Drafter that rewrites NOTE.md once."""

    def __init__(self):
        self.done = False

    def propose(self, target, observed, baseline):
        from cns.seat import FileEdit
        from warden.models import Transformation, TransformationStatus
        if self.done:
            return None
        self.done = True
        return Transformation(
            target=str(Path(target).resolve()), intent="t", architectural_reason="t", affected_files=("NOTE.md",),
            expected_behavior="none", preservation_requirements=(), known_defects=(), transformation_scope="documentation",
            baseline_reference=baseline, evidence=(), edits=(FileEdit("NOTE.md", "write", "new\n", ""),),
            status=TransformationStatus.PROPOSED)


def _repo(root: Path) -> Path:
    (root / "pkg").mkdir()
    (root / "pkg" / "__init__.py").write_text("V = 1\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_a.py").write_text("from pkg import V\n\ndef test_a():\n    assert V == 1\n", encoding="utf-8")
    (root / "NOTE.md").write_text("old\n", encoding="utf-8")
    (root / "pyproject.toml").write_text('[project]\nname = "d"\nversion = "0.0.1"\n', encoding="utf-8")
    return root


@pytest.fixture
def stack(monkeypatch):
    state = {"attacks": HELD, "ghost": ()}
    monkeypatch.setattr(tagteam, "ghost_scan", lambda target, **kw: state["ghost"])
    monkeypatch.setattr(TagTeam, "_calibrate", lambda self, python, notes: True)
    monkeypatch.setattr(tagteam, "governor_attacks", lambda **kw: state["attacks"])
    monkeypatch.setattr(tagteam, "assay_score", lambda **kw: (True, {"key_proven": True, "failure_modes": 5, "caught": 3}, "ok"))
    return state


class WithBaseline(Judge):
    """Hands the Judge a Ghost baseline report of its own choosing.

    Warden 0.8.0 did not carry Ghost's baseline report, so this adds it. Warden 0.9.0 already carries the two
    fields (None here, because the Ghost scan is stubbed), so they are overridden rather than added twice.
    """

    baseline = {"path": None, "suppressed": 0}

    def decide(self, evidence):
        from types import SimpleNamespace
        fields = dict(vars(evidence))
        fields.update(ghost_baseline_before=self.baseline, ghost_baseline_after=self.baseline)
        return super().decide(SimpleNamespace(**fields))


def _run(root, judge=None):
    auth = grant("william", "transform", str(root.resolve()), "documentation", "judge integration")
    team = TagTeam(drafter=Rewrites(), judge=judge or WithBaseline(), ghost_tools_root=Path("."), swizzle_root=Path("."),
                   assay_root=Path("."), assay_floor=3)
    return team.run(root, findings=[], authorization=auth)


def test_a_clean_run_is_accepted_by_the_judge(tmp_path, stack):
    result = _run(_repo(tmp_path))
    assert result.decision == "ACCEPT" and result.verdict.judge.startswith("judge")
    assert (tmp_path / "NOTE.md").read_text(encoding="utf-8") == "new\n"


def test_a_violated_attack_makes_the_judge_turn_the_whole_run_away(tmp_path, stack):
    stack["attacks"] = VIOLATED
    result = _run(_repo(tmp_path))
    assert result.decision == "JUDGE_REJECTED" and any("violated" in r for r in result.verdict.reasons)
    assert (tmp_path / "NOTE.md").read_text(encoding="utf-8") == "old\n"


def test_attacks_that_never_ran_leave_the_run_unjudged(tmp_path, stack):
    stack["attacks"] = None
    result = _run(_repo(tmp_path))
    assert result.decision == "ACCEPT_UNVERIFIED" and result.verdict.decision == "INSUFFICIENT"
    assert result.held_digest
    assert (tmp_path / "NOTE.md").read_text(encoding="utf-8") == "old\n"


def test_without_a_baseline_report_the_real_warden_run_is_unjudged(tmp_path, stack):
    result = _run(_repo(tmp_path), judge=Judge())
    assert result.decision == "ACCEPT_UNVERIFIED" and result.verdict.decision == "INSUFFICIENT"
    assert any("baseline" in r for r in result.verdict.reasons)


# ---- the consistency check on cycles and declined must not turn away what the real loop writes ------------

class Nothing:
    """A Drafter with nothing to propose, so the loop converges at once."""

    def propose(self, target, observed, baseline):
        return None


class Finishes:
    """A Finisher that rewrites NOTE.md (a change that belongs to no cycle)."""

    def finish(self, target, baseline, facts):
        from cns.seat import FileEdit
        from warden.models import Transformation, TransformationStatus
        return Transformation(
            target=str(Path(target).resolve()), intent="t", architectural_reason="t", affected_files=("NOTE.md",),
            expected_behavior="none", preservation_requirements=(), known_defects=(), transformation_scope="documentation",
            baseline_reference=baseline, evidence=(), edits=(FileEdit("NOTE.md", "write", "final\n", ""),),
            status=TransformationStatus.PROPOSED)


class DeclinedThenRewrites(Rewrites):
    """First offers a change to a test file that cites a finding (declined), then rewrites NOTE.md."""

    def __init__(self):
        super().__init__()
        self.offered = False

    def propose(self, target, observed, baseline):
        from cns.seat import FileEdit
        from warden.models import Defect, DefectSeverity, Transformation, TransformationStatus
        if not self.offered:
            self.offered = True
            return Transformation(
                target=str(Path(target).resolve()), intent="t", architectural_reason="t",
                affected_files=("tests/test_a.py",), expected_behavior="none", preservation_requirements=(),
                known_defects=(Defect(summary="unused", severity=DefectSeverity.LOW, ghost_id="ghost-unused"),),
                transformation_scope="documentation", baseline_reference=baseline, evidence=(),
                edits=(FileEdit("tests/test_a.py", "write", "x = 1\n", ""),), status=TransformationStatus.PROPOSED)
        return super().propose(target, observed, baseline)


def _run_with(root, drafter, finisher=None):
    auth = grant("william", "transform", str(root.resolve()), "documentation", "judge integration")
    team = TagTeam(drafter=drafter, finisher=finisher, judge=WithBaseline(), ghost_tools_root=Path("."),
                   swizzle_root=Path("."), assay_root=Path("."), assay_floor=3)
    return team.run(root, findings=[], authorization=auth)


def _evidence_the_judge_saw(monkeypatch):
    seen = []

    class Spy(WithBaseline):
        def decide(self, evidence):
            seen.append(evidence)
            return super().decide(evidence)

    monkeypatch.setattr(sys.modules[__name__], "WithBaseline", Spy)
    return seen


def test_a_finishing_change_that_belongs_to_no_cycle_is_still_accepted(tmp_path, stack, monkeypatch):
    seen = _evidence_the_judge_saw(monkeypatch)
    result = _run_with(_repo(tmp_path), Nothing(), Finishes())
    ev = seen[0]
    assert [o for _, o in ev.cycles] == ["NOTHING_TO_PROPOSE"] and ev.changed == (("NOTE.md", "write"),)
    assert result.decision == "ACCEPT", result.verdict.reasons
    assert (tmp_path / "NOTE.md").read_text(encoding="utf-8") == "final\n"


def test_a_declined_proposal_beside_an_applied_change_is_still_accepted(tmp_path, stack, monkeypatch):
    seen = _evidence_the_judge_saw(monkeypatch)
    root = _repo(tmp_path)
    stack["ghost"] = ()
    result = _run_with(root, DeclinedThenRewrites())
    ev = seen[0]
    assert [o for _, o in ev.cycles] == ["DECLINED", "APPLIED", "NOTHING_TO_PROPOSE"]
    assert ev.declined == ("ghost-unused",) and ev.changed == (("NOTE.md", "write"),)
    assert result.decision == "ACCEPT", result.verdict.reasons


def test_an_applied_change_and_a_finishing_change_together_are_still_accepted(tmp_path, stack, monkeypatch):
    seen = _evidence_the_judge_saw(monkeypatch)
    result = _run_with(_repo(tmp_path), Rewrites(), Finishes())
    assert len(seen[0].changed) == 2 and [o for _, o in seen[0].cycles] == ["APPLIED", "NOTHING_TO_PROPOSE"]
    assert result.decision == "ACCEPT", result.verdict.reasons
