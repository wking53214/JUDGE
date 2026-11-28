# Outside review of the Judge: a reviewer's guide

Written 2026-11-28 for Judge 0.20.0. This guide is for someone who does not work on this project and has agreed to read the Judge's rules and try to break them. It is the preparation for must-have 1 of ROAD TO 1.0.0 in `README.md`. No review has been made yet. Nothing here claims the rules are right.

## 1. What is being asked

Read the rules, try to make the Judge approve something it should not (or turn away something it should approve), and report what you find. A finding is useful when it is any one of these:

- evidence that a careful person would call harmful, and the Judge says ACCEPT;
- a verdict that depends on something other than the evidence and the project folder;
- a rule that is missing, in the wrong order, or too loose;
- a reason sentence that could mislead a person who is deciding whether to keep a held result;
- a way to avoid the test detection (a test hidden from the lists of names and marks).

**Who counts as outside.** The owner has not yet defined this. This guide assumes: someone who did not write, commit to or direct changes to this repository, and who is not the maintainer's own assistant. The outside check of 2026-11-28 (KNOWN DEFECTS 2) was made by the maintainer's assistant and is not a review. A reviewer who is unsure whether they qualify should say so in their report.

**If the Judge has moved on.** This guide was written for Judge 0.20.0. If `judge --version` prints something newer, read `CHANGELOG.md` for the rules that changed since.

Not asked: style of the code, Warden's, Ghost's, SWIZZLE's or ASSAY's own behaviour, or how well the project is run. The Judge does not run anything; it only reads and decides.

## 2. The Judge in one minute

A tool called Warden runs a loop that proposes changes to a project, tests them, and collects evidence: test results before and after, what the scanner Ghost found before and after, what the attack tool SWIZZLE did to the governor, how the answer key ASSAY graded Ghost, and which files changed. Warden hands that evidence to the Judge once, at the end. The Judge returns one of three words with reasons:

- **ACCEPT**: the change stands. This is the only approval.
- **REJECT**: the evidence shows harm. Warden puts the whole project back as it was.
- **INSUFFICIENT**: nothing shows harm, but something is unknown or needs a person. Warden puts the project back and holds the result until a named human approves that exact result.

The governing rule is "unknown is not approved": only values the Judge recognizes count as good. The Judge never raises an error; any trouble reading evidence ends in INSUFFICIENT.

## 3. Who the Judge is meant to stop, and who it is not

The circuit works like this (see `README.md`, "WHAT THIS IS"): some actor proposes a change through Warden's claim seat, Warden applies it and collects evidence, and the Judge decides. The Judge is meant to stop a proposed change that makes the project worse (a worse test result, a new serious finding) or that tampers with the checks (tests, test settings, Ghost's own files, version-control folders). It is not meant to stop a person who controls the evidence file or the machine the Judge runs on; that is the gap signing is meant to close (below). This is the working boundary as the README describes it. If you think the boundary is drawn in the wrong place, say so; that is itself a finding.

## 4. What the Judge trusts (read this before reporting)

These are known and accepted for now. They are listed so you do not spend time on them, but a way to exploit them without the access described is a real finding.

- **The evidence is not signed.** Anyone who can write the evidence file can change the verdict. Signing is must-have 2 of ROAD TO 1.0.0 and is not done.
- **The Judge trusts Warden to have collected everything.** It cannot tell if something was left out. Signing would prove who wrote the evidence, not that it is complete.
- **The project folder is read.** The Judge looks at the folder named in `target` on the machine it runs on, to follow symbolic links in edited paths, to read written code files for tests inside them, and (through `judge/lastcommit.py`) to read a deleted file as it stood in the project's last commit. The same evidence can give a different verdict on a different folder.
- **The CNS release it is pinned to** defines the fields the evidence can carry. The pin is in `pyproject.toml`.

## 5. Where the rules are

