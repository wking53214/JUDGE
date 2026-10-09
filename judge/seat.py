"""The Judge's seat in Warden's loop: evidence in, verdict out.

The Judge decides and does nothing else. It does not run the tests, ask Ghost,
attack the governor or touch a file; others measured, and Warden handed it what
they measured. Its rules are deliberately few and written down here, so a person
can read why a run was accepted or turned away.

THE RULES, in order. The first that fires decides.

  REJECT        the evidence shows harm:
    the suite is red, or fewer tests pass than before
    Ghost reports a finding at the end that it did not report at the start
    SWIZZLE's proofs failed
    SWIZZLE's attacks on the governor found an invariant violated (high or medium)
    ASSAY's answer key was unproven, or Ghost caught fewer known failure modes
    than the floor the person set
    code changed under a documentation grant
    the evidence contradicts itself (impossible counts, a code edit with no suite)
  INSUFFICIENT  nothing shows harm, but too little was measured to approve:
    the final suite run, Ghost, SWIZZLE's proofs, SWIZZLE's attacks on the
    governor or ASSAY's grading of Ghost is missing. All five are required,
    for prose changes too.
  ACCEPT        everything required ran, and none of it shows harm.

Unknown is not approved: a missing measurement can never produce ACCEPT.
A run that changed nothing is ACCEPTed only if the evidence is complete.
"""

from __future__ import annotations

from warden.roles import Evidence, Verdict

NAME = "judge 0.1"

_PROSE = (".md", ".rst", ".txt")


class Judge:
    def decide(self, evidence: Evidence) -> Verdict:
        harm = _harm(evidence)
        if harm:
            return Verdict("REJECT", tuple(harm), NAME)
        missing = _missing(evidence)
        if missing:
            return Verdict("INSUFFICIENT", tuple(f"{m} was not measured" for m in missing), NAME)
        changed = len(evidence.changed)
        return Verdict("ACCEPT", (
            f"{changed} change(s) applied; suite green with no fewer passes; Ghost reports nothing new; "
            "SWIZZLE's proofs hold and none of its attacks on the governor found a violation; "
            f"Ghost caught {evidence.assay.get('caught')} of {evidence.assay.get('failure_modes')} "
            "failure modes in ASSAY's answer key",), NAME)


def _harm(e: Evidence) -> list[str]:
    out: list[str] = []
    before, after = e.suite_before, e.suite_after
    if after is not None:
        if not after.green:
            out.append(f"the suite is not green at the end ({after.describe()})")
        if before is not None and after.passed < before.passed:
            out.append(f"fewer tests pass than before ({before.passed} then, {after.passed} now)")
        if before is not None and before.passed == 0 and e.changed:
            out.append("changes were applied although the suite had no passing tests to protect them")
    if e.ghost_before is not None and e.ghost_after is not None:
        new = sorted(set(e.ghost_after) - set(e.ghost_before))
        if new:
            out.append(f"Ghost reports {len(new)} finding(s) it did not report at the start ({', '.join(new[:3])})")
    if e.swizzle_proofs is False:
        out.append("SWIZZLE's own proofs failed, so its reports cannot be trusted")
    for a in e.attacks or ():
        if a.get("status") == "violated" and a.get("severity") in {"high", "medium"}:
            out.append(f"SWIZZLE's attack '{a.get('scenario')}' found a violated invariant ({a.get('severity')})")
    if e.assay is not None:
        if e.assay.get("key_proven") is not True:
            out.append("ASSAY's answer key was not proven, so Ghost's grade means nothing")
        else:
            caught, floor = int(e.assay.get("caught", 0)), int(e.assay.get("floor", 0))
            if caught < floor:
                out.append(f"Ghost caught {caught} of {e.assay.get('failure_modes')} known failure modes, "
                           f"below the floor of {floor}")
    code = [p for p, _ in e.changed if not p.lower().endswith(_PROSE)]
    if code and e.scope.strip().lower() not in {"code", "all"}:
        out.append(f"code changed under a {e.scope!r} grant ({', '.join(code[:3])})")
    if e.changed and e.suite_after is None and code:
        out.append("code changed and no final suite result was given")
    return out


def _missing(e: Evidence) -> list[str]:
    out = []
    if e.suite_after is None:
        out.append("the final suite run")
    if e.ghost_before is None or e.ghost_after is None:
        out.append("Ghost")
    if e.swizzle_proofs is None:
        out.append("SWIZZLE's proofs")
    if e.attacks is None:
        out.append("SWIZZLE's attacks on the governor")
    if e.assay is None:
        out.append("ASSAY's grading of Ghost")
    return out
