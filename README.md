# Judge

The third party that decides. It reads the evidence of a whole run and says ACCEPT, REJECT or INSUFFICIENT. It measures nothing and writes nothing.

## WHAT THIS IS

One of seven repositories in a stack that improves code under human control. Judge has one job: given the evidence a run produced, decide whether the run is acceptable, and say why. [Warden](https://github.com/wking53214/Warden) runs the loop and is the only one that writes files. When the loop is done, Warden hands Judge the evidence and does what the verdict says. Warden cannot say ACCEPT on its own.

Version `0.4.8` (see `CHANGELOG.md`). Python 3.11 or newer. Its one runtime dependency is [CNS](https://github.com/wking53214/CNS), which defines the shared rows the Judge reads and returns (`cns.seat`) and the gate contract of the optional connector (`cns.gate`); the exact release tag is pinned in `pyproject.toml`. The Judge imports no Warden code. Warden is used only by the tests that seat the Judge in the real loop, as the test-time extra `warden`, pinned to a full commit in `pyproject.toml`; see "Testing against the pin" below.

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
| INSUFFICIENT (evidence unreadable) | a count is not a whole number of zero or more (a true/false value, a float, NaN, a negative all fail), a field has the wrong type or is missing (`target` must be text), an exit code is not a whole number, two exit-code names of one suite (`exit_code`, `returncode`, `exitcode`, `exit_status`) give different numbers (every name present is read; the first one found does not win), or any other error occurs while reading (`cycles` and `declined` are read too, so a wrong type there is unreadable). The Judge never raises an error. |
| REJECT | the suite is red or fewer tests pass than before; more tests are skipped or expected-to-fail than before; tests or test settings were changed (Warden's list, or any path shaped like a test (including `test*.txt`, which pytest collects as doctests by default), a test setting, `conftest.py`, `setup.py`, `pyproject.toml`, `Makefile`, a CI file, a hook folder, a fixture folder (`fixtures`, `specimens`, `testdata`, `golden`, `snapshots`, `corpus`: what the tests compare against), a lockfile, a requirements or constraints file, a Dockerfile, any `.ghost_*` file, compared without regard to case, and following symlinks, whether or not Warden listed it); Ghost's baseline suppresses more findings at the end than at the start, or its file moved; the final suite exited non-zero or is marked forged; an edit reached outside the project (`..`, an absolute path) or into `.git` or an environment folder (`.venv`, `venv`, `env`, `.tox`, `.nox`, `.eggs`, `node_modules`, `site-packages`); Ghost reports a finding at the end that it did not report at the start (counted one by one, so a repeat counts as new); SWIZZLE's proofs are exactly `False`; a SWIZZLE attack is `violated` at any severity except `low` (an unknown or missing severity counts as high); ASSAY's key is exactly `False`, Ghost caught fewer failure modes than the floor, or caught is more than the total; code changed under a documentation grant |
| INSUFFICIENT | nothing shows harm, but something is unknown: the final suite run, Ghost, SWIZZLE's proofs, SWIZZLE's attacks or ASSAY's grade is missing; the starting suite run (`suite_before`) is missing, did not run, or was not green (`failed` or `errors` above zero, or a non-zero exit code), because the before and after comparison needs a known good start; the grant's `scope` is not `documentation`, `code` or `all`, or an edit's `kind` is not `write`, `replace` or `delete`; the proofs or the key are anything other than exactly `True`; no attacks were attempted; an attack is not a proper entry or did not give a clean answer (status `error`, `timeout`, `crashed`, `unknown`, `not_run`, empty or missing); ASSAY's floor, caught or failure_modes is missing or not a whole number (a missing floor is never read as 0; a floor of 0 given on purpose is allowed and shown in the reason); ASSAY lists no failure modes; Ghost's baseline report (`ghost_baseline_before` and `ghost_baseline_after`, each `{path, suppressed}`) is missing or unreadable; some tests did not run before the run and a `.py` file was written or deleted; Warden lists a check that never ran other than `judge`; the evidence contradicts itself about what was applied (a cycle outcome the Judge does not know, two cycles with one number, more `APPLIED` cycles than listed edits, listed edits that no `APPLIED` cycle explains unless a converged loop, ending on `NOTHING_TO_PROPOSE`, could have had a finishing change, `declined` entries with no `DECLINED` cycle, or a last cycle that is `REFUSED`, `PUT_BACK` or `SUITE_RED`, which means the loop never converged; see "What the cycle checks cannot do" below) |
| ACCEPT | everything above is clear. The reason lists what was checked with the real numbers: passed, skipped and xfailed counts, attacks held out of attacks run, Ghost findings at start and end, and ASSAY caught out of total with the floor. When the suite counts rest on printed text alone (no exit code), the reason says so. |

| module | owns |
|---|---|
| `judge.seat` | the `Judge` class Warden calls, and its rules |
| `judge.cli` | the `judge` command line: `judge decide` and `judge --version` |
| `judge.cns_connector` | the Judge as a CNS gate (optional; nothing else imports it) |

## KEY INTERNAL CONCEPTS

- **Unknown is not approved.** A measurement that did not run, or came back in a shape the Judge does not recognize, can never produce ACCEPT.
- **Harm outranks missing evidence.** If the suite is red, the verdict is REJECT even when other checks are missing.
- **Read-only.** Judge imports only the standard library, CNS's shared rows (`cns.seat`, `cns.suite`) and, in the connector, CNS's gate contract (`cns.gate`). It imports no Warden code and no other role of the stack. It does not use `ast`, `subprocess` or `os`, and it calls nothing that writes a file. A test holds every module to an allowlist of the imports it may make, so a new import fails until a person adds it on purpose.
- **Reasons are always given.** Every verdict carries at least one sentence.

## IMPORTANT BOUNDARIES

Judge is a different seat from SWIZZLE on purpose. SWIZZLE reports whether an invariant held. Judge decides what that means for this run. Neither can do the other's job.

## Install

```bash
pip install git+https://github.com/wking53214/Judge.git
```

That installs the Judge and its one runtime dependency, CNS. To run the whole test suite (including the tests that seat the Judge in the real Warden loop):

```bash
pip install -e ".[dev]"      # pytest, ruff, mypy and the pinned Warden
pytest
```

Without Warden (`pip install -e ".[test]"`) the tests that need it are skipped with a stated reason (`pytest -rs`). CI runs both ways, and its Warden job sets `JUDGE_REQUIRE_WARDEN=1` so a missing Warden is a failure, not a skip.

### Bumping the Warden pin

The tests depend on one exact Warden commit (extra `warden` in `pyproject.toml`), so a change on Warden's `main`
cannot break them without anyone noticing. To move to a newer Warden:

1. Pick the Warden commit you want and copy its full 40-character SHA.
2. Put it after the `@` in the `warden @ git+...` line of `pyproject.toml`, and update the Warden version in the comment on that line.
3. Put the same SHA in the `ref:` of the Warden checkout in `.github/workflows/tests.yml`.
4. Run `pip install -e ".[dev]"` and `pytest`. `tests/test_warden_pin.py` checks that the pin is a full commit, that CI checks out the same commit, and that the comment names the Warden version that is installed; `tests/test_contract.py` checks that `requires_contract` matches the installed Warden's `CONTRACT`.
5. Open a pull request. CI runs the same checks.

CNS is pinned by release tag (`@v1.9.0`, with the commit it peels to in a comment) in the `dependencies` line of `pyproject.toml`; every repository of the stack spells that pin the same way.

## Usage

### With Warden

Warden loads the Judge as a seat:

```bash
warden tagteam PATH --drafter drafter.seat:Drafter --finisher burnish.finisher:Burnish \
  --judge judge.seat:Judge --authorize ACTOR --scope code --reason TEXT \
  --ghost-root GHOST_TOOLS --swizzle-root SWIZZLE
```

Without `--judge`, Warden can only end a run as `ACCEPT_UNVERIFIED`.

### From the command line

```bash
judge --version
judge decide EVIDENCE.json        # or "-" to read standard input
python -m judge decide EVIDENCE.json
```

`judge decide` reads a JSON object with the fields of `cns.seat.Evidence`, the same input `Judge.decide` takes, and prints
the decision as JSON: `{"decision": "ACCEPT" | "REJECT" | "INSUFFICIENT", "reasons": [...], "judge": "judge X.Y.Z"}`.
`examples/accept.json` is a complete input that is accepted. Lists are JSON arrays; `null` means "not measured", which is never "fine".
The fields are `target`, `scope`, `cycles`, `changed`, `judging_files_touched`, `suite_before`, `suite_after`, `ghost_before`,
`ghost_after`, `declined`, `swizzle_proofs`, `attacks`, `unmeasured` (all required) and `notes`, `assay`,
`ghost_baseline_before`, `ghost_baseline_after` (optional in the schema, but a missing `assay` or baseline is unknown and so never ACCEPT). `suite_before` is required to be a suite that ran and was green (see below); `null` is not accepted. A suite is an object with
the fields of `cns.suite.SuiteRun` (`ran`, `passed`, `failed`, `errors`, `skipped`, `xfailed`, `xpassed`, `reason`, `exit_code`) and,
if present, the flags the Judge reads (`forged`, `text_only`).

What an ACCEPT requires of the evidence (anything less is INSUFFICIENT, or REJECT where it shows harm):

- `target` is text; `scope` is `documentation`, `code` or `all`; every edit `kind` is `write`, `replace` or `delete`.
- `suite_before` and `suite_after` are both present and `ran`; `suite_before` has `failed` 0, `errors` 0 and exit code 0 (a missing
  or red start leaves nothing to compare the end with). `suite_after` is green (`passed` above 0, `failed` 0, `errors` 0, exit code 0,
  not forged). Every exit-code name present in a suite must agree.
- A suite whose counts rest on printed text alone (no exit code) is never enough.
- The last cycle is not `REFUSED`, `PUT_BACK` or `SUITE_RED`.
- Ghost's findings before and after, the baseline report, SWIZZLE's proofs and attacks and ASSAY's grade are all given and clean.

| exit code | meaning |
|---|---|
| 0 | ACCEPT, and the decision was delivered on standard output or the reader of standard output had left (a broken pipe). The only approval. |
| 1 | Anything else: REJECT, INSUFFICIENT, or an input that is not the evidence schema (reported as INSUFFICIENT). Also an ACCEPT whose decision could not be delivered for any reason other than the reader leaving (standard output closed, or a failed write such as a full device): a verdict that was not delivered is not an approval. |
| 2 | Usage error: bad arguments, a file or standard input that cannot be read (including a closed standard input), or text that is not JSON. Nothing is printed on standard output. |

Delivery of the decision, exactly:

- The reader left (`judge decide FILE | head`, a broken pipe): nothing is printed on standard error and the exit code is the one
  earned, 0 for an ACCEPT and 1 for any other decision.
- Standard output closed (`judge decide FILE >&-`) or a write to it fails (for example a full device): one plain line on
  standard error, no traceback, and exit 1 for every decision. The line names the decision, so an ACCEPT that was not delivered is
  visible as such.
- Standard input closed (`judge decide - <&-`): one plain line on standard error and exit 2.
- If standard error is also unusable, that one line is lost and the exit code is unchanged.
- `main` never replaces `sys.stdout`, so a program that calls `judge.cli.main()` in-process keeps its own stream. The one
  exception is the process's real standard output after a failed write: it is closed, so the interpreter does not try to flush the
  same bytes again at exit (which ends in exit status 120 and a message from Python).

The command fails closed: any exception while building or judging the evidence yields INSUFFICIENT and exit 1, never 0.
Logs go to standard error: `-v` shows each decision, `-vv` adds each reason. As a library, Judge logs to the `judge` logger
(decision at INFO, reasons at DEBUG, unreadable evidence at WARNING) and installs no handler.

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
- Evidence captured from the real Warden loop (nine runs, `tests/fixtures/real/`, plus `examples/accept.json`) is accepted, and altering any field the Judge reads in the ways a fuzzing audit used is not. **VERIFIED** by `tests/test_real_evidence.py`; the real-loop tests (`tests/test_in_the_loop.py`) show that a loop which stopped on a refused, put-back or red cycle, or never converged, is not handed to the Judge at all.
- Seated in the real Warden loop: a clean run is accepted, a run with a violated SWIZZLE attack is turned away and the tree is put back, a run whose attacks never ran is unjudged, so Warden puts it back and holds it until a person approves it. **VERIFIED** by `tests/test_in_the_loop.py`.
- Seated in the whole circuit with live Ghost, SWIZZLE (12 of 12 proofs, 26 of 26 governor attacks held), ASSAY (3 of 5 failure modes caught, floor 3), Drafter and Burnish, through `warden tagteam --stack`: the verdict was ACCEPT with every number in its reason, and the run exited 0. **VERIFIED** by hand on 2026-10-14 on a scratch repository; recorded in Warden's `docs/REGISTRY.json`.
- It imports only the standard library and CNS, never measures, never writes. **VERIFIED** by `tests/test_independence.py`, which fails on any import that is not on a per-module allowlist.
- The `judge` command: exit codes, fail-closed behaviour and the version. **VERIFIED** by `tests/test_cli.py` and `tests/test_version.py`.

The suite has no skipped, expected-to-fail or deselected tests when Warden is installed. The red-team cases are in `tests/test_strict_evidence.py` and `tests/test_red_team_round2.py`; count them with `pytest --collect-only -q`. This README states no test count on purpose, because a number written here drifts.

### Testing against the pin

The Judge itself does not import Warden. Two test files do, because they seat the Judge in the real loop and check the contract
(`tests/test_in_the_loop.py`, `tests/test_contract.py`). They run against the Warden commit pinned in the `warden` extra of
`pyproject.toml`, which is the commit CI checks out; the pin names its Warden version in a comment. Reference the pin there rather
than a version written here: this README does not repeat it, so it cannot go stale.

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

## WHAT THE CYCLE CHECKS CANNOT DO

The clause "a listed edit that no `APPLIED` cycle explains" cannot fire on a converged run when a finisher may have run. A
converged run ends on `NOTHING_TO_PROPOSE` whether or not a finisher then edited files, and the evidence does not say which, so
every listed edit can be blamed on the finisher. The clause catches hand-made evidence (for example a record that ends on a
`REFUSED` cycle with edits listed), not a fabricated edit list on a converged run, so it is not a protection for real evidence.
Closing it needs a `finisher ran` field in the CNS `Evidence` shape. That is a change to CNS, and it is the owner's call.

## KNOWN DEFECTS

None known beyond the above.

## WHAT REMAINS OUTSTANDING

A recorded run on a real repository. A way for a person to override a verdict with a written reason.

## CLAIMS VS REALITY

The README says Judge never writes and never measures. The tests read its source and fail if any module imports anything not on its allowlist (which excludes `ast`, `subprocess`, `os` and all Warden code), or calls anything that writes a file. The README does not say the rules are complete, because they are not.

## Status

Experimental, maintained by one person. The version is the one at the top of this file and in `CHANGELOG.md`; an older tag `v0.10.0` exists that does not correspond to this version (it points at the 0.3.0 code), releases of this version are not tagged yet, and tagging is the owner's decision.

## Support

Open an issue at https://github.com/wking53214/Judge/issues.

## Contributing

Welcome, narrowly. A new rule must come with a test that shows it firing and a test that shows it not firing, and must keep the order: harm first, then missing evidence, then ACCEPT.

## License

Apache-2.0. See `LICENSE`.
