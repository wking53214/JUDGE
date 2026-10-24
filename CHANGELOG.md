# Changelog

All notable changes to Judge are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/). Versions 0.1.0 to 0.3.0 are reconstructed from the git
history.

## [Unreleased]

## [0.4.11] - 2026-10-24

Five steps from the round-6 independent audit. Each defect was reproduced before it was changed.

### Fixed
- Step 1: the "some tests did not run, so a code change cannot be shown safe" rule listed only the edit kinds `write` and
  `delete` (`judge/seat.py`), so a lone `replace` edit to a `.py` file with skips before and after was ACCEPT while the same
  edit as `write` was INSUFFICIENT. It now uses the set of known kinds (`write`, `replace`, `delete`); an unknown kind was
  already INSUFFICIENT. Failing-first tests in `tests/test_strict_evidence.py` cover every kind, case and spacing variants, the
  unknown kind and the cases that stay ACCEPT.
- Step 5: `judge --verbos decide FILE` ran, and `--vers` and `--hel` were taken as `--version` and `--help`, because argparse
  accepts any unambiguous prefix of a long option. Both parsers now set `allow_abbrev=False`, so a prefix is a usage error
  (exit 2). Failing-first tests in `tests/test_cli.py`; the full spellings still work.

### Changed
- Step 2: the README no longer says "any path shaped like a test". A new section "What counts as a test, exactly" lists the
  folders, file names and file name patterns copied from `judge/seat.py`, and states that the "some tests did not run" rule looks
  only at `.py` files. KNOWN DEFECTS lists what the audit reproduced as ACCEPT (JavaScript, TypeScript, Go, Java and Ruby test
  files, a Rust source file, `Cargo.toml`, `.gitignore`); language support is not extended. New `tests/test_readme_patterns.py`
  holds the README lists to the code and documents the gap.
- Step 3: the comments in `judge/seat.py` (module docstring and `_cycle_contradictions`) that said CNS has no `finisher ran` field
  now say CNS 2.0.0 has `Evidence.finisher_ran` and that the Judge does not read it, by the owner's decision, so the gap stays
  open. New `tests/test_finisher_ran_gap.py` holds those statements. No code behaviour changed.
- Step 4: the README's SELF-HOSTING section cites the CNS repository's `docs/evidence/SELFHOSTING_2026-10-23.md` (on its branch
  `claude/horsemen-production-status-5wsndb` until merged): run 1 FINISH_REJECTED because the finisher wrote a test count into
  the README (fixed in the finisher), run 2 ACCEPT with 7 gaps and 42 Ghost findings standing, and what that does not mean.
  Rule-5 edit: `tests/test_readme_ledger.py::test_self_hosting_says_it_predates_the_current_rules_and_links_the_cns_repository`
  pinned the old sentence "No fresh run on the current commits is recorded yet"; it is replaced by two tests, one holding the new
  paragraph with the evidence numbers as constants and one keeping the old assertions that still hold.
- Step 5: the Warden test pin moved from `b57b81e1c98333c43d422666c89a8fcf3ae6eaca` (Warden 0.13.9) to
  `9ecd1124e6c1b1c4ad7daed37b17f9009662dd9d` (Warden 0.13.10), in the `warden` extra of `pyproject.toml` and the `ref:` of the
  Warden CI job. CNS stays `@v2.0.0`; `pip check` is clean.

## [0.4.10] - 2026-10-22

Three changes, nothing else: the CNS pin (step 1), the Warden test pin (step 2) and the README (step 3). No Judge code changed
and no existing test was edited.

### Changed
- The CNS pin moved from the tag `v1.9.0` to the tag `v2.0.0`: `cns @ git+https://github.com/wking53214/CNS.git@v2.0.0`, with
  the commit the tag peels to (`b13e5d2f9e0e4291725f82794b89117c3d840ac1`) in a comment on the pin line. The suite passes against
  the installed cns 2.0.0 (its `direct_url.json` shows `requested_revision` `v2.0.0` and that commit) with no change to a test.
