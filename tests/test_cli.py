"""The ``judge`` command line: exit 0 only for ACCEPT, and every failure is closed."""

import copy
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from judge import cli

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "accept.json"


def _data() -> dict:
    return copy.deepcopy(json.loads(EXAMPLE.read_text(encoding="utf-8")))


def _write(tmp_path: Path, data: object) -> str:
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def _decision(capsys) -> dict:
    return json.loads(capsys.readouterr().out)


def test_the_documented_example_is_accepted(capsys):
    assert cli.main(["decide", str(EXAMPLE)]) == 0
    out = _decision(capsys)
    assert out["decision"] == "ACCEPT" and out["reasons"] and out["judge"].startswith("judge ")


def test_harm_is_rejected_with_exit_1(tmp_path, capsys):
    data = _data()
    data["suite_after"] = {"ran": True, "passed": 10, "failed": 2, "exit_code": 1}
    assert cli.main(["decide", _write(tmp_path, data)]) == 1
    assert _decision(capsys)["decision"] == "REJECT"


def test_missing_measurement_is_insufficient_with_exit_1(tmp_path, capsys):
    data = _data()
    data["attacks"] = None
    assert cli.main(["decide", _write(tmp_path, data)]) == 1
    assert _decision(capsys)["decision"] == "INSUFFICIENT"


def test_extra_suite_flags_the_judge_reads_are_honoured(tmp_path, capsys):
    data = _data()
    data["suite_after"]["forged"] = True
    assert cli.main(["decide", _write(tmp_path, data)]) == 1
    assert _decision(capsys)["decision"] == "REJECT"


def test_evidence_can_be_read_from_standard_input(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(EXAMPLE.read_text(encoding="utf-8")))
    assert cli.main(["decide", "-"]) == 0
    assert _decision(capsys)["decision"] == "ACCEPT"


@pytest.mark.parametrize("data", [
    {},                                          # nothing
    {"target": "/t"},                            # fields missing
    [],                                          # JSON, but not an object
    "ACCEPT",                                    # a string is not evidence
    None,
    {**json.loads(EXAMPLE.read_text(encoding="utf-8")), "surprise": 1},      # unknown field
])
def test_input_that_is_not_the_schema_is_insufficient_never_approved(tmp_path, capsys, data):
    assert cli.main(["decide", _write(tmp_path, data)]) == 1
    out = _decision(capsys)
    assert out["decision"] == "INSUFFICIENT" and out["reasons"]


@pytest.mark.parametrize("field,value", [
    ("suite_after", "green"), ("suite_after", {"ran": "yes"}), ("suite_after", {"nope": 1}),
    ("changed", "README.md"), ("attacks", 7), ("scope", ["code"]), ("assay", [1]), ("ghost_before", "x"),
])
def test_wrongly_typed_fields_are_never_approved(tmp_path, capsys, field, value):
    data = _data()
    data[field] = value
    assert cli.main(["decide", _write(tmp_path, data)]) == 1
    assert _decision(capsys)["decision"] != "ACCEPT"


def test_an_exception_while_judging_is_insufficient_not_approval(tmp_path, capsys, monkeypatch):
    def boom(self, evidence):
        raise RuntimeError("boom")
    monkeypatch.setattr(cli.Judge, "decide", boom)
    assert cli.main(["decide", str(EXAMPLE)]) == 1
    out = _decision(capsys)
    assert out["decision"] == "INSUFFICIENT" and "RuntimeError" in out["reasons"][0]


def test_an_unknown_decision_from_the_judge_is_not_exit_0(monkeypatch, capsys):
    class Odd:
        decision, reasons, judge = "accept", ("lowercase is not ACCEPT",), "x"
    monkeypatch.setattr(cli, "_decide", lambda data: Odd())
    assert cli.main(["decide", str(EXAMPLE)]) == 1


