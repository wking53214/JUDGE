"""The Judge decides. It imports Warden's data shapes and nothing else from the stack,
and it cannot measure or write: no ast, subprocess, or file opening."""

import ast
from pathlib import Path

import judge

_FORBIDDEN = {"burnish", "drafter", "ghost_buster", "swizzle", "assay", "ast", "subprocess", "shutil", "os"}
_WRITERS = {"write_text", "write_bytes", "open", "unlink", "mkdir", "rename", "replace", "remove"}


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def test_no_module_imports_another_role_or_measures_anything():
    root = Path(judge.__file__).parent
    offenders = {str(p.relative_to(root)): sorted(_imports(p) & _FORBIDDEN)
                 for p in root.rglob("*.py") if _imports(p) & _FORBIDDEN}
    assert offenders == {}


def test_warden_is_the_only_stack_import():
    root = Path(judge.__file__).parent
    stack = {"warden", "judge"}
    for p in root.rglob("*.py"):
        assert {n for n in _imports(p) if n in {"warden", "burnish", "drafter"}} <= stack


def test_nothing_in_the_judge_can_write_a_file():
    root = Path(judge.__file__).parent
    for p in root.rglob("*.py"):
        calls = {getattr(n.func, "attr", getattr(n.func, "id", "")) for n in ast.walk(_tree(p)) if isinstance(n, ast.Call)}
        assert not (calls & _WRITERS), f"{p.name} calls {calls & _WRITERS}"
