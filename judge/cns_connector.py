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

The evidence is read once into a frozen copy. The digest is computed from that
copy and the Judge decides that same copy, so the evidence bound and the
evidence judged cannot differ. A digest names the evidence that was judged; it
does not show that the evidence is true or complete.

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

from .seat import ROW_ATTRIBUTES, Judge

__all__ = [
    "JudgeGate",
    "cns_chain",
]

#: What ``subject`` is set to when the caller does not name the judged evidence.
DEFAULT_SUBJECT = "run-evidence"

#: Deepest nesting the digest will follow. Evidence is a few levels deep; this stops a cycle.
_MAX_DEPTH = 32


class _Row:
    """A read-only copy of one evidence row: the attributes it had when it was copied, and nothing else."""

    __slots__ = ("_values",)

    def __init__(self, values: dict) -> None:
        object.__setattr__(self, "_values", values)

    def __getattr__(self, name: str) -> object:
        try:
            return object.__getattribute__(self, "_values")[name]
        except KeyError:
            raise AttributeError(name) from None

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("a copied evidence row cannot be changed")


def _snapshot(value: object, depth: int = 0) -> object:
    """Read the evidence once into a frozen copy: scalars, dicts, tuples and read-only rows.

    The digest is computed from this copy and the Judge decides this copy, so nothing can differ between the
    evidence that was bound and the evidence that was judged: not a later change to the original, not a mapping
    whose ``items`` and ``get`` disagree, not an attribute that answers differently each time it is read.
    A row keeps its dataclass fields, its instance attributes and every attribute the Judge reads
    (``judge.seat.ROW_ATTRIBUTES``), including one that lives on the class, so what the Judge reads is digested.
    """
    if depth > _MAX_DEPTH:
        raise TypeError("the evidence is nested too deeply to bind a verdict to")
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {k: _snapshot(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(_snapshot(v, depth + 1) for v in value)
    names = set(getattr(value, "__dict__", ()))
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        names |= {f.name for f in dataclasses.fields(value)}
    values: dict = {}
    for n in sorted((names | ROW_ATTRIBUTES) - {n for n in names if n.startswith("_")}):
        try:
            values[n] = getattr(value, n)
        except AttributeError:
            if n in names:
                raise TypeError(f"{type(value).__name__}.{n} cannot be read") from None
    if not values:
        raise TypeError(f"cannot bind a verdict to {type(value).__name__}")
    return _Row({n: _snapshot(v, depth + 1) for n, v in values.items()})


def _plain(value: object) -> object:
    """A snapshot as plain content a digest can bind: scalars, mappings and lists."""
    if isinstance(value, _Row):
        return {n: _plain(v) for n, v in object.__getattribute__(value, "_values").items()}
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [_plain(v) for v in value]
    return value


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
            frozen = _snapshot(candidate)
            content = _plain(frozen)
            if not isinstance(content, dict):
                raise TypeError(f"{type(candidate).__name__} is not run evidence")
            digest = subject_digest(content)
        except (TypeError, ValueError, RecursionError) as exc:
            return self._result(
                GateOutcome.TERMINAL_BREACH,
                f"the evidence cannot be bound to a verdict, so nothing is approved ({exc})",
            )
        # The Judge decides the frozen copy the digest was computed from, never the original object, so the
        # verdict is about exactly the bound evidence. The Judge reads its input defensively (by attribute, and
        # answers INSUFFICIENT for anything it cannot read), so the cast changes no behaviour.
        verdict = self._judge.decide(cast(Evidence, frozen))
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
