"""The Judge decides and nothing else: every import in every module is on a reviewed allowlist.

A denylist can only catch what its author thought of. This is an allowlist: each module in the package
may import exactly the modules named for it below, so any new import (a Warden module, ``ast``,
``subprocess``, ``os``, a third-party package) fails here until a person adds it on purpose, in review.
Allowed everywhere: ``judge.*``. Allowed outside the standard library: only CNS's shared rows
(``cns.seat``, ``cns.suite``) and its gate contract (``cns.gate``, used by the connector alone).

The Judge imports no Warden code at all. Warden is a test-time extra (see pyproject.toml).
"""

import ast
import sys
from pathlib import Path

import judge

ROOT = Path(judge.__file__).resolve().parent

#: Module stem -> the exact modules it may import (relative imports count as ``judge.*``, always allowed).
ALLOWED: dict[str, frozenset[str]] = {
    "__init__": frozenset({"logging"}),
    "__main__": frozenset(),
    "_version": frozenset({"__future__", "importlib.metadata"}),
    "cli": frozenset({
        "__future__", "argparse", "dataclasses", "json", "logging", "sys", "collections.abc", "pathlib", "typing",
        "cns.seat", "cns.suite",
    }),
    "cns_connector": frozenset({"__future__", "dataclasses", "collections.abc", "typing", "cns.gate", "cns.seat"}),
    "seat": frozenset({"__future__", "logging", "re", "unicodedata", "collections", "collections.abc", "pathlib", "typing", "cns.seat"}),
}
CNS_MODULES = {"cns.seat", "cns.suite", "cns.gate"}
#: Calls that import, run or write something the Judge must never do.
_DYNAMIC = {"__import__", "import_module", "exec", "eval"}
_WRITERS = {
    "write_text", "write_bytes", "open", "unlink", "mkdir", "rename", "replace", "remove", "write", "writelines", "touch",
    "rmdir", "rmtree", "makedirs", "symlink_to", "hardlink_to", "chmod", "truncate",
}


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imports(path: Path) -> set[str]:
    """Every module imported anywhere in the file (also inside functions), relative ones as ``judge.*``."""
    names: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                names.add("judge." + (node.module or ""))
            else:
                names.add(node.module or "")
    return names


def _modules() -> list[Path]:
    return sorted(ROOT.rglob("*.py"))


def test_every_module_has_a_reviewed_allowlist():
    assert {p.stem for p in _modules()} == set(ALLOWED), "a module was added or removed: review its imports and update ALLOWED"
    assert not [p for p in ROOT.rglob("*") if p.is_dir() and p.name != "__pycache__"], "subpackages need their own review"


def test_no_module_imports_anything_that_is_not_allowlisted():
    offenders = {}
    for p in _modules():
        extra = {m for m in _imports(p) if not m.startswith("judge.")} - ALLOWED[p.stem]
        if extra:
            offenders[p.name] = sorted(extra)
    assert offenders == {}


def test_the_allowlists_themselves_are_only_stdlib_cns_and_judge():
    allowed = set().union(*ALLOWED.values())
    outside = {m for m in allowed if m.split(".")[0] not in sys.stdlib_module_names and m not in CNS_MODULES}
    assert outside == set()
    # the dangerous standard-library modules are not on any list
    assert not allowed & {"ast", "subprocess", "shutil", "os", "socket", "ctypes", "pickle", "importlib"}


def test_the_judge_imports_no_warden_and_no_other_role():
    for p in _modules():
        tops = {m.split(".")[0] for m in _imports(p)}
        assert not tops & {"warden", "burnish", "drafter", "ghost_buster", "ghost_tools", "swizzle", "assay"}, p.name


def test_no_module_imports_dynamically_or_writes_a_file():
    for p in _modules():
        calls = {getattr(n.func, "attr", getattr(n.func, "id", "")) for n in ast.walk(_tree(p)) if isinstance(n, ast.Call)}
        assert not calls & _DYNAMIC, f"{p.name} calls {sorted(calls & _DYNAMIC)}"
        assert not calls & _WRITERS, f"{p.name} calls {sorted(calls & _WRITERS)}"


def test_the_allowlist_would_catch_a_new_import(tmp_path):
    """The check is live: a module that imports something unlisted is an offender."""
    bad = tmp_path / "seat.py"
    bad.write_text("import warden\nimport os\nfrom cns.gate import Gate\nfrom .x import y\n", encoding="utf-8")
    extra = {m for m in _imports(bad) if not m.startswith("judge.")} - ALLOWED["seat"]
    assert extra == {"warden", "os", "cns.gate"}
