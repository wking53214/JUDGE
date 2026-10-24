# Judge

The third party that decides. It reads the evidence of a whole run and says ACCEPT, REJECT or INSUFFICIENT. It measures nothing and writes nothing.

## WHAT THIS IS

One of seven repositories in a stack that improves code under human control. Judge has one job: given the evidence a run produced, decide whether the run is acceptable, and say why. [Warden](https://github.com/wking53214/Warden) runs the loop and is the only one that writes files. When the loop is done, Warden hands Judge the evidence and does what the verdict says. Warden cannot say ACCEPT on its own.

Version `0.4.10` (see `CHANGELOG.md`). Python 3.11 or newer. Its one runtime dependency is [CNS](https://github.com/wking53214/CNS), which defines the shared rows the Judge reads and returns (`cns.seat`) and the gate contract of the optional connector (`cns.gate`); the exact release tag is pinned in `pyproject.toml`. The Judge imports no Warden code. Warden is used only by the tests that seat the Judge in the real loop, as the test-time extra `warden`, pinned to a full commit in `pyproject.toml`; see "Testing against the pin" below.

This is an experimental project kept by one person. The rules below are a first draft written to match the failures found so far. Read WHAT DOES NOT WORK / NOT PROVEN and KNOWN DEFECTS before you rely on a verdict.

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
| INSUFFICIENT | nothing shows harm, but something is unknown: the final suite run, Ghost, SWIZZLE's proofs, SWIZZLE's attacks or ASSAY's grade is missing; the starting suite run (`suite_before`) is missing, did not run, or was not green (`failed` or `errors` above zero, or a non-zero exit code), because the before and after comparison needs a known good start; the grant's `scope` is not `documentation`, `code` or `all`, or an edit's `kind` is not `write`, `replace` or `delete`; the proofs or the key are anything other than exactly `True`; no attacks were attempted; an attack is not a proper entry or did not give a clean answer (status `error`, `timeout`, `crashed`, `unknown`, `not_run`, empty or missing); ASSAY's floor, caught or failure_modes is missing or not a whole number (a missing floor is never read as 0; a floor of 0 given on purpose is allowed and shown in the reason); ASSAY lists no failure modes; Ghost's baseline report (`ghost_baseline_before` and `ghost_baseline_after`, each `{path, suppressed}`) is missing or unreadable; some tests did not run before the run and a `.py` file was written, replaced or deleted (every edit kind the Judge knows); Warden lists a check that never ran other than `judge`; the evidence contradicts itself about what was applied (a cycle outcome the Judge does not know, two cycles with one number, more `APPLIED` cycles than listed edits, listed edits that no `APPLIED` cycle explains unless a converged loop, ending on `NOTHING_TO_PROPOSE`, could have had a finishing change, `declined` entries with no `DECLINED` cycle, or a last cycle that is `REFUSED`, `PUT_BACK` or `SUITE_RED`, which means the loop never converged; see KNOWN DEFECTS for what these cycle checks cannot do) |
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

Judge is a different seat from SWIZZLE on purpose. SWIZZLE reports whether an invariant held. Judge decides what that means for this run. Neither can do the other's job.

## HOW TO INSTALL AND RUN

Do not run `pip install judge`. That name on PyPI belongs to a different project (checked on 2026-10-22: a library for choosing values by conditions, not this one). Install from a checkout or from the git URL.

From a checkout, with everything the tests need (pytest, ruff, mypy and the pinned Warden):

```bash
git clone https://github.com/wking53214/JUDGE.git
cd JUDGE
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest
judge --version
judge decide examples/accept.json
```

Only the Judge and its one runtime dependency, CNS, from the git URL (this installs the default branch):

```bash
pip install git+https://github.com/wking53214/JUDGE.git
```

Without Warden (`pip install -e ".[test]"`) the tests that need it are skipped with a stated reason (`pytest -rs`). CI runs both ways, and its `warden` job sets `JUDGE_REQUIRE_WARDEN=1` so a missing Warden is a failure, not a skip. To run what CI's `lint` job runs, use `pip install -e ".[lint]"`, then `ruff check .` and `mypy`.

The CNS pin moved from `v1.9.0` to `v2.0.0`. Judge's suite passed against it with no change to a test, and no Judge code was edited for it. The pin is the release tag in the `dependencies` line of `pyproject.toml`, with the commit it peels to in a comment; every repository of the stack spells that pin the same way.

### Testing against the pin

The Judge itself does not import Warden. Two test files do, because they seat the Judge in the real loop and check the contract
(`tests/test_in_the_loop.py`, `tests/test_contract.py`). They run against the Warden commit pinned in the `warden` extra of
`pyproject.toml`, which is the commit CI checks out; the pin names its Warden version in a comment. Reference the pin there rather
than a version written here: this README does not repeat it, so it cannot go stale.

### Bumping the Warden pin

The tests depend on one exact Warden commit (extra `warden` in `pyproject.toml`), so a change on Warden's `main`
cannot break them without anyone noticing. To move to a newer Warden:

1. Pick the Warden commit you want and copy its full 40-character SHA.
2. Put it after the `@` in the `warden @ git+...` line of `pyproject.toml`, and update the Warden version in the comment on that line.
3. Put the same SHA in the `ref:` of the Warden checkout in `.github/workflows/tests.yml`.
4. Run `pip install -e ".[dev]"` and `pytest`. `tests/test_warden_pin.py` checks that the pin is a full commit, that CI checks out the same commit, and that the comment names the Warden version that is installed; `tests/test_contract.py` checks that `requires_contract` matches the installed Warden's `CONTRACT`.
5. Open a pull request. CI runs the same checks.

### With Warden

Warden loads the Judge as a seat. The flags below are the ones `warden tagteam --help` lists; the paths are placeholders:

```bash
warden tagteam PATH --drafter drafter.seat:Drafter --finisher burnish.finisher:Burnish \
  --judge judge.seat:Judge --authorize ACTOR --scope code --reason TEXT \
  --ghost-root GHOST_TOOLS --swizzle-root SWIZZLE --assay-root ASSAY
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

Each line names what shows it. "Hand-made evidence" means a test builds the input itself.

- Each rule above, one at a time, on hand-made evidence. `tests/test_judge.py`, `tests/test_strict_evidence.py` and `tests/test_red_team_round2.py`. Example: `tests/test_strict_evidence.py::test_a_missing_floor_is_not_zero`.
- Unknown is not approved: wrong types, missing fields, NaN, true/false where a number belongs, and an exception while reading all end in INSUFFICIENT, never an error and never ACCEPT. `tests/test_strict_evidence.py::test_malformed_evidence_is_insufficient_never_an_exception` and `tests/test_strict_evidence.py::test_an_exception_while_reading_fails_closed`.
- Nine pieces of evidence captured from the real Warden loop (a scratch project, with Ghost, SWIZZLE and ASSAY answers stubbed to fixed values), plus `examples/accept.json`, are accepted, and altering any field the Judge reads in the ways a fuzzing audit used is not. `tests/test_real_evidence.py::test_the_nine_real_evidence_files_are_present`, `tests/test_real_evidence.py::test_real_evidence_is_accepted`, `tests/test_real_evidence.py::test_a_mutation_of_real_evidence_is_never_accepted`.
- Seated in the real Warden loop (the pinned Warden, with Ghost, SWIZZLE and ASSAY stubbed): a clean run is accepted, a run with a violated SWIZZLE attack is turned away and the tree is put back, a run whose attacks never ran is held as `ACCEPT_UNVERIFIED` and put back until a person approves it. `tests/test_in_the_loop.py::test_a_clean_run_is_accepted_by_the_judge`, `tests/test_in_the_loop.py::test_a_violated_attack_makes_the_judge_turn_the_whole_run_away`, `tests/test_in_the_loop.py::test_attacks_that_never_ran_leave_the_run_unjudged`.
- A loop that stopped on a refused, put-back or red cycle, or never converged, is not handed to the Judge at all. `tests/test_in_the_loop.py::test_a_loop_that_never_converges_is_not_handed_to_the_judge`, `tests/test_in_the_loop.py::test_a_refused_cycle_stops_the_loop_before_the_judge`, `tests/test_in_the_loop.py::test_a_put_back_cycle_stops_the_loop_before_the_judge`.
- The Judge declares the seat contract and the pinned Warden loads it without a warning. `tests/test_contract.py::test_the_declaration_matches_the_warden_it_runs_with`, `tests/test_contract.py::test_warden_loads_the_judge_with_no_contract_warning`.
- It imports only the standard library and CNS, never measures, never writes. `tests/test_independence.py::test_no_module_imports_anything_that_is_not_allowlisted`, `tests/test_independence.py::test_the_judge_imports_no_warden_and_no_other_role`, `tests/test_independence.py::test_no_module_imports_dynamically_or_writes_a_file`. The test reads the source and fails on an import that is not on a per-module allowlist.
- The `judge` command: exit codes, fail-closed behaviour, delivery of the decision (broken pipe, closed standard output, closed standard input, a full device) and the version. `tests/test_cli.py`, `tests/test_version.py`, `tests/test_docs_claims.py::test_the_exit_codes_are_documented`.
- The CNS gate connector maps each answer to its outcome and binds the result to the evidence. `tests/test_cns_connector.py::test_the_verdict_is_bound_to_the_evidence_it_judged`, and `tests/test_seat_independence.py` shows no decision code imports the connector.
- The pins: CNS by release tag with its commit in a comment, Warden by a full commit that CI checks out too, GitHub Actions by full commit, lint tools by exact version. `tests/test_cns_pin.py`, `tests/test_warden_pin.py`, `tests/test_ci_pins.py`.
- CI runs on every push. Its `lint` job runs ruff and mypy, its `pytest` job runs the suite without Warden, and its `warden` job runs the whole suite against the pinned Warden with `JUDGE_REQUIRE_WARDEN=1`; each on Python 3.11, 3.12 and 3.13 (`.github/workflows/tests.yml`, held by `tests/test_readme_ledger.py::test_every_ci_job_the_readme_names_is_in_the_workflow`).
- With Warden installed the suite has no skipped, expected-to-fail or deselected tests on a system that has `/dev/full` (see WHAT DOES NOT WORK / NOT PROVEN). This README states no test count on purpose, because a number written here drifts; count them with `pytest --collect-only -q`.
- Recorded by hand, not by a test in this repository: on 2026-10-14 the whole circuit, with live Ghost, SWIZZLE and ASSAY, Drafter and Burnish, governed a scratch repository through `warden tagteam --stack` and the Judge's verdict was ACCEPT with its numbers in the reason (Warden's `docs/REGISTRY.json`, row 3). The Judge in that run was the 0.3.0 code. Nobody has repeated it with the current Judge.

## WHAT DOES NOT WORK / NOT PROVEN

- That the rules are the right ones. They are a first draft written to match the failures found so far. Nobody outside the project has reviewed them.
- A recorded run on a real repository. Every full-circuit run recorded for the Judge used a scratch repository or the circuit's own repositories, and used older Judge code (see SELF-HOSTING).
- The captured evidence in `tests/fixtures/real/` comes from a scratch project with stubbed Ghost, SWIZZLE and ASSAY answers. It shows the shape Warden writes, not what the real instruments say about a real project.
- The `warden tagteam` command above is checked against `warden tagteam --help` only. No whole-circuit run with the current pins is recorded.
- It cannot weigh severity beyond "a low attack violation is tolerated, anything else is harm". A single new low-severity Ghost finding is as bad as a critical one.
- Test files are recognized by name and folder. A real source file in a folder called `test`, `tests` or `testing`, or named `test_something.py`, is treated as a test file and turned away (`tests/test_strict_evidence.py::test_judging_paths_are_caught_by_their_shape` shows the shapes).
- Any change to a test file is rejected, even a harmless one, because there is no format-only exception yet. The test-count rule compares passes before and after, so a run that removes a deliberately obsolete test is rejected.
- It trusts the evidence Warden assembles. It cannot tell whether Warden left something out.
- Two tests that hand `/dev/full` to the command as its standard output are skipped on a system that has no `/dev/full` (`tests/test_cli.py::test_an_accept_that_cannot_be_written_to_a_full_device_exits_1_with_one_plain_line` and its rejection twin). The closed-descriptor tests use POSIX features, and CI runs on Linux only. Windows and macOS are untested.
- Python versions other than 3.11, 3.12 and 3.13 are untested.

## KNOWN DEFECTS

Open, with no fix yet.

1. **The cycle checks cannot catch a made-up edit list on a converged run.** The clause "a listed edit that no `APPLIED` cycle explains" cannot fire on a converged run when a finisher may have run. A converged run ends on `NOTHING_TO_PROPOSE` whether or not a finisher then edited files, and the evidence did not say which, so every listed edit can be blamed on the finisher. The clause catches hand-made evidence (for example a record that ends on a `REFUSED` cycle with edits listed), not a fabricated edit list on a converged run, so it is not a protection for real evidence. The `Evidence` row of the pinned CNS now has a `finisher_ran` field (default `None`). Judge does not read it, and adopting it is deferred. The comments in `judge/seat.py` that say the field does not exist predate that. No test yet.

## WHAT BROKE AND HOW IT WAS FIXED

Newest first. Versions and dates are the ones in `CHANGELOG.md`. Versions 0.1.0 to 0.3.0 are reconstructed from git history there. "Test" names what now prevents it coming back.

**0.4.9** (2026-10-22): the 0.4.8 fix for a closed pipe was incomplete. It set `sys.stdout` to `None`, so `judge decide FILE >&-` ended in an `AttributeError` traceback, `judge decide - <&-` ended in one for `read`, an ACCEPT written to a full device ended in an `OSError` traceback (exit 1, or status 120 when buffered) while the same ACCEPT into a broken pipe exited 0, and a program calling `judge.cli.main()` in-process after a broken pipe kept `sys.stdout = None`. The 0.4.8 text had also overstated that a closed standard output is never an error; an ACCEPT that was not delivered is not an approval. Now a broken pipe keeps the earned code quietly, any other failed delivery prints one line and exits 1, unreadable standard input exits 2. How it was found: not recorded in the changelog. Test: `tests/test_cli.py::test_a_closed_stdout_is_one_plain_line_and_an_accept_that_was_not_delivered_exits_1`, `tests/test_cli.py::test_an_accept_that_cannot_be_written_to_a_full_device_exits_1_with_one_plain_line`, `tests/test_cli.py::test_a_closed_stdin_is_one_plain_line_and_exit_2`, `tests/test_cli.py::test_main_run_in_process_leaves_the_callers_stdout_in_place`.

**0.4.8** (2026-10-21): `judge decide FILE | head` ended in a `BrokenPipeError` traceback and exit 1 even for an ACCEPT. The fix was partial (see 0.4.9). The CI `lint` job also ran on Python 3.12 only; it now runs on 3.11, 3.12 and 3.13. Test: `tests/test_cli.py::test_a_broken_pipe_keeps_the_earned_code_quietly_for_accept_and_reject`. The lint matrix has no test.

**0.4.4** (2026-10-21): a fuzzing audit found hand-made evidence that was ACCEPTed although something was unknown. Real Warden does not produce any of it. The holes: `suite_before: null` skipped every before and after comparison, a starting suite that was red or had not run passed, a suite with `exit_code: 0` beside `returncode: 1` passed because the first exit-code name won, an unknown `scope` or edit `kind` passed when only prose changed, a cycle list whose last cycle was `REFUSED`, `PUT_BACK` or `SUITE_RED` with edits listed passed, `test*.txt` files (which pytest collects as doctests) and `venv/`, `env/`, `.tox/`, `.nox/`, `.eggs/`, `node_modules/` and `site-packages/` were not treated as tests or as outside the project. The earlier wording that the listed-edit clause protects real evidence was also withdrawn (see KNOWN DEFECTS 1). Test: `tests/test_real_evidence.py::test_a_missing_starting_suite_is_insufficient_and_says_so`, `tests/test_real_evidence.py::test_exit_codes_that_disagree_are_insufficient_and_name_both`, `tests/test_real_evidence.py::test_an_unknown_scope_is_insufficient_when_only_prose_changed`, `tests/test_real_evidence.py::test_an_unknown_edit_kind_is_insufficient`, `tests/test_real_evidence.py::test_a_refused_last_cycle_with_edits_listed_is_not_accepted`, `tests/test_real_evidence.py::test_a_prose_file_pytest_collects_as_a_doctest_is_judged_like_a_test`, `tests/test_real_evidence.py::test_environment_folders_are_outside_the_project`.

**0.4.2** (2026-10-17): `judge decide` on input nested about 100,000 brackets deep raised an uncaught `RecursionError` (traceback, exit 1); it is now a usage error, exit 2. Also `cycles` and `declined` were required by the command line but never read by the decision, so evidence that contradicted itself (`cycles` empty beside a listed change, an outcome such as `REVERTED`, declined removals with no declined cycle) was accepted. The decision now reads both. The changelog entry first cited "the saved record of a real run", which was not in the repository; the captured evidence was added in 0.4.4. Three existing tests built evidence that was now a contradiction, so their evidence was changed and their assertions were not. Test: `tests/test_cli.py::test_deeply_nested_input_through_the_real_command_exits_2`, `tests/test_judge.py::test_a_cycle_outcome_the_judge_does_not_know_is_not_accepted`, `tests/test_judge.py::test_declined_removals_with_no_declined_cycle_are_not_accepted`, `tests/test_judge.py::test_a_listed_change_that_no_cycle_applied_is_not_accepted`.

**0.4.1** (2026-10-17): installing Judge together with the pinned Warden failed with `ResolutionImpossible` (the two did not name the same CNS), and CI worked around it with `--no-deps`. Warden now pins CNS the same way as Judge and the workaround is gone. Test: no unit test; CI's `warden` job installs the pinned Warden next to Judge and fails on a conflict.

**0.4.0** (2026-10-17): the documents said the Judge imported code from Warden's role module and relied on Warden for everything, which was false once the shared rows moved to CNS, and the old independence test was a denylist that could not catch a false claim. The dependency list now says CNS only, Warden is a test-time extra, the independence test is an allowlist, hard-coded test counts were removed from the documents, and six mypy errors were fixed (optional arithmetic on suite counts, untyped gate attributes). Test: `tests/test_docs_claims.py::test_no_document_claims_the_judge_imports_or_depends_on_warden_alone`, `tests/test_docs_claims.py::test_no_document_hardcodes_a_test_count_or_a_pin`, `tests/test_independence.py::test_no_module_imports_anything_that_is_not_allowlisted`. The mypy errors are held by the `lint` job.

**0.3.0** (2026-10-10, later commits shipped under the same number): three defects. On 2026-10-11 counts printed as text with no exit code could still give a plain ACCEPT with a note, although the code under test can fake them; now they give INSUFFICIENT. On 2026-10-12 the README said an INSUFFICIENT verdict leaves the changes standing; Warden puts the tree back and holds the result, and the Judge's own test had asserted the old behaviour and failed, so the README and that test were corrected. On 2026-10-14, when the circuit governed ASSAY's own repository, Burnish's code tidy reformatted thirteen specimens (recorded hashes, deliberately degraded sources) and only the suite caught it; the Judge now rejects any edit under a fixture or specimen folder whatever the grant. Test: `tests/test_red_team_round2.py::test_text_only_counts_never_give_a_plain_accept`, `tests/test_in_the_loop.py::test_attacks_that_never_ran_leave_the_run_unjudged`, `tests/test_judge.py::test_a_fixture_or_specimen_is_judging_material_even_under_a_code_grant`.

**0.2.0** (2026-10-09): the first red-team pass, "unknown is not approved". The commit lists the cases it closed: attacks, evidence shape, strict true/false types, judging files and paths, skipped tests, repeated Ghost findings, unmeasured checks, and an ACCEPT sentence that states what was checked. Test: `tests/test_strict_evidence.py`.

## SELF-HOSTING

On 2026-10-14 the circuit governed fresh clones of its own seven repositories, Judge's among them. Warden's `docs/REGISTRY.json`, row 5, records for the Judge's clone that the circuit's verdict was ACCEPT with one change, and the change was Burnish's generated facts section in the README. The changes to the clones were not kept. Row 6 of the same file covers four other repositories and does not include the Judge. Both rows predate Warden 0.13.0 and the current rules, and the Judge seat in them was the 0.3.0 code. No fresh run on the current commits is recorded yet. See the [CNS repository](https://github.com/wking53214/CNS).

## CEILINGS CODE CANNOT FIX

This is a young repository kept by one person. It has no outside users yet and no outside review of its rules. Releases are tagged by the owner, so check the repository's tags and releases for what exists. A passing test suite here shows the code does what its tests say; it does not show the rules are the right ones.

## Support

Open an issue at https://github.com/wking53214/Judge/issues.

## Contributing

Welcome, narrowly. A new rule must come with a test that shows it firing and a test that shows it not firing, and must keep the order: harm first, then missing evidence, then ACCEPT.

## License

Apache-2.0. See `LICENSE`.