| what | where |
|---|---|
| The rules in order, in plain text | the header of `judge/seat.py` |
| The same rules as a table with what each verdict needs | "ARCHITECTURAL STORY" in `README.md` |
| Which paths count as tests, test settings or CI files | "What counts as a test, exactly" in `README.md`, and the lists in `judge/seat.py` |
| Reading a deleted file from the last commit | `judge/lastcommit.py` |
| The command line and its exit codes | `judge/cli.py`, "From the command line" in `README.md` |
| The CNS gate connector (maps each verdict to an answer) | `judge/cns_connector.py` |
| Real evidence to read: the three records of the whole-circuit run (ACCEPT, hold, REJECT) | `tests/fixtures/circuit_run/accept.json`, `tests/fixtures/circuit_run/hold.json`, `tests/fixtures/circuit_run/reject.json` |
| What is proven, not proven, and open | "WHAT WORKS", "WHAT DOES NOT WORK / NOT PROVEN", "KNOWN DEFECTS" in `README.md` |
| The owner's rulings that shaped a rule | named, with their dates, in the header of `judge/seat.py` and in `CHANGELOG.md` |

The order matters and is part of what you are asked to judge: unreadable evidence first, then harm (REJECT), then missing or unknown evidence and holds (INSUFFICIENT), then ACCEPT.

## 6. Get it running

```bash
git clone https://github.com/wking53214/JUDGE.git
cd JUDGE
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest
judge decide examples/accept.json
```

Python 3.11 or newer. The install fetches the pinned CNS and Warden from GitHub, so it needs network access to github.com. The suite passes with nothing skipped when the pinned Warden is installed (the `dev` extra installs it). The tests are the specification: each rule has a test that shows it firing. To see what a rule does, find its test, then weaken the rule in `judge/seat.py` and watch that test fail.

To try your own evidence, copy `examples/accept.json`, change it, and run `judge decide FILE`. The `target` field must name a folder that exists on your machine; the example uses `.`, the folder you run the command from. Exit code 0 means ACCEPT and nothing else does.

## 7. Probes to start with

Each row is one change to a copy of `examples/accept.json`, with the verdict the Judge gives. They were run on 2026-11-28 and `tests/test_review_package.py` runs them again on every change, so this table cannot drift from the code. Several rows are the Judge working as designed; they are here because a reviewer should decide whether the design is right.

| id | change to the example | verdict | why it may matter |
|---|---|---|---|
| P1 | `swizzle_proofs` set to false | REJECT | the attack tool's own self-check failed |
| P2 | `suite_after` gets one failed test | REJECT | a red suite at the end |
| P3 | a second attack, severity `low`, status `violated` | ACCEPT | a violated low-severity attack is tolerated by design; is that right? |
| P4 | the same attack at severity `medium` | REJECT | any severity above low is harm |
| P5 | ASSAY `floor` 0 and `caught` 0 | ACCEPT | a floor of zero given on purpose is allowed; does that make the grade meaningless? |
| P6 | one new Ghost finding, no severity word given | REJECT | a finding with no readable severity is treated as harm |
| P7 | one new finding, severity word `minor` | INSUFFICIENT | held for a named human by the owner's ruling of 2026-10-28 |
| P8 | `suite_after` red and `target` not text | INSUFFICIENT | unreadable evidence is checked before harm, so the red suite is not mentioned |
| P9 | no cycles, no edits, nothing changed | ACCEPT | a run that changed nothing is approved when the evidence is complete |
| P10 | an edit to `../x.txt` | REJECT | an edit outside the project |
| P11 | `suite_after` passed count one lower than `suite_before` | REJECT | fewer passing tests than before |
| P12 | `target` names a folder that does not exist | INSUFFICIENT | the symbolic-link check could not run |
| P13 | a written test file (`test_x.py` in a folder called `tests`) under a documentation grant | REJECT | code changed under a documentation grant |
| P14 | the same test file under scope `code` | INSUFFICIENT | a changed test is held for a named human, not approved by the machine |
| P15 | both suite runs name their tests; one test that passed at the start is replaced by another, so the counts stay equal | REJECT | tests are compared by name, not only by count |
| P16 | `suite_after` marked `text_only` while also giving an exit code | INSUFFICIENT | the evidence contradicts itself about where its counts came from |
| P17 | an edit to a path under `tests`, with one letter swapped for a look-alike from another script, scope `code` | INSUFFICIENT | look-alike letters are read as Latin ones, then the path counts as a test |
| P18 | an edit to a path under an upper-case `TESTS` folder, scope `code` | INSUFFICIENT | paths are compared without regard to case |
| P19 | Ghost's baseline suppresses one more finding at the end | REJECT | hiding a finding by suppressing it |
| P20 | an edit to `.git/hooks/pre-commit` | REJECT | an edit into a version-control folder |
| P21 | `unmeasured` lists a check that never ran | INSUFFICIENT | a check that did not run is never read as fine |
| P22 | `attacks` is empty | INSUFFICIENT | no attack was attempted, so nothing was tested |
| P23 | `suite_after` marked `forged` | REJECT | a result marked forged cannot be believed |

