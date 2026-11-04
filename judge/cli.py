"""The ``judge`` command line: decide on one piece of evidence and say so in the exit code.

    judge --version
    judge decide EVIDENCE.json     # or "-" to read standard input

``decide`` reads a JSON object with the fields of ``cns.seat.Evidence`` (the same input
``Judge.decide`` takes), prints the decision as JSON on standard output and exits:

    0  ACCEPT (the only approval), and the decision was delivered or the reader of standard output had left
    1  anything else: REJECT, INSUFFICIENT, an input the Judge could not judge, or an ACCEPT that could not be delivered
    2  usage error: bad arguments, a file or standard input that cannot be read, text that is not JSON

The command fails closed. Any exception while building or judging the evidence yields an
INSUFFICIENT decision and exit 1; nothing but an explicit ACCEPT from the Judge exits 0.
The command reads one file (or standard input) and writes only to standard output and
standard error. Logs go to standard error: ``-v`` shows decisions, ``-vv`` adds each reason.

Delivery of the decision. The decision is the output, so an ACCEPT whose decision was never delivered is not an approval:

* The reader of standard output left (a broken pipe, ``judge decide FILE | head``): nothing is printed and the exit code is
  the one earned (0 for ACCEPT, 1 otherwise). The caller chose to stop reading; the Judge did decide.
* The decision could not be delivered for any other reason (standard output is closed, or the write fails, for example a full
  device): one plain line on standard error, no traceback, and exit 1 for every decision. An ACCEPT that was not delivered
  exits 1, never 0.
* Standard input closed or unreadable (``judge decide - <&-``): one plain line on standard error and exit 2.

A closed or failed standard error only loses that one line; the exit code is still the one above. ``main`` never replaces
``sys.stdout``. When a write to the process's real standard output fails, that stream is closed so the interpreter does not
try to flush the same undeliverable bytes again at exit (which would end in exit status 120 and a message from Python).
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

#: What ``_deliver`` answers when the reader of standard output went away (a broken pipe).
_READER_LEFT = "reader left"

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


def _say(message: str) -> None:
    """One plain line on standard error, or nothing when standard error is closed or fails (it has no other channel)."""
    err = sys.stderr
    if err is None:
        return
    try:
        print(f"judge: {message}", file=err)
        err.flush()
    except (OSError, ValueError):
        pass


def _read(source: str) -> str:
    if source == "-":
        if sys.stdin is None:
            raise OSError("standard input is closed")
        return sys.stdin.read()
    return Path(source).read_text(encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="judge",
        allow_abbrev=False,  # a prefix such as --verbos is a usage error, never a guess
        description="The third party that decides. Exit 0 only for ACCEPT; 1 for any other decision; 2 for a usage error.",
    )
    parser.add_argument("--version", action="version", version=f"judge {__version__}")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="log decisions to stderr (-vv: each reason too)")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    decide = sub.add_parser("decide", allow_abbrev=False,
                          help="decide on evidence given as a JSON file and print the decision as JSON")
    decide.add_argument("-v", "--verbose", action="count", default=argparse.SUPPRESS, help="same as -v before the command")
    decide.add_argument("input", metavar="EVIDENCE.json", help='path to the evidence, or "-" for standard input')
    return parser


def _deliver(text: str) -> str | None:
    """Print ``text`` on standard output. None when delivered, ``_READER_LEFT`` on a broken pipe, else why it was not."""
    out = sys.stdout
    if out is None:
        return "standard output is closed"
    try:
        print(text, file=out)
        out.flush()
        return None
    except BrokenPipeError:
        failure = _READER_LEFT
    except (OSError, ValueError) as exc:  # ValueError: the stream was closed under us
        failure = f"{type(exc).__name__}: {exc}"
    real = sys.__stdout__
    if real is not None and out is real:
        # Buffered bytes that could not be written are still queued; the interpreter would try them again at exit and end in
        # status 120. Closing the stream drops them (the close error is the same failure again, already recorded).
        try:
            real.close()
        except (OSError, ValueError):
            pass
    return failure


def _run_decide(source: str) -> int:
    try:
        text = _read(source)
    except (OSError, ValueError) as exc:  # ValueError covers UnicodeDecodeError and a stream closed under us
        _say(f"cannot read {source!r}: {type(exc).__name__}: {exc}")
        return EXIT_USAGE
    try:
        data = json.loads(text)
    except ValueError as exc:
        _say(f"{source!r} is not valid JSON: {exc}")
        return EXIT_USAGE
    except (RecursionError, MemoryError) as exc:  # input nested or large enough to exhaust the decoder: not usable JSON
        _say(f"{source!r} cannot be decoded as JSON ({type(exc).__name__}): too deeply nested or too large")
        return EXIT_USAGE
    verdict = _decide(data)
    failure = _deliver(json.dumps({"decision": str(verdict.decision), "reasons": [str(r) for r in verdict.reasons],
                                   "judge": str(verdict.judge)}, indent=2))
    if failure == _READER_LEFT:
        # The reader went away (``judge decide FILE | head``) and chose to stop reading: the exit code stays the earned one.
        pass
    elif failure is not None:
        _say(f"the decision ({verdict.decision}) could not be delivered on standard output ({failure})"
             + ("; an ACCEPT that was not delivered exits 1" if verdict.decision == "ACCEPT" else ""))
        return EXIT_NOT_APPROVED
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
