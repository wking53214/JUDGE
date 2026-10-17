# Changelog

All notable changes to Judge are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [Semantic Versioning](https://semver.org/). Versions 0.1.0 to 0.3.0 are reconstructed from the git
history; no release tags exist yet.

## [Unreleased]

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
