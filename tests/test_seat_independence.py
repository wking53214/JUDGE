"""The Judge decides without CNS's gate contract. Only the connector module may import it.

The connector (``judge.cns_connector``) wraps the Judge as a ``cns.gate`` gate. Nothing in the
Judge's own decision code may depend on that wrapper or on ``cns.gate``: the Judge's answer is
the same whether or not anyone connects it. This test reads the source, so a new import added
to the decision code fails here rather than in a consumer."""

import ast
from pathlib import Path

import judge

PACKAGE = Path(judge.__file__).resolve().parent
CONNECTOR = "cns_connector"


def _imported_modules(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            yield module
            for alias in node.names:
                yield f"{module}.{alias.name}".lstrip(".")


def _decision_modules():
    return sorted(p for p in PACKAGE.glob("*.py") if p.stem != CONNECTOR)


def test_the_package_has_a_decision_module_to_check():
    assert [p.name for p in _decision_modules()] and (PACKAGE / "seat.py") in _decision_modules()


def test_no_decision_module_imports_the_cns_connector():
    offenders = {p.name: [m for m in _imported_modules(p) if CONNECTOR in m.split(".")]
                 for p in _decision_modules()}
    assert {k: v for k, v in offenders.items() if v} == {}


def test_no_decision_module_imports_the_cns_gate_contract():
    offenders = {p.name: [m for m in _imported_modules(p) if m == "cns.gate" or m.startswith("cns.gate.")]
                 for p in _decision_modules()}
    assert {k: v for k, v in offenders.items() if v} == {}


def test_the_connector_is_the_only_module_that_speaks_the_gate_contract():
    speaking = [p.name for p in PACKAGE.glob("*.py")
                if any(m == "cns.gate" or m.startswith("cns.gate.") for m in _imported_modules(p))]
    assert speaking == [f"{CONNECTOR}.py"]
