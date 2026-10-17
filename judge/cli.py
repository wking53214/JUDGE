"""The ``judge`` command line: decide on one piece of evidence and say so in the exit code.

    judge --version
    judge decide EVIDENCE.json     # or "-" to read standard input

``decide`` reads a JSON object with the fields of ``cns.seat.Evidence`` (the same input
``Judge.decide`` takes), prints the decision as JSON on standard output and exits:

    0  ACCEPT (the only approval)
    1  anything else: REJECT, INSUFFICIENT, or an input the Judge could not judge
    2  usage error: bad arguments, a file that cannot be read, text that is not JSON

The command fails closed. Any exception while building or judging the evidence yields an
INSUFFICIENT decision and exit 1; nothing but an explicit ACCEPT from the Judge exits 0.
The command reads one file (or standard input) and writes only to standard output and
standard error. Logs go to standard error: ``-v`` shows decisions, ``-vv`` adds each reason.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from cns.seat import Evidence, Verdict
from cns.suite import SuiteRun

from ._version import __version__
from .seat import NAME, Judge

__all__ = ["main", "evidence_from_data"]

EXIT_APPROVED = 0
EXIT_NOT_APPROVED = 1
EXIT_USAGE = 2

log = logging.getLogger(__name__)

#: Attributes the Judge reads from a suite run that are not SuiteRun fields (a forged or text-only result, other exit-code names).
_SUITE_EXTRAS = ("forged", "forged_output", "text_only", "returncode", "exitcode", "exit_status")
_SUITE_FIELDS = {f.name for f in dataclasses.fields(SuiteRun)}
_EVIDENCE_FIELDS = {f.name: f for f in dataclasses.fields(Evidence)}
_SUITE_KEYS = ("suite_before", "suite_after")


def _freeze(value: Any) -> Any:
    """JSON lists become tuples (the declared shape of the evidence); mappings and scalars stay."""
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, dict):
        return {k: _freeze(v) for k, v in value.items()}
    return value


def _suite(value: Any, name: str) -> Any:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object or null, not {type(value).__name__}")
    unknown = sorted(set(value) - _SUITE_FIELDS - set(_SUITE_EXTRAS))
    if unknown:
        raise ValueError(f"{name} has unknown field(s): {', '.join(unknown)}")
    try:
        run = SuiteRun(**{k: v for k, v in value.items() if k in _SUITE_FIELDS})
    except TypeError as exc:
        raise ValueError(f"{name} is not a suite run ({exc})") from None
    for key in _SUITE_EXTRAS:
        if key in value:
            object.__setattr__(run, key, value[key])
    return run


def evidence_from_data(data: object) -> Evidence:
    """Build ``cns.seat.Evidence`` from decoded JSON. Raises ValueError if it does not match the schema."""
    if not isinstance(data, dict):
        raise ValueError(f"the decision input must be a JSON object, not {type(data).__name__}")
    unknown = sorted(set(data) - set(_EVIDENCE_FIELDS))
    if unknown:
        raise ValueError(f"unknown field(s): {', '.join(unknown)}")
    required = [
        n for n, f in _EVIDENCE_FIELDS.items()
        if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
    ]
    missing = [n for n in required if n not in data]
    if missing:
        raise ValueError(f"missing field(s): {', '.join(missing)}")
    values = {k: (_suite(v, k) if k in _SUITE_KEYS else _freeze(v)) for k, v in data.items()}
    return Evidence(**values)


def _not_judged(why: str) -> Verdict:
    return Verdict("INSUFFICIENT", (f"the decision input could not be judged ({why}), so nothing can be approved",), NAME)


def _decide(data: object) -> Verdict:
    try:
        verdict = Judge().decide(evidence_from_data(data))
    except ValueError as exc:
        log.warning("decision input does not match the evidence schema: %s", exc)
        return _not_judged(str(exc))
    except Exception as exc:  # fail closed: whatever went wrong, nothing is approved
        log.warning("decision input could not be judged (%s)", type(exc).__name__)
        return _not_judged(type(exc).__name__)
    return verdict


def _read(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    return Path(source).read_text(encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="judge",
        description="The third party that decides. Exit 0 only for ACCEPT; 1 for any other decision; 2 for a usage error.",
    )
    parser.add_argument("--version", action="version", version=f"judge {__version__}")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="log decisions to stderr (-vv: each reason too)")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    decide = sub.add_parser("decide", help="decide on evidence given as a JSON file and print the decision as JSON")
    decide.add_argument("-v", "--verbose", action="count", default=argparse.SUPPRESS, help="same as -v before the command")
    decide.add_argument("input", metavar="EVIDENCE.json", help='path to the evidence, or "-" for standard input')
    return parser


def _run_decide(source: str) -> int:
    try:
        text = _read(source)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"judge: cannot read {source!r}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_USAGE
    try:
        data = json.loads(text)
    except ValueError as exc:
        print(f"judge: {source!r} is not valid JSON: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except (RecursionError, MemoryError) as exc:  # input nested or large enough to exhaust the decoder: not usable JSON
        print(f"judge: {source!r} cannot be decoded as JSON ({type(exc).__name__}): too deeply nested or too large", file=sys.stderr)
        return EXIT_USAGE
    verdict = _decide(data)
    print(json.dumps({"decision": str(verdict.decision), "reasons": [str(r) for r in verdict.reasons], "judge": str(verdict.judge)},
                     indent=2))
    return EXIT_APPROVED if verdict.decision == "ACCEPT" else EXIT_NOT_APPROVED


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line; returns the exit code (the console script exits with it)."""
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse exits for --version, --help and bad usage
        code = exc.code
        return code if isinstance(code, int) else (EXIT_APPROVED if code is None else EXIT_USAGE)
    root = logging.getLogger("judge")
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    previous = root.level
    root.addHandler(handler)
    root.setLevel((logging.WARNING, logging.INFO, logging.DEBUG)[min(args.verbose, 2)])
    try:
        return _run_decide(args.input)
    finally:
        root.removeHandler(handler)
        root.setLevel(previous)
