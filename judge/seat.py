"""The Judge's seat in Warden's loop: evidence in, verdict out.

The Judge decides and does nothing else. It does not run the tests, ask Ghost,
attack the governor or touch a file; others measured, and Warden handed it what
they measured. Its rules are deliberately few and written down here, so a person
can read why a run was accepted or turned away.

THE GOVERNING RULE: UNKNOWN IS NOT APPROVED. Only values the Judge recognizes
count as good. Anything odd, missing, misspelled or of the wrong type is never
read as fine.

THE RULES, in order. The first group that fires decides.

  INSUFFICIENT  (checked first) the evidence cannot be read at all: a wrong
                type, a negative or fractional count, a missing field. Nothing
                is approved, and the Judge never raises an error.
  REJECT        the evidence shows harm:
    the suite is red, or fewer tests pass than before
    more tests are skipped (or expected-to-fail) than before
    tests or test settings were changed (the Warden's list, or any path that
      looks like a test, a test setting or a CI file)
    an edit reached outside the project, or into git or environment folders
    Ghost reports a finding at the end that it did not report at the start
      (counted one by one, so a repeated finding is new)
    SWIZZLE's proofs are exactly False
    SWIZZLE's attacks found an invariant violated (any severity except low;
      an unknown severity counts as high)
    ASSAY's answer key is exactly False, Ghost caught fewer failure modes than
      the floor, or the numbers contradict each other
    code changed under a documentation grant
  INSUFFICIENT  nothing shows harm, but something is unknown:
    the final suite run, Ghost, SWIZZLE's proofs or attacks, or ASSAY's grade
      is missing, or not exactly the expected value
    an attack gave no clean answer (error, timeout, crashed, unknown, not run),
      was not a proper entry, or no attack was attempted at all
    ASSAY's floor, caught or failure_modes is missing or not a whole number
    some tests did not run before, and code was changed
    the Warden reports a check that never ran (anything but 'judge')
  ACCEPT        everything required ran, nothing shows harm, nothing is unknown.

A run that changed nothing is ACCEPTed only if the evidence is complete.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping

from warden.roles import Evidence, Verdict

NAME = "judge 0.2"

_PROSE = (".md", ".rst", ".txt")
_TEST_DIRS = {"tests", "test"}
_TEST_FILES = {"conftest.py", "pyproject.toml", "pytest.ini", "tox.ini", "setup.cfg",
               "noxfile.py", ".coveragerc", "makefile"}
_OUTSIDE_DIRS = {"..", ".git", ".venv"}
_HARM_SEVERITIES = {"high", "medium", "critical", "severe"}
#: Change kinds that only reformat. There are none today, so nothing is excused.
_FORMAT_ONLY_KINDS: frozenset = frozenset()


class _Unreadable(Exception):
    def __init__(self, what: str):
        super().__init__(what)
        self.what = what


def _unreadable(what: str) -> Verdict:
    return Verdict("INSUFFICIENT",
                   (f"the evidence could not be read ({what}), so nothing can be approved",), NAME)


class Judge:
    #: The seat contract this Judge was written against. Warden warns when it is missing and refuses a mismatch.
    requires_contract = "1"

    def decide(self, evidence: Evidence) -> Verdict:
        try:
            return _decide(evidence)
        except _Unreadable as exc:
            return _unreadable(what=exc.what)
        except Exception as exc:  # anything odd in the evidence: fail closed, never raise
            return _unreadable(what=type(exc).__name__)


# ---- reading the evidence safely -------------------------------------------------

def _is_count(x: object) -> bool:
    return isinstance(x, int) and not isinstance(x, bool) and x >= 0


def _field(e: object, name: str) -> object:
    try:
        return getattr(e, name)
    except AttributeError:
        raise _Unreadable(f"{name} is missing") from None


def _strings(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)) or not all(isinstance(x, str) for x in value):
        raise _Unreadable(f"{name} is a {type(value).__name__}, not a list of text")
    return tuple(value)


def _optional_strings(value: object, name: str):
    return None if value is None else _strings(value, name)


class _Suite:
    def __init__(self, run: object, name: str):
        ran = getattr(run, "ran", None)
        if not isinstance(ran, bool):
            raise _Unreadable(f"{name}.ran is a {type(ran).__name__}")
        counts = {}
        for f in ("passed", "failed", "errors", "skipped", "xfailed"):
            v = getattr(run, f, 0) if f == "xfailed" else getattr(run, f, None)
            if not _is_count(v):
                raise _Unreadable(f"{name}.{f} is a {type(v).__name__}, not a count")
            counts[f] = v
        self.ran, self.counts, self.run = ran, counts, run
        self.passed, self.failed, self.errors = counts["passed"], counts["failed"], counts["errors"]
        self.skipped, self.xfailed = counts["skipped"], counts["xfailed"]

    @property
    def green(self) -> bool:
        return self.ran and self.passed > 0 and self.failed == 0 and self.errors == 0

    @property
    def not_run(self) -> int:
        return self.skipped + self.xfailed

    def describe(self) -> str:
        if not self.ran:
            return f"did not run ({getattr(self.run, 'reason', '')})"
        return (f"{self.passed} passed, {self.failed} failed, {self.errors} errors, "
                f"{self.skipped} skipped, {self.xfailed} xfailed")


def _suite(run: object, name: str):
    return None if run is None else _Suite(run, name)


def _norm_path(path: str) -> str:
    p = "/".join(path.strip().lower().split("\\"))
    while p.startswith("./"):
        p = p[2:]
    return p


def _parts(norm: str) -> list[str]:
    return [c for c in norm.split("/") if c not in ("", ".")]


def _is_judging(norm: str, kind: str) -> bool:
    if kind in _FORMAT_ONLY_KINDS:
        return False
    parts = _parts(norm)
    if not parts:
        return False
    name = parts[-1]
    return (bool(set(parts[:-1]) & _TEST_DIRS) or name in _TEST_DIRS or name.startswith("test_")
            or name.endswith("_test.py") or name in _TEST_FILES or ".github" in parts)


def _reaches_outside(norm: str) -> bool:
    absolute = norm.startswith("/") or norm.startswith("~") or (len(norm) > 1 and norm[1] == ":")
    return absolute or bool(set(_parts(norm)) & _OUTSIDE_DIRS)


# ---- the decision ----------------------------------------------------------------

def _decide(e: Evidence) -> Verdict:
    scope = _field(e, "scope")
    if not isinstance(scope, str):
        raise _Unreadable(f"scope is a {type(scope).__name__}, not text")
    raw_changed = _field(e, "changed")
    if not isinstance(raw_changed, (tuple, list)):
        raise _Unreadable(f"changed is a {type(raw_changed).__name__}, not a list of edits")
    changed: list[tuple[str, str]] = []
    for item in raw_changed:
        if (not isinstance(item, (tuple, list)) or len(item) != 2
                or not isinstance(item[0], str) or not isinstance(item[1], str)):
            raise _Unreadable(f"a changed entry is a {type(item).__name__}, not a (path, kind) pair")
        changed.append((item[0], item[1]))
    judging_listed = _strings(_field(e, "judging_files_touched"), "judging_files_touched")
    before, after = _suite(_field(e, "suite_before"), "suite_before"), _suite(_field(e, "suite_after"), "suite_after")
    g_before = _optional_strings(_field(e, "ghost_before"), "ghost_before")
    g_after = _optional_strings(_field(e, "ghost_after"), "ghost_after")
    unmeasured = _strings(_field(e, "unmeasured"), "unmeasured")
    proofs = _field(e, "swizzle_proofs")
    attacks = _field(e, "attacks")
    if attacks is not None and not isinstance(attacks, (tuple, list)):
        raise _Unreadable(f"attacks is a {type(attacks).__name__}, not a list")
    assay = getattr(e, "assay", None)
    if assay is not None and not isinstance(assay, Mapping):
        raise _Unreadable(f"assay is a {type(assay).__name__}, not a report")

    harm: list[str] = []
    unknown: list[str] = []

    # the suite
    if after is not None:
        if not after.green:
            harm.append(f"the suite is not green at the end ({after.describe()})")
        if before is not None:
            if after.passed < before.passed:
                harm.append(f"fewer tests pass than before ({before.passed} then, {after.passed} now)")
            if after.not_run > before.not_run:
                harm.append(f"more tests are skipped than before ({before.not_run} then, {after.not_run} now), "
                            "which can hide a test that would fail")
            if before.passed == 0 and changed:
                harm.append("changes were applied although the suite had no passing tests to protect them")

    # judging files and paths that leave the project
    judging = list(judging_listed)
    outside: list[str] = []
    for path, kind in changed:
        norm = _norm_path(path)
        if _reaches_outside(norm):
            outside.append(path)
        elif _is_judging(norm, kind.strip().lower()) and path not in judging:
            judging.append(path)
    if judging:
        harm.append(f"tests or test settings were changed ({', '.join(judging[:3])})")
    if outside:
        harm.append(f"an edit reached outside the project or into git or environment folders ({', '.join(outside[:3])})")

    # Ghost, counted one finding at a time
    ghost_start = ghost_end = None
    if g_before is not None and g_after is not None:
        ghost_start, ghost_end = len(g_before), len(g_after)
        new = sorted((Counter(g_after) - Counter(g_before)).elements())
        if new:
            harm.append(f"Ghost reports {len(new)} finding(s) it did not report at the start ({', '.join(new[:3])})")

    # SWIZZLE's proofs
    if proofs is False:
        harm.append("SWIZZLE's own proofs failed, so its reports cannot be trusted")
    elif proofs is None:
        pass
    elif proofs is not True:
        unknown.append(f"SWIZZLE's proofs gave an answer that is not a plain yes or no ({proofs!r})")

    # SWIZZLE's attacks
    held = low_only = 0
    total = 0
    if attacks is not None:
        total = len(attacks)
        if total == 0:
            unknown.append("SWIZZLE attempted no attacks on the governor, so nothing was tested")
        for a in attacks:
            if not isinstance(a, Mapping):
                unknown.append("one of SWIZZLE's attack results was not a readable report")
                continue
            name = a.get("scenario")
            name = "(unnamed)" if name is None else str(name)
            status = _norm_text(a.get("status"))
            severity = _norm_text(a.get("severity"))
            if status == "held":
                held += 1
            elif status == "violated":
                if severity == "low":
                    low_only += 1
                else:
                    shown = severity if severity in _HARM_SEVERITIES else "unknown, treated as high"
                    harm.append(f"SWIZZLE's attack '{name}' found a violated invariant ({shown})")
            else:
                shown = f"status '{status}'" if status else "no status"
                unknown.append(f"SWIZZLE's attack '{name}' did not give a clean answer ({shown})")

    # ASSAY
    caught = modes = floor = None
    if assay is not None:
        key = assay.get("key_proven")
        if key is False:
            harm.append("ASSAY's answer key was not proven, so Ghost's grade means nothing")
        elif key is not True:
            unknown.append("ASSAY's answer key was not confirmed as proven")
        caught, modes = assay.get("caught"), assay.get("failure_modes")
        floor = assay.get("floor", 0)
        if not _is_count(caught):
            unknown.append("ASSAY did not report a usable count of failure modes Ghost caught")
            caught = None
        if not _is_count(modes):
            unknown.append("ASSAY did not report a usable count of known failure modes")
            modes = None
        if not _is_count(floor):
            unknown.append("ASSAY's floor is not a whole number of zero or more, so it cannot be applied")
            floor = None
        if caught is not None and modes is not None and caught > modes:
            harm.append(f"ASSAY's numbers contradict themselves (Ghost caught {caught} but only {modes} failure modes exist)")
        if caught is not None and floor is not None and caught < floor:
            harm.append(f"Ghost caught {caught} of {modes if modes is not None else 'an unknown number of'} "
                        f"known failure modes, below the floor of {floor}")

    # scope
    code = [p for p, _ in changed if not p.strip().lower().endswith(_PROSE)]
    if code and scope.strip().lower() not in {"code", "all"}:
        harm.append(f"code changed under a {scope!r} grant ({', '.join(code[:3])})")
    if changed and after is None and code:
        harm.append("code changed and no final suite result was given")

    if harm:
        return Verdict("REJECT", tuple(harm), NAME)

    # nothing shows harm: now what is missing or unknown
    missing = []
    if after is None:
        missing.append("the final suite run")
    if g_before is None or g_after is None:
        missing.append("Ghost")
    if proofs is None:
        missing.append("SWIZZLE's proofs")
    if attacks is None:
        missing.append("SWIZZLE's attacks on the governor")
    if assay is None:
        missing.append("ASSAY's grading of Ghost")
    reasons = [f"{m} was not measured" for m in missing] + unknown
    odd = [u for u in unmeasured if _norm_text(u) != "judge"]
    if odd:
        reasons.append(f"these checks never ran: {', '.join(odd)}")
    if (before is not None and before.not_run > 0
            and any(p.strip().lower().endswith(".py") and k.strip().lower() in {"write", "delete"} for p, k in changed)):
        reasons.append("some tests did not run, so a code change cannot be shown safe")
    if reasons:
        return Verdict("INSUFFICIENT", tuple(reasons), NAME)

    return Verdict("ACCEPT", (_accept_sentence(
        len(changed), before, after, ghost_start, ghost_end, held, total, low_only, caught, modes, floor),), NAME)


def _norm_text(x: object) -> str:
    return "" if x is None else str(x).strip().lower()


def _accept_sentence(changes, before, after, g0, g1, held, total, low_only, caught, modes, floor) -> str:
    attacks = f"{held} of {total} attacks on the governor held"
    if low_only:
        attacks += f", and {low_only} found a violation of only low severity"
    return (
        f"checked and accepted: {changes} change(s) applied; no tests or test settings were changed and no edit left the project; "
        f"suite {after.passed} passed, {after.skipped} skipped, {after.xfailed} xfailed "
        f"(before: {before.passed if before else 'not given'} passed"
        f"{'' if before is None else f', {before.skipped} skipped, {before.xfailed} xfailed'}); "
        f"Ghost: {g0} finding(s) at the start, {g1} at the end, none new; "
        f"SWIZZLE's own proofs held; {attacks}; "
        f"ASSAY: Ghost caught {caught} of {modes} known failure modes, floor {floor}")
