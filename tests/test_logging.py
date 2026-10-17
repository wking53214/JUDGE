"""The decision seam is logged, and logging never changes a verdict."""

import logging

import pytest
from test_judge import _evidence

from judge import Judge


def test_a_decision_is_logged_at_info_with_its_target(caplog):
    caplog.set_level(logging.INFO, logger="judge")
    verdict = Judge().decide(_evidence())
    assert verdict.decision == "ACCEPT"
    assert any("verdict ACCEPT for target /t" in r.getMessage() for r in caplog.records)


def test_reasons_are_logged_at_debug_only(caplog):
    caplog.set_level(logging.INFO, logger="judge")
    Judge().decide(_evidence())
    assert not [r for r in caplog.records if r.levelno == logging.DEBUG]
    caplog.clear()
    caplog.set_level(logging.DEBUG, logger="judge")
    Judge().decide(_evidence())
    assert [r for r in caplog.records if r.getMessage().startswith("reason:")]


def test_unreadable_evidence_is_a_logged_warning_and_insufficient(caplog):
    caplog.set_level(logging.INFO, logger="judge")
    verdict = Judge().decide(object())
    assert verdict.decision == "INSUFFICIENT"
    assert [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("verdict INSUFFICIENT" in r.getMessage() for r in caplog.records)


def test_an_unexpected_exception_is_logged_and_still_insufficient(caplog, monkeypatch):
    import judge.seat as seat

    def boom(evidence):
        raise ZeroDivisionError

    monkeypatch.setattr(seat, "_decide", boom)
    verdict = Judge().decide(_evidence())
    assert verdict.decision == "INSUFFICIENT" and "ZeroDivisionError" in verdict.reasons[0]


class Hostile:
    """Evidence whose target cannot even be turned into text."""

    def __getattr__(self, name):
        raise RuntimeError(name)


def test_logging_cannot_turn_a_verdict_into_an_error():
    assert Judge().decide(Hostile()).decision == "INSUFFICIENT"


def test_a_target_that_breaks_str_does_not_change_the_verdict(caplog):
    class BadTarget(str):
        def __str__(self):
            raise ValueError

    caplog.set_level(logging.INFO, logger="judge")
    assert Judge().decide(_evidence(target=BadTarget("/t"))).decision == "ACCEPT"


@pytest.mark.parametrize("level", [logging.DEBUG, logging.CRITICAL])
def test_the_verdict_is_the_same_whatever_the_log_level(level, caplog):
    caplog.set_level(level, logger="judge")
    assert Judge().decide(_evidence()).decision == "ACCEPT"
    assert Judge().decide(_evidence(suite_after=None)).decision != "ACCEPT"


def test_the_package_installs_no_handler_but_a_null_one():
    handlers = logging.getLogger("judge").handlers
    assert handlers and all(isinstance(h, logging.NullHandler) for h in handlers)