- The Warden test pin moved from `380894f0304ef40587dd29efd41b4ceccf94a5d3` (Warden 0.13.8) to
  `b57b81e1c98333c43d422666c89a8fcf3ae6eaca` (Warden 0.13.9), in the `warden` extra of `pyproject.toml` and the `ref:` of the
  Warden CI job. pip resolves one CNS (v2.0.0) with Warden installed and `pip check` is clean. The `Warden.git` spelling is unchanged.
  Judge pins no other sibling.
- The README was rewritten to state what works (each line names a test or CI job), what does not work or is not proven, the open
  defects, what broke and how it was fixed, what has and has not been recorded about the circuit governing this repository, and
  the limits code cannot fix. The sections "WHAT IS BEAUTIFUL", "WHAT IS IMPLEMENTED", "WHAT IS PROVEN", "WHAT REMAINS OUTSTANDING"
  and "CLAIMS VS REALITY" were removed: their content is either in the new sections or could not be shown. The install section
  warns that the bare name `judge` on PyPI is another project. The README and the header of this file no longer say whether
  release tags exist.

### Added
- `tests/test_readme_ledger.py`: the README keeps its required sections in order, every test it names exists, every ledger entry
  cites a version and date in this file, the CI jobs it names are in the workflow, it uses no marketing words or em dash, its
  install lines never use a bare package name, and its self-hosting paragraph says the recorded runs predate the current rules.

### Known defects found while writing the README (open, listed in the README)
- An edit of kind `replace` on a `.py` file does not trigger the "some tests did not run" rule, which lists only `write` and
  `delete`; with skips before and after, a lone `replace` edit is ACCEPTed. No fix yet.
- The comments in `judge/seat.py` that say the CNS `Evidence` shape has no `finisher ran` field are out of date: the shape
  now has `finisher_ran`. Judge does not read it, and adopting it is deferred.

## [0.4.9] - 2026-10-22

Two changes, nothing else: the Warden test pin (step 1) and delivery of the decision (step 2).