def test_a_missing_file_is_a_usage_error(tmp_path, capsys):
    assert cli.main(["decide", str(tmp_path / "nope.json")]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "cannot read" in captured.err


def test_a_directory_is_a_usage_error(tmp_path):
    assert cli.main(["decide", str(tmp_path)]) == 2


def test_text_that_is_not_json_is_a_usage_error(tmp_path, capsys):
    path = tmp_path / "x.json"
    path.write_text("{not json", encoding="utf-8")
    assert cli.main(["decide", str(path)]) == 2
    assert capsys.readouterr().out == ""


def test_deeply_nested_input_is_a_usage_error_not_a_traceback(tmp_path, capsys):
    path = tmp_path / "deep.json"
    path.write_text("[" * 100_000, encoding="utf-8")
    assert cli.main(["decide", str(path)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "Traceback" not in captured.err and "nested" in captured.err


def test_deeply_nested_input_through_the_real_command_exits_2(tmp_path):
    path = tmp_path / "deep.json"
    path.write_text("[" * 100_000 + "]" * 100_000, encoding="utf-8")
    done = subprocess.run([sys.executable, "-m", "judge", "decide", str(path)], capture_output=True, text=True, timeout=60)
    assert done.returncode == 2 and "Traceback" not in done.stderr and done.stdout == ""


def test_bytes_that_are_not_text_are_a_usage_error(tmp_path):
    path = tmp_path / "x.json"
    path.write_bytes(b"\xff\xfe\x00\x80")
    assert cli.main(["decide", str(path)]) == 2


@pytest.mark.parametrize("argv", [[], ["decide"], ["nonsense"], ["decide", "a", "b"], ["--bogus"]])
def test_bad_usage_exits_2(argv, capsys):
    assert cli.main(argv) == 2
    assert capsys.readouterr().out == ""


def test_help_exits_0(capsys):
    assert cli.main(["--help"]) == 0
    assert "decide" in capsys.readouterr().out


def test_verbose_logs_go_to_standard_error_and_the_decision_stays_clean_json(capsys):
    assert cli.main(["-vv", "decide", str(EXAMPLE)]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out)["decision"] == "ACCEPT"
    assert "verdict ACCEPT" in captured.err and "reason:" in captured.err


def test_without_verbose_an_accepted_run_logs_nothing(capsys):
    assert cli.main(["decide", str(EXAMPLE)]) == 0
    assert capsys.readouterr().err == ""


def test_the_installed_script_and_module_entry_point_agree(tmp_path):
    for cmd in ([sys.executable, "-m", "judge"], [str(Path(sys.executable).parent / "judge")]):
        version = subprocess.run([*cmd, "--version"], capture_output=True, text=True, check=False)
        assert version.returncode == 0 and version.stdout.startswith("judge "), cmd
        ok = subprocess.run([*cmd, "decide", str(EXAMPLE)], capture_output=True, text=True, check=False)
        assert ok.returncode == 0 and json.loads(ok.stdout)["decision"] == "ACCEPT", cmd
        bad = subprocess.run([*cmd, "decide", str(tmp_path / "missing.json")], capture_output=True, text=True, check=False)
        assert bad.returncode == 2, cmd


def _run_into_a_closed_pipe(path: str) -> subprocess.CompletedProcess:
    """Run the real command with stdout on a pipe whose read end is already closed, as in ``judge decide FILE | head``."""
    read_end, write_end = os.pipe()
    os.close(read_end)
    try:
        return subprocess.run([sys.executable, "-m", "judge", "decide", path], stdout=write_end, stderr=subprocess.PIPE,
                              text=True, timeout=60, check=False)
    finally:
        os.close(write_end)


def test_a_closed_stdout_is_not_a_traceback_and_keeps_the_exit_code_of_an_accept():
    done = _run_into_a_closed_pipe(str(EXAMPLE))
    assert done.stderr == "" and done.returncode == 0


def test_a_closed_stdout_keeps_the_exit_code_of_a_rejection(tmp_path):
    data = _data()
    data["suite_after"] = {"ran": True, "passed": 10, "failed": 2, "exit_code": 1}
    done = _run_into_a_closed_pipe(_write(tmp_path, data))
    assert done.stderr == "" and done.returncode == 1


def test_a_broken_pipe_without_a_file_descriptor_still_returns_the_earned_code(monkeypatch):
    class Gone(io.StringIO):
        def write(self, text):
            raise BrokenPipeError(32, "Broken pipe")

    monkeypatch.setattr(sys, "stdout", Gone())
    assert cli.main(["decide", str(EXAMPLE)]) == 0