## 8. Questions we most want answered

1. **Order.** Is it right that unreadable evidence outranks harm (P8)? A real Warden types its evidence and cannot produce such a record, but a hand-made one can.
2. **Tolerated and allowed values.** Are P3 (a low-severity violation is fine), P5 (a floor of zero is allowed) and P9 (no change is approved) sound, or does any of them let something through that should stop?
3. **Severity.** The Judge uses Ghost's own words (`major` and `critical` are harm; `minor` and `informational` are held) and keeps them apart from Warden's `high`, `medium` and `low`. Can the two scales be confused, or the mapping from finding id to word be gamed?
4. **Counting findings.** New findings are counted one by one, so a repeated finding counts as new. Does anything let a new problem hide inside an old finding's id, or inside the baseline of suppressed findings?
5. **Test detection.** A test is found by the name of its path and by marks in its text, not by understanding code. What evades the lists (a framework, a dialect, a generated test, a name against convention)? Which innocent files are held needlessly? Known cases are in section 9.
6. **Holds.** A changed test is held for a named human and never approved by the machine. Could the reason sentence lead a person to approve something they should not? Could a hold be turned into an ACCEPT by splitting the change?
7. **Paths.** Case, symbolic links, look-alike letters from another script, and paths that reach `.git` or `.ghost_*`. What is missed?
8. **What is not measured.** The ACCEPT sentence says what the suite itself did (a write outside the project, a planted hook) is not measured. Is there something cheap to measure that would matter?
9. **The gate connector.** INSUFFICIENT maps to `RETRY`, and asking again with the same evidence gives the same hold. Is that mapping a trap for a caller?
10. **Anything missing.** Is there a kind of harm that no rule looks for?
11. **Reading the input.** `judge decide` reads a JSON file and refuses one with a repeated key (the last copy used to win). Is there another way the same bytes can be read two ways, by the Judge and by whatever else reads that file?
12. **The boundary in section 3.** Is "stop a bad proposed change, not a person who controls the evidence" the right line for the first release?

## 9. Known limits (do not report these as new)

They are written in `README.md` under KNOWN DEFECTS and ROAD TO 1.0.0, and 1.0.0 is planned to ship with them told to users:

- an edit to a file that holds tests is held even when its tests are unchanged, outside Rust;
- no comparison of tests by name for Rust, because Warden's cargo runner reports no test names;
- tests are found by names and marks, not by understanding code, and one Common Lisp mark holds a file needlessly (a line starting `(test ` where `test` is only a variable);
- the zUnit and MFUnit marks were never checked against real code;
- the Judge trusts Warden to collect all the evidence;
- the whole-circuit run was made on a scratch project, with changes chosen to produce each verdict, by the maintainer's assistant.

## 10. How to report, and what happens to a finding

For each finding, say what you changed (or which files), what the Judge said, what you expected and why. A copy of the evidence file that shows it is the best report. Open an issue at https://github.com/wking53214/JUDGE/issues. If you would rather not publish a finding, open an issue that says so without details and the owner will arrange another way.

Each finding is answered in `README.md` under ROAD TO 1.0.0, in one of two ways:

- **Fixed**, with a test that fails without the fix. A new rule is also weakened by hand once to confirm a test fails. A rule may be made stricter without asking; loosening a rule needs the owner's decision (William N. King).
- **Accepted as a limit**, listed in KNOWN DEFECTS with the reason.

You will be named in the answer if you want to be.

## 11. What a review does not show

A review shows the rules were read by someone who did not write them. It does not show the rules are complete, and it does not replace signed evidence (must-have 2). After the review the README will still say what was and was not checked.
