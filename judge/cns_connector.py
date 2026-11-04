"""The Judge as a CNS gate (``cns.gate``).

The Judge already reads its evidence and returns its verdict as CNS rows
(``cns.seat``). This module adds the other direction: the Judge's decision, offered
through CNS's shared gate contract so any consumer that speaks it can use the Judge.
Nothing here is imported by ``judge`` itself; import this module to use it.

What connecting means
---------------------
The Judge keeps its own answer, a ``Verdict`` of ACCEPT, REJECT or
INSUFFICIENT. CNS's shared gate contract is ``cns.gate.GateResult``. This
module wraps the Judge as a ``cns.gate.Gate`` so a consumer that speaks CNS
can resolve the Judge's verdict alongside gates from other repositories.
Nothing about how the Judge decides changes: :class:`JudgeGate` hands the
evidence to ``Judge.decide`` and translates the answer.

The mapping, and why
--------------------
=====================  ===========================================
Judge                  CNS
=====================  ===========================================
gate position          ``OMEGA``. The Judge reads what a whole run
                       produced; the change does not stand unless
                       it accepts. It has no precondition end, and
                       this connector does not invent one.
ACCEPT                 ``PASS``
REJECT                 ``TERMINAL_BREACH``  (the evidence shows harm)
INSUFFICIENT           ``RETRY``  (something was not measured: bring
                       the missing evidence and ask again; or, in the
                       two ruled cases, the change is held for a named
                       human, who keeps or drops it)
any other answer       ``TERMINAL_BREACH``  (an answer the connector
                       does not recognise is never read as permission)
reasons                ``reason``, joined with ``"; "``
judged evidence        ``subject`` (a label, default ``"run-evidence"``)
                       and ``subject_digest``, which is
                       ``cns.gate.subject_digest`` of everything the
                       evidence carries
=====================  ===========================================

A verdict is bound to the evidence it judged. The digest covers every
attribute on the evidence and on the rows inside it, not only the declared
fields, because the Judge reads some attributes that are not declared (the
suite flags ``forged`` and ``text_only``, Ghost's baseline). Evidence that
cannot be described unambiguously (a wrong type, NaN, a cycle, a set) is a
``TERMINAL_BREACH``, never a pass.

Because the Judge has only the outcome end, ``cns_chain(...).complete()`` is
``False`` by design. A consumer that wants a complete chain supplies the
``alpha`` end from a repository that has one.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import cast

from cns.gate import GateChain, GateOutcome, GatePosition, GateResult, subject_digest
from cns.seat import Evidence

from .seat import Judge

__all__ = [
    "JudgeGate",
    "cns_chain",
]

#: What ``subject`` is set to when the caller does not name the judged evidence.
DEFAULT_SUBJECT = "run-evidence"

#: Deepest nesting the digest will follow. Evidence is a few levels deep; this stops a cycle.
_MAX_DEPTH = 32


def _plain(value: object, depth: int = 0) -> object:
    """Evidence as plain content a digest can bind: scalars, mappings and lists.

    Rows are read through their dataclass fields and their instance attributes,
    so an attribute set after construction is bound too.
    """
    if depth > _MAX_DEPTH:
        raise TypeError("the evidence is nested too deeply to bind a verdict to")
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {k: _plain(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v, depth + 1) for v in value]
    names = set(getattr(value, "__dict__", ()))
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        names |= {f.name for f in dataclasses.fields(value)}
    names = {n for n in names if not n.startswith("_")}
    if not names:
        raise TypeError(f"cannot bind a verdict to {type(value).__name__}")
    return {n: _plain(getattr(value, n), depth + 1) for n in names}


class JudgeGate:
    """The Judge as a ``cns.gate.Gate`` at the OMEGA end.

    ``check`` takes the run's evidence, has the Judge decide it, and returns
    the verdict as a ``cns.gate.GateResult`` bound to that evidence. An
    exception from the Judge propagates; it is never turned into a PASS.
    """

    def __init__(self, judge: Judge | None = None, *, subject: str = DEFAULT_SUBJECT) -> None:
        self._judge = judge if judge is not None else Judge()
        self._subject = subject

    name: str = "judge.verdict"
    position: GatePosition = GatePosition.OMEGA

    def _result(self, outcome: GateOutcome, reason: str, digest: str = "") -> GateResult:
        return GateResult(
            gate=self.name,
            position=self.position,
            outcome=outcome,
            reason=reason,
            subject=self._subject,
            subject_digest=digest,
        )

    def check(self, candidate: object) -> GateResult:
        try:
            content = _plain(candidate)
            if not isinstance(content, dict):
                raise TypeError(f"{type(candidate).__name__} is not run evidence")
            digest = subject_digest(content)
        except (TypeError, ValueError, RecursionError) as exc:
            return self._result(
                GateOutcome.TERMINAL_BREACH,
                f"the evidence cannot be bound to a verdict, so nothing is approved ({exc})",
            )
        # The gate contract hands over any object. The Judge reads its input defensively and answers
        # INSUFFICIENT for anything that is not readable evidence, so the cast changes no behaviour.
        verdict = self._judge.decide(cast(Evidence, candidate))
        outcomes = {
            "ACCEPT": GateOutcome.PASS,
            "REJECT": GateOutcome.TERMINAL_BREACH,
            "INSUFFICIENT": GateOutcome.RETRY,
        }
        decision = verdict.decision
        if not isinstance(decision, str) or decision not in outcomes:
            return self._result(
                GateOutcome.TERMINAL_BREACH,
                f"the Judge answered {decision!r}, which this connector does not recognise; "
                "an unknown answer is never read as permission",
                digest,
            )
        return self._result(outcomes[decision], "; ".join(verdict.reasons), digest)


def cns_chain(judge: Judge | None = None, *, subject: str = DEFAULT_SUBJECT) -> GateChain:
    """A ``cns.gate.GateChain`` holding the Judge in the ``omega`` slot.

    ``alpha`` stays empty: the Judge has no precondition end.
    """
    return GateChain(omega=(JudgeGate(judge, subject=subject),))
