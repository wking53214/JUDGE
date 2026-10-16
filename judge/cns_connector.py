"""Optional connector to CNS (``cns.gate``).

The Judge is independent. It has no CNS dependency, imports nothing from CNS
when it loads, and its whole suite passes with CNS absent. This module is the
one place that knows CNS exists, and it asks for CNS only when one of its
functions is called. Without CNS installed those calls raise
:class:`CnsNotInstalled` with the install command; nothing else in the Judge
is affected.

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
INSUFFICIENT           ``RETRY``  (something was not measured; bring
                       the missing evidence and ask again)
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

Install with the extra: ``pip install 'judge[cns]'``.
"""

from __future__ import annotations

import dataclasses
import importlib
from collections.abc import Mapping
from types import ModuleType
from typing import Any

from .seat import Judge

__all__ = [
    "CnsNotInstalled",
    "JudgeGate",
    "cns_available",
    "cns_chain",
]

INSTALL_HINT = "pip install 'judge[cns]'"

#: What ``subject`` is set to when the caller does not name the judged evidence.
DEFAULT_SUBJECT = "run-evidence"

#: Deepest nesting the digest will follow. Evidence is a few levels deep; this stops a cycle.
_MAX_DEPTH = 32


class CnsNotInstalled(ImportError):
    """Raised by this module's functions when ``cns`` cannot be imported."""


def _cns_gate() -> ModuleType:
    """Import ``cns.gate`` on demand, or say exactly what is missing."""
    try:
        return importlib.import_module("cns.gate")
    except ImportError as exc:
        raise CnsNotInstalled(
            "judge.cns_connector needs the CNS package (cns.gate), which is not "
            f"installed. Install it with: {INSTALL_HINT}. The Judge itself works "
            "without it."
        ) from exc


def cns_available() -> bool:
    """Whether the CNS gate contract can be imported in this environment."""
    try:
        _cns_gate()
    except CnsNotInstalled:
        return False
    return True


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
        _cns_gate()  # fail here, at construction, not on first use
        self._judge = judge if judge is not None else Judge()
        self._subject = subject

    @property
    def name(self) -> str:
        return "judge.verdict"

    @property
    def position(self) -> Any:
        return _cns_gate().GatePosition.OMEGA

    def _result(self, outcome: Any, reason: str, digest: str = "") -> Any:
        gate = _cns_gate()
        return gate.GateResult(
            gate=self.name,
            position=gate.GatePosition.OMEGA,
            outcome=outcome,
            reason=reason,
            subject=self._subject,
            subject_digest=digest,
        )

    def check(self, candidate: object) -> Any:
        gate = _cns_gate()
        try:
            content = _plain(candidate)
            if not isinstance(content, dict):
                raise TypeError(f"{type(candidate).__name__} is not run evidence")
            digest = gate.subject_digest(content)
        except (TypeError, ValueError, RecursionError) as exc:
            return self._result(
                gate.GateOutcome.TERMINAL_BREACH,
                f"the evidence cannot be bound to a verdict, so nothing is approved ({exc})",
            )
        verdict = self._judge.decide(candidate)
        outcomes = {
            "ACCEPT": gate.GateOutcome.PASS,
            "REJECT": gate.GateOutcome.TERMINAL_BREACH,
            "INSUFFICIENT": gate.GateOutcome.RETRY,
        }
        decision = verdict.decision
        if not isinstance(decision, str) or decision not in outcomes:
            return self._result(
                gate.GateOutcome.TERMINAL_BREACH,
                f"the Judge answered {decision!r}, which this connector does not recognise; "
                "an unknown answer is never read as permission",
                digest,
            )
        return self._result(outcomes[decision], "; ".join(verdict.reasons), digest)


def cns_chain(judge: Judge | None = None, *, subject: str = DEFAULT_SUBJECT) -> Any:
    """A ``cns.gate.GateChain`` holding the Judge in the ``omega`` slot.

    ``alpha`` stays empty: the Judge has no precondition end.
    """
    return _cns_gate().GateChain(omega=(JudgeGate(judge, subject=subject),))
