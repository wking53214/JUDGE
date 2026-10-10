"""Seated in Warden's loop, with the real Warden: the Judge accepts a clean run and turns away a harmful one."""

from pathlib import Path

import pytest

import warden.tagteam as tagteam
from warden.authorization import grant
from warden.tagteam import TagTeam

from judge import Judge

HELD = ({"scenario": "a", "severity": "high", "status": "held"},)
VIOLATED = ({"scenario": "a", "severity": "high", "status": "violated"},)


class Rewrites:
    """A stand-in Drafter that rewrites NOTE.md once."""

    def __init__(self):
        self.done = False

    def propose(self, target, observed, baseline):
        from warden.models import FileEdit, Transformation, TransformationStatus
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
    """Today's Warden does not carry Ghost's baseline report; this hands it to the Judge the way Warden will."""

    baseline = {"path": None, "suppressed": 0}

    def decide(self, evidence):
        from types import SimpleNamespace
        view = SimpleNamespace(**vars(evidence), ghost_baseline_before=self.baseline, ghost_baseline_after=self.baseline)
        return super().decide(view)


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
    assert (tmp_path / "NOTE.md").read_text(encoding="utf-8") == "new\n"


def test_without_a_baseline_report_the_real_warden_run_is_unjudged(tmp_path, stack):
    result = _run(_repo(tmp_path), judge=Judge())
    assert result.decision == "ACCEPT_UNVERIFIED" and result.verdict.decision == "INSUFFICIENT"
    assert any("baseline" in r for r in result.verdict.reasons)
