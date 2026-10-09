# Judge

The third party that decides. It reads the evidence of a whole run and says ACCEPT, REJECT or INSUFFICIENT. It measures nothing and writes nothing.

## WHAT THIS IS

One of seven repositories in a stack that improves code under human control. Judge has one job: given the evidence a run produced, decide whether the run is acceptable, and say why. [Warden](https://github.com/wking53214/Warden) runs the loop and is the only one that writes files. When the loop is done, Warden hands Judge the evidence and does what the verdict says. Warden cannot say ACCEPT on its own.

Version `0.1.0`. Python 3.11 or newer. It depends on Warden for the shapes of the evidence and the verdict, and on nothing else.

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
                                          INSUFFICIENT: changes stand, flagged as unjudged.
```

The rules are few and are written at the top of `judge/seat.py`, so a person can read why a run was turned away. The first rule that fires decides:

| verdict | when |
|---|---|
| REJECT | the suite is red or fewer tests pass than before; Ghost reports a finding at the end it did not report at the start; SWIZZLE's proofs failed; SWIZZLE's attacks on the governor found a high or medium invariant violated; code changed under a documentation grant |
| INSUFFICIENT | nothing shows harm, but the final suite run, Ghost, SWIZZLE's proofs or SWIZZLE's attacks is missing |
| ACCEPT | all four ran and none shows harm |

| module | owns |
|---|---|
| `judge.seat` | the `Judge` class Warden calls, and its rules |

## KEY INTERNAL CONCEPTS

- **Unknown is not approved.** A measurement that did not run can never produce ACCEPT.
- **Harm outranks missing evidence.** If the suite is red, the verdict is REJECT even when other checks are missing.
- **Read-only.** Judge imports `warden.roles` and nothing else from the stack. It does not use `ast`, `subprocess` or `os`, and it calls nothing that writes a file. A test reads its source to prove it.
- **Reasons are always given.** Every verdict carries at least one sentence.

## IMPORTANT BOUNDARIES

Judge is a different seat from SWIZZLE on purpose. SWIZZLE reports whether an invariant held. Judge decides what that means for this run. Neither can do the other's job.

## Install

```bash
pip install git+https://github.com/wking53214/Warden.git
pip install git+https://github.com/wking53214/Judge.git
```

## Usage

No command line of its own. Warden loads it:

```bash
warden tagteam PATH --drafter drafter.seat:Drafter --finisher burnish.finisher:Burnish \
  --judge judge.seat:Judge --authorize ACTOR --scope code --reason TEXT \
  --ghost-root GHOST_TOOLS --swizzle-root SWIZZLE
```

Without `--judge`, Warden can only end a run as `ACCEPT_UNVERIFIED`.

## LIFECYCLE / EXECUTION MODEL

Warden calls `Judge.decide` once, after the last cycle and after the finisher. On REJECT, Warden restores every file to its state before the run.

## WHAT WORKS

- Each rule above, one at a time, on hand-made evidence. **VERIFIED** by `tests/test_judge.py`.
- Seated in the real Warden loop: a clean run is accepted, a run with a violated SWIZZLE attack is turned away and the tree is put back, a run whose attacks never ran stays unjudged. **VERIFIED** by `tests/test_in_the_loop.py`.
- It imports only `warden.roles`, never measures, never writes. **VERIFIED** by `tests/test_independence.py`.

25 tests exist in this tree, and all 25 passed on CPython 3.13 on 2026-10-08.

## WHAT IS BEAUTIFUL

The rules fit on one screen and every one of them can be argued with.

## WHAT IS IMPLEMENTED

The rules in the table above.

## WHAT IS PROVEN

The tests named above, against hand-built evidence and against the real Warden with stubbed Ghost and SWIZZLE.

## WHAT IS NOT PROVEN

- That the rules are the right ones. They are a first draft written to match the failures found so far.
- A recorded run against a real repository with live Ghost and SWIZZLE.

## WHAT DOES NOT WORK

- It cannot weigh severity beyond "high or medium attack violated". A single low-severity Ghost finding that is new is as bad as a critical one.
- It trusts the evidence Warden assembles. It cannot tell whether Warden left something out.

## WHAT IS STILL UGLY

- The test-count rule compares passes before and after, so a run that removes a deliberately obsolete test is rejected.

## KNOWN DEFECTS

None known beyond the above.

## WHAT REMAINS OUTSTANDING

A recorded live run. A way for a person to override a verdict with a written reason.

## CLAIMS VS REALITY

The README says Judge never writes and never measures. The tests read its source and fail if it imports `ast`, `subprocess` or `os`, or calls anything that writes a file. The README does not say the rules are complete, because they are not.

## Status

Experimental, version 0.1.0, maintained by one person.

## Support

Open an issue at https://github.com/wking53214/Judge/issues.

## Contributing

Welcome, narrowly. A new rule must come with a test that shows it firing and a test that shows it not firing, and must keep the order: harm first, then missing evidence, then ACCEPT.

## License

Apache-2.0. See `LICENSE`.