### Fixed
- Delivery of the decision is now handled in every case instead of only a broken pipe. The 0.4.8 closed-pipe fix set
  `sys.stdout = None`, which (a) made `judge decide FILE >&-` end in an `AttributeError` traceback (`'NoneType' object has no
  attribute 'flush'`) and `judge decide - <&-` end in one for `read`, (b) left an ACCEPT written to a full device ending in an
  `OSError` traceback (exit 1, or exit status 120 with buffered output), while the same ACCEPT into a broken pipe exited 0, and
  (c) was process-global, so a program calling `judge.cli.main()` in-process after a broken pipe kept `sys.stdout = None` and lost
  its later prints. Now `main` never replaces `sys.stdout`; the rule is: the reader left (broken pipe) keeps the earned code
  quietly; standard output closed or a failed write prints one plain line to standard error and exits 1 for every decision, so an
  ACCEPT that was not delivered exits 1 (it was overstated before that a closed standard output is never an error); a closed or
  unreadable standard input prints one plain line and exits 2. After a failed write the process's real standard output is closed so
  the interpreter's flush at exit cannot fail again (exit status 120). The `cli.py` docstring and the README exit-code table state
  the rule. New tests in `tests/test_cli.py` run the real command with a closed stdout, a closed stdin, a full device
  (`/dev/full` opened for writing as the child's stdout), and a broken pipe for ACCEPT and REJECT, with and without
  `PYTHONUNBUFFERED`, and check `sys.stdout` is untouched after an in-process `main()`; all but the broken-pipe regression guards
  fail on the 0.4.8 code. No pre-existing test was edited.

### Changed
- The Warden test pin moved from `1636e1a21f124eedbf6e158db95dc75344f4308d` (Warden 0.13.7) to
  `380894f0304ef40587dd29efd41b4ceccf94a5d3` (Warden 0.13.8, not tagged), in the `warden` extra of `pyproject.toml` and the
  `ref:` of the Warden CI job. The `Warden.git` spelling and the CNS tag `@v1.9.0` are unchanged.

## [0.4.8] - 2026-10-21

### Changed
- The Warden test pin moved from `0c1ea567f0b69586cfd735f82260774aec9552bb` (Warden 0.13.6) to
  `1636e1a21f124eedbf6e158db95dc75344f4308d` (Warden 0.13.7, not tagged), in the `warden` extra of `pyproject.toml` and the
  `ref:` of the Warden CI job. The `Warden.git` spelling and the CNS tag `@v1.9.0` are unchanged.
- The CI `lint` job (ruff and mypy) now runs on Python 3.11, 3.12 and 3.13 instead of 3.12 only.

### Fixed
- `judge decide FILE | head` no longer ends in a `BrokenPipeError` traceback (and exit 1 even for an ACCEPT) when the reader closes the
  pipe. A closed standard output is handled quietly and the exit code stays the one the decision earned. The documented recipe
  (`os.dup2` onto `os.devnull`) is not used because `tests/test_independence.py` keeps `os` out of the Judge; the command drops
  `sys.stdout` instead, which also stops the flush at exit from raising. New tests in `tests/test_cli.py` run the real command
  with a closed pipe.

## [0.4.7] - 2026-10-21

### Changed
- The CNS pin is now spelled by release tag, `cns @ git+https://github.com/wking53214/CNS.git@v1.9.0`, with the commit the tag
  peels to (`da18e411743d4e3b0e783105394d845fb1c16746`) in a comment. It is the same CNS release as before.
- The Warden test pin moved from `decc3c3b5af479ad0eef3df4d66dbcb21e90897c` (Warden 0.13.5) to
  `0c1ea567f0b69586cfd735f82260774aec9552bb` (Warden 0.13.6, not tagged), in the `warden` extra of `pyproject.toml` and the
  `ref:` of the Warden CI job.

## [0.4.6] - 2026-10-21

### Changed
- The CNS pin moved from `5252ceebe98185f7be81212d988055ccf9884568` (v1.8.0) to `da18e411743d4e3b0e783105394d845fb1c16746` (v1.9.0).
- The Warden test pin moved from `36e98433f4928b7d12905f02b56e55ee1943b56e` (Warden 0.13.4) to
  `decc3c3b5af479ad0eef3df4d66dbcb21e90897c` (Warden 0.13.5, not tagged), in the `warden` extra of `pyproject.toml` and the
  `ref:` of the Warden CI job.
- `origin/main` (PR #15) was merged into this branch. Its conflicts in `README.md` and `pyproject.toml` were resolved by
  keeping this branch's full-commit pins and Warden-as-test-extra layout.

## [0.4.5] - 2026-10-21

### Changed
- The Warden test pin moved from `580f659` (Warden 0.13.3) to `36e98433f4928b7d12905f02b56e55ee1943b56e` (Warden 0.13.4), in the
  `warden` extra of `pyproject.toml` and the `ref:` of the Warden CI job. Warden 0.13.4 requires every instrument root to be a
  git checkout with a readable version.
- No test or fixture needed a change for Warden 0.13.4: the whole suite passes against it unchanged, with nothing skipped.

## [0.4.4] - 2026-10-21

### Fixed
A round-3 fuzzing audit found hand-made evidence that was ACCEPTed although something was unknown. Real Warden does not
produce any of it today; "unknown is not approved" is now true for it too.
- `suite_before: null` was ACCEPTed and silently skipped every before and after comparison. The starting suite must now be
  present, must have run and must be green (`failed` 0, `errors` 0, exit code 0), else INSUFFICIENT with the reason named.
  A starting suite with `failed: 5, errors: 3, exit_code: 1`, or `ran: false`, was ACCEPTed too; the same rule covers it.
- A suite with `exit_code: 0` beside `returncode: 1` was ACCEPTed because the first exit-code name present won. Every exit-code
  name present is now read; any disagreement, or a value that is not a whole number, is INSUFFICIENT.
- An unknown `scope` (`"banana"`, `""`) or an unknown edit `kind` was ACCEPTed when only prose files changed. Both are now
  INSUFFICIENT (known scopes: `documentation`, `code`, `all`; known kinds: `write`, `replace`, `delete`). `target` must be text.
- A cycle list whose last cycle was `REFUSED`, `PUT_BACK` or `SUITE_RED`, with edits listed, was ACCEPTed. A last cycle that
  stopped the loop without converging is now INSUFFICIENT. Warden judges only converged runs, whose last cycle is
  `NOTHING_TO_PROPOSE`; `tests/test_in_the_loop.py` shows with the real loop that a never-converging, refused, put-back or red
  run is never handed to the Judge.
- Protected-path gaps: pytest collects `test*.txt` as doctests by default, so `testing.txt`, `tests.txt` and the like are now
  judged like tests (REJECT). `venv/`, `env/`, `.tox/`, `.nox/`, `.eggs/`, `node_modules/` and `site-packages/` are now environment
  folders like `.venv/` (REJECT, edit outside the project).

### Added
- Captured real evidence: `tests/fixtures/real/` holds the nine evidence shapes the real Warden loop produced (one applied
  cycle, two cycles, one cycle with two edits, a declined proposal then an applied cycle, a finisher only, an applied cycle then
  a finisher, nothing to propose, a removal commented out, with and without a finisher), and `tests/fixtures/accept.json` is a
  copy of `examples/accept.json`. `tests/test_real_evidence.py` checks that every one is ACCEPTed (also through the command line)
  and that each way of altering the fields the Judge reads, alone and stacked, is not.

### Changed
- The Warden test pin moved from `9d9a71d` (Warden 0.13.2) to `580f659336818b4a5a2c0ca235d2344012536426` (Warden 0.13.3), in the
  `warden` extra of `pyproject.toml` and the `ref:` of the Warden CI job.
- No existing test was edited.

### Known limit (documented, not fixed)
- The clause "a listed edit that no `APPLIED` cycle explains" cannot fire when a finisher may have run: a converged run ends on
  `NOTHING_TO_PROPOSE` whether or not a finisher then edited files, so any listed edit can be blamed on the finisher. It catches
  hand-made evidence only, and the earlier wording that it protects real evidence is withdrawn. Closing it needs a
  `finisher ran` field in the CNS `Evidence` shape, which is a change to CNS and the owner's call.

## [0.4.3] - 2026-10-21

### Changed
- Warden test pin moved from `ec551d8` (Warden 0.13.1) to `9d9a71d1bc3195f0abd9aee8fe553cc09838b684` (Warden 0.13.2), in the
  `warden` extra of `pyproject.toml` and in the `ref:` of the Warden CI job. Warden 0.13.2 refuses a ghost scan with no root and
  enforces instrument roots; the real-loop tests were run against it.

## [0.4.2] - 2026-10-17

### Fixed
- `judge decide` on input nested deeply enough to exhaust the JSON decoder (about 100,000 open brackets) raised an
  uncaught `RecursionError`: a traceback and exit 1. It is now a usage error, exit 2, like other undecodable input.
- `cycles` and `declined` were required by the command line but never read by the decision, so evidence that
  contradicted itself (`cycles` empty beside a listed change, an outcome such as `REVERTED`, declined removals with no
  declined cycle) was still accepted. The decision now reads both. It names a contradiction and returns INSUFFICIENT
  for: a cycle outcome it does not know, two cycles with one number, more `APPLIED` cycles than listed edits, listed
  edits that no `APPLIED` cycle explains (unless a converged loop, ending on `NOTHING_TO_PROPOSE`, could have had a
  finishing change, whose edits belong to no cycle), and `declined` entries with no `DECLINED` cycle. A wrong type in
  either field is unreadable evidence. Declined entries beside an applied change are normal and still accepted.
  Real-loop tests (finish-only, declined plus applied, applied plus finish) show Warden's own evidence is unaffected.
  (This entry first cited "the saved record of a real run", which was not in the repository; the captured evidence is
  now under `tests/fixtures/real/`, added in 0.4.4. The clause for listed edits that no `APPLIED` cycle explains cannot
  fire on a converged run when a finisher may have run; see 0.4.4.)
- The README and this file said no release tags exist; an older tag `v0.10.0` does, and the text now says so.

### Changed
- Three existing tests built evidence with an `APPLIED` cycle and no listed edit, which is the contradiction now caught;
  their evidence carries a `NOTHING_TO_PROPOSE` cycle instead and their assertions are unchanged.
- Every GitHub Action in the workflow is pinned to a full commit (`actions/checkout` v4.2.2, `actions/setup-python`
  v5.6.0), guarded by `tests/test_ci_pins.py`. The `lint` extra pins ruff (0.17.1) and mypy (2.4.0) to exact versions.
  The Warden test-time pin is unchanged.

## [0.4.1] - 2026-10-17

### Changed
- The Warden test-time pin moved from `2cf0eec` (Warden 0.12.0) to `ec551d8e10f82b6e3e681593a97011ae517d360b`
  (Warden 0.13.1, untagged), in `pyproject.toml` and in the `ref:` of the CI Warden job.
- Warden now pins CNS by the same full commit as Judge, so `pip install -e ".[dev]"` resolves without conflict
  (the earlier `ResolutionImpossible` is gone). The `--no-deps` workaround is removed from the CI Warden job.

## [0.4.0] - 2026-10-17

### Added
- `judge` command line: `judge --version` and `judge decide EVIDENCE.json` (or `-` for standard input). It prints the
  decision as JSON. Exit code 0 means ACCEPT and nothing else; 1 is any other decision; 2 is a usage error.
- `python -m judge`, the same command.
- `judge.__version__`, read from the installed package metadata, so `pyproject.toml` is the single source of the version.
  The Verdict's `judge` field now names the running version (`judge 0.4.0`).
- Standard `logging` at the decision seam (logger `judge`): the decision at INFO, each reason at DEBUG, unreadable
  evidence at WARNING. The package installs only a `NullHandler`; the command line sends logs to standard error (`-v`, `-vv`).
- `examples/accept.json`, a documented decision input.
- `CHANGELOG.md`.
- Ruff and mypy configuration and CI gates; Python 3.13 in the CI matrix and the classifiers.
- A CI job that checks out Warden at the pinned commit and runs the whole suite with `JUDGE_REQUIRE_WARDEN=1`, so the
  real-loop and contract tests cannot be silently skipped.

### Changed
- Dependencies now say what is true: the runtime dependency is CNS alone (`cns.seat`, `cns.gate`, `cns.suite`). Judge
  imports no Warden code. Warden moved to the test-time extra `warden` (also in `dev`), still pinned to a full commit.
- CNS is pinned to a full commit (the v1.8.0 commit) instead of the tag.
- The independence test is now an allowlist of the imports each module may make, so any new import fails it. The old
  denylist could not catch a false claim.
- `tests/test_cns_connector.py` takes `Verdict` and `SuiteRun` from CNS instead of Warden.
- README and STACK.md no longer claim Judge imports `warden.roles` or depends on Warden alone; hard-coded test counts removed.

### Fixed
- Six mypy errors: Optional arithmetic on suite counts in `judge/seat.py` and untyped gate attributes and a `decide`
  argument in `judge/cns_connector.py`. `JudgeGate.name` and `.position` are now plain attributes, as `cns.gate.Gate` declares.

## [0.3.0] - 2026-10-10

### Added
- Hardening of the evidence checks: protected files (tests, test settings, CI, lockfiles, Dockerfiles), Ghost's baseline,
  ASSAY's floor, and the suite's exit code (a5c14d8).

### Changed (later commits shipped under 0.3.0 without a version bump)
- Text-only suite counts can no longer produce a plain ACCEPT (2026-10-11).
- INSUFFICIENT puts the tree back and holds the result; README corrected (2026-10-12).
- A fixture or specimen folder is judging material (2026-10-14).
- The shared rows (`Evidence`, `Verdict`, `SuiteRun`) come from CNS 1.7.0, later 1.8.0 (2026-10-15).
- `judge.cns_connector`: the Judge as a CNS gate at the OMEGA end, with tests that the decision code does not import it (2026-10-16).
- The Warden pin moved several times, the last to an untagged 0.12.0 commit (2026-10-17).

## [0.2.0] - 2026-10-09

### Added
- The Judge fails closed: unknown is not approved (133732a).
- `requires_contract = "1"` on the seat (b562a52).

## [0.1.0] - 2026-10-08

### Added
- The Judge: the third party that decides ACCEPT, REJECT or INSUFFICIENT from the evidence of a whole run.
- Reads ASSAY's grade of Ghost: reject below the floor, insufficient if it is missing.
