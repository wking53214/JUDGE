# Judge

The third party that decides. It reads the evidence of a whole run and says ACCEPT, REJECT or INSUFFICIENT. It measures nothing and writes nothing.

## WHAT THIS IS

One of seven repositories in a stack that improves code under human control. Judge has one job: given the evidence a run produced, decide whether the run is acceptable, and say why. [Warden](https://github.com/wking53214/Warden) runs the loop and is the only one that writes files. When the loop is done, Warden hands Judge the evidence and does what the verdict says. Warden cannot say ACCEPT on its own.

Version `0.3.0`. Python 3.11 or newer. It depends on Warden for the shapes of the evidence and the verdict, and on nothing else. It is pinned to Warden tag `v0.11.0`; see "Testing against the pin" below.

## WHAT IT DOES NOT OWN

- Finding problems (Ghost Tools).
- Attacking the governor and the detectors (SWIZZLE). Judge reads SWIZZLE's report; it does not ask SWIZZLE for anything.
- Proposing fixes (Drafter), writing files, granting permission, running tests (Warden).
- The answer key (ASSAY).
- Beautifying the code and writing the final README (Burnish).

## ARCHITECTURAL STORY

```text
Warden loop ends  ->  Evidence (suite, Ghost, SWIZZLE, what changed)  ->  Judge.decide  ->  Verdict
                                                                                              |
                                          ACCEPT: stands.  REJECT: Warden puts the whole tree back.
                                          INSUFFICIENT: Warden puts the tree back and holds the result (ACCEPT_UNVERIFIED) until a person approves that exact result.
```

The rules are written at the top of `judge/seat.py`, so a person can read why a run was turned away. The governing rule is **unknown is not approved**: only values the Judge recognizes count as good. Text is trimmed and lowercased before it is compared. Harm is found first and outranks missing evidence. The checks for unreadable evidence come before everything else.

| verdict | when |
|---|---|
| INSUFFICIENT (evidence unreadable) | a count is not a whole number of zero or more (a true/false value, a float, NaN, a negative all fail), a field has the wrong type or is missing, or any other error occurs while reading. The Judge never raises an error. |
| REJECT | the suite is red or fewer tests pass than before; more tests are skipped or expected-to-fail than before; tests or test settings were changed (Warden's list, or any path shaped like a test, a test setting, `conftest.py`, `setup.py`, `pyproject.toml`, `Makefile`, a CI file, a hook folder, a fixture folder (`fixtures`, `specimens`, `testdata`, `golden`, `snapshots`, `corpus`: what the tests compare against), a lockfile, a requirements or constraints file, a Dockerfile, any `.ghost_*` file, compared without regard to case, and following symlinks, whether or not Warden listed it); Ghost's baseline suppresses more findings at the end than at the start, or its file moved; the final suite exited non-zero or is marked forged; an edit reached outside the project (`..`, an absolute path) or into `.git` or `.venv`; Ghost reports a finding at the end that it did not report at the start (counted one by one, so a repeat counts as new); SWIZZLE's proofs are exactly `False`; a SWIZZLE attack is `violated` at any severity except `low` (an unknown or missing severity counts as high); ASSAY's key is exactly `False`, Ghost caught fewer failure modes than the floor, or caught is more than the total; code changed under a documentation grant |
| INSUFFICIENT | nothing shows harm, but something is unknown: the final suite run, Ghost, SWIZZLE's proofs, SWIZZLE's attacks or ASSAY's grade is missing; the proofs or the key are anything other than exactly `True`; no attacks were attempted; an attack is not a proper entry or did not give a clean answer (status `error`, `timeout`, `crashed`, `unknown`, `not_run`, empty or missing); ASSAY's floor, caught or failure_modes is missing or not a whole number (a missing floor is never read as 0; a floor of 0 given on purpose is allowed and shown in the reason); ASSAY lists no failure modes; Ghost's baseline report (`ghost_baseline_before` and `ghost_baseline_after`, each `{path, suppressed}`) is missing or unreadable; some tests did not run before the run and a `.py` file was written or deleted; Warden lists a check that never ran other than `judge` |
| ACCEPT | everything above is clear. The reason lists what was checked with the real numbers: passed, skipped and xfailed counts, attacks held out of attacks run, Ghost findings at start and end, and ASSAY caught out of total with the floor. When the suite counts rest on printed text alone (no exit code), the reason says so. |

| module | owns |
|---|---|
| `judge.seat` | the `Judge` class Warden calls, and its rules |

## KEY INTERNAL CONCEPTS

- **Unknown is not approved.** A measurement that did not run, or came back in a shape the Judge does not recognize, can never produce ACCEPT.
- **Harm outranks missing evidence.** If the suite is red, the verdict is REJECT even when other checks are missing.
- **Read-only.** Judge imports `warden.roles` and nothing else from the stack. It does not use `ast`, `subprocess` or `os`, and it calls nothing that writes a file. A test reads its source to prove it.
- **Reasons are always given.** Every verdict carries at least one sentence.

## IMPORTANT BOUNDARIES

Judge is a different seat from SWIZZLE on purpose. SWIZZLE reports whether an invariant held. Judge decides what that means for this run. Neither can do the other's job.

## Install

```bash
pip install "git+https://github.com/wking53214/Warden.git@2cf0eeccf839f88d624deb133fe1cb4b16a99009"
pip install git+https://github.com/wking53214/Judge.git
```

### Bumping the Warden pin

This package depends on one exact Warden commit (see `dependencies` in `pyproject.toml`), so a change on
Warden's `main` cannot break it without anyone noticing. To move to a newer Warden:

1. Pick the Warden commit (or `vX.Y.Z` tag) you want.
2. Put it after the `@` in the `warden @ git+...` line of `pyproject.toml`.
3. Run `pip install -e ".[dev]"` and `pytest`. The tests check that the pin is a tag or a full commit and that
   this package's `requires_contract` matches the installed Warden's `CONTRACT`.
4. Open a pull request. CI runs the same checks.

## Usage

No command line of its own. Warden loads it:

```bash
warden tagteam PATH --drafter drafter.seat:Drafter --finisher burnish.finisher:Burnish \
  --judge judge.seat:Judge --authorize ACTOR --scope code --reason TEXT \
  --ghost-root GHOST_TOOLS --swizzle-root SWIZZLE
```

Without `--judge`, Warden can only end a run as `ACCEPT_UNVERIFIED`.

### As a CNS gate

The Judge already reads and returns CNS's shared rows (`cns.seat`). `judge.cns_connector` adds the other
direction: anything that speaks CNS's gate contract (`cns.gate`) can use the Judge's verdict. The `judge` package
does not import it; import the module to use it.

```python
from judge.cns_connector import JudgeGate
result = JudgeGate().check(evidence)   # a cns.gate.GateResult at the OMEGA end
```

ACCEPT is `PASS`, REJECT is `TERMINAL_BREACH`, INSUFFICIENT is `RETRY` (bring the missing evidence and ask
again), and any other answer is `TERMINAL_BREACH`. The result is bound to a digest of the evidence it judged,
including attributes the Judge reads that are not declared fields, so it cannot be moved onto other evidence.
Evidence that cannot be described unambiguously is a `TERMINAL_BREACH`. The Judge has only the outcome end, so
`cns_chain().complete()` is `False` until a consumer adds an `alpha` gate from another repository. Nothing about
how the Judge decides changes, and Warden does not use this module.

## LIFECYCLE / EXECUTION MODEL

Warden calls `Judge.decide` once, after the last cycle and after the finisher. On REJECT, Warden restores every file to its state before the run.

## WHAT WORKS

- Each rule above, one at a time, on hand-made evidence. **VERIFIED** by `tests/test_judge.py`.
- Seated in the real Warden loop: a clean run is accepted, a run with a violated SWIZZLE attack is turned away and the tree is put back, a run whose attacks never ran is unjudged, so Warden puts it back and holds it until a person approves it. **VERIFIED** by `tests/test_in_the_loop.py`.
- Seated in the whole circuit with live Ghost, SWIZZLE (12 of 12 proofs, 26 of 26 governor attacks held), ASSAY (3 of 5 failure modes caught, floor 3), Drafter and Burnish, through `warden tagteam --stack`: the verdict was ACCEPT with every number in its reason, and the run exited 0. **VERIFIED** by hand on 2026-10-14 on a scratch repository; recorded in Warden's `docs/REGISTRY.json`.
- It imports only `warden.roles`, never measures, never writes. **VERIFIED** by `tests/test_independence.py`.

316 tests are collected in this tree: 155 in `tests/test_strict_evidence.py` (the red-team cases), 100 in `tests/test_red_team_round2.py`, 28 in `tests/test_judge.py`, 21 in `tests/test_cns_connector.py`, 4 in `tests/test_in_the_loop.py`, 3 in `tests/test_independence.py`, 3 in `tests/test_contract.py`, 1 in `tests/test_warden_pin.py` and 1 in `tests/test_cns_pin.py`. None are skipped or marked expected-to-fail.

### Testing against the pin

Judge's tests import Warden from whatever is on the import path.

- Against Warden `v0.11.0` (the pin, which CI installs): all 288 pass on CPython 3.13. Checked 2026-10-14. The same is true of `v0.10.1`.
- Against Warden `v0.9.0` (the old pin): 287 pass and one fails, `tests/test_in_the_loop.py::test_attacks_that_never_ran_leave_the_run_unjudged`. That test expects a held result (`held_digest`), which `v0.9.0` does not have.

## WHAT IS BEAUTIFUL

The rules fit on one screen and every one of them can be argued with.

## WHAT IS IMPLEMENTED

The rules in the table above.

## WHAT IS PROVEN

The tests named above, against hand-built evidence and against the real Warden with stubbed Ghost and SWIZZLE.

## WHAT IS NOT PROVEN

- That the rules are the right ones. They are a first draft written to match the failures found so far.
- A recorded run against a real repository. The recorded circuit run used a scratch repository.

## WHAT DOES NOT WORK

- It cannot weigh severity beyond "low attack violation is tolerated, anything else is harm". A single low-severity Ghost finding that is new is as bad as a critical one.
- Test files are recognized by name and folder. A real source file in a folder called `test` or `tests` would be treated as a test file and turned away.
- It trusts the evidence Warden assembles. It cannot tell whether Warden left something out.

## WHAT IS STILL UGLY

- The test-count rule compares passes before and after, so a run that removes a deliberately obsolete test is rejected. Any change to a test file is rejected, even a harmless one, because there is no format-only exception yet.

## KNOWN DEFECTS

None known beyond the above.

## WHAT REMAINS OUTSTANDING

A recorded run on a real repository. A way for a person to override a verdict with a written reason.

## CLAIMS VS REALITY

The README says Judge never writes and never measures. The tests read its source and fail if it imports `ast`, `subprocess` or `os`, or calls anything that writes a file. The README does not say the rules are complete, because they are not.

## Status

Experimental, version 0.3.0, maintained by one person.

## Support

Open an issue at https://github.com/wking53214/Judge/issues.

## Contributing

Welcome, narrowly. A new rule must come with a test that shows it firing and a test that shows it not firing, and must keep the order: harm first, then missing evidence, then ACCEPT.

## License

Apache-2.0. See `LICENSE`.
