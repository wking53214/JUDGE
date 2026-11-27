"""Read one file as it was in the project's last commit, without running git (0.13.0, was KNOWN DEFECTS 2).

Why: a deleted file is gone from the project folder by the time the Judge looks, so the tests it held cannot be read
there. Warden refuses to start on a git folder with uncommitted changes, so for a git project the file as it was before
the run is the one in the commit HEAD names. This module reads that copy straight from the `.git` folder with the
standard library (zlib for the compression, hashlib to check every object against its id).

What it reads: HEAD (a branch name or a commit id), the branch from its own file or from `packed-refs`, then the
commit, its tree, the folders down to the file, and the file. Objects are read loose or from pack files with an
index of version 2, including both kinds of delta. A `.git` file that points elsewhere (a linked worktree or a
submodule) and a `commondir` file are followed.

What it does not read, and so reports as unreadable (never as "no tests"): a SHA-256 repository, objects kept only
in an alternate store or fetched later (a partial clone), an index other than version 2, a file that is a link, a
submodule entry, an object or pack larger than the limits below. `git replace` refs are ignored, as Warden ignores
them. Anyone who can write the `.git` folder can change what is read here, as anyone who can write the project folder
can change what the Judge reads elsewhere.

It never writes anything and never runs a program.
"""

from __future__ import annotations

import hashlib
import zlib
from pathlib import Path

#: A file larger than this is not returned; the caller holds it as unreadable.
BLOB_LIMIT = 4 * 1024 * 1024
#: A pack file is read whole (the Judge calls nothing that opens a file for streaming), so a larger one is not read.
_PACK_LIMIT = 256 * 1024 * 1024
#: Any other object (commit, tree, a delta's base) larger than this is not read.
_OBJECT_LIMIT = 64 * 1024 * 1024
#: Git's own default chain is 50; anything far past it is not a real repository.
_DELTA_DEPTH = 1000
_REF_DEPTH = 10
_TYPES = {1: b"commit", 2: b"tree", 3: b"blob", 4: b"tag"}
_HEX = frozenset("0123456789abcdef")


class Unreadable(Exception):
    """The file's committed copy could not be read; the reason is a plain sentence."""


class NotGit(Unreadable):
    """The project folder is not inside a git work tree."""


class NotCommitted(Unreadable):
    """The last commit has no file at that path."""


def committed_bytes(project: Path, rel: str) -> bytes:
    """The bytes of `rel` (a path inside `project`, with `/` between folders) in the commit HEAD names.

    Raises NotGit, NotCommitted or Unreadable; returns only a real file's bytes.
    """
    project = project.resolve()
    top, gitdir = _find_git(project)
    common = _common_dir(gitdir)
    _refuse_sha256(common)
    store = _Store(common)
    commit = _resolve_head(gitdir, common)
    kind, body = store.read(commit)
    if kind != b"commit":
        raise Unreadable("HEAD does not name a commit")
    tree = _tree_of(body)
    inside = project.relative_to(top).parts
    parts = [*inside, *(p for p in rel.split("/") if p not in ("", "."))]
    if not parts or any(p == ".." for p in parts):
        raise Unreadable("the path does not name a file inside the project")
    for i, name in enumerate(parts):
        kind, body = store.read(tree)
        if kind != b"tree":
            raise Unreadable("a folder in the last commit is not a tree")
        entry = _entry(body, name.encode("utf-8", "surrogateescape"))
        if entry is None:
            raise NotCommitted("the last commit has no file at that path")
        mode, oid = entry
        last = i == len(parts) - 1
        if not last:
            if mode != b"40000":
                raise NotCommitted("the last commit has no folder at that path")
            tree = oid
            continue
        if mode not in (b"100644", b"100755"):
            raise Unreadable("in the last commit that path is a link, a folder or a submodule, not a file")
        kind, body = store.read(oid, limit=BLOB_LIMIT)
        if kind != b"blob":
            raise Unreadable("the last commit's entry for that path is not a file")
        return body
    raise Unreadable("the path does not name a file inside the project")  # pragma: no cover


# ---- finding the repository -----------------------------------------------------------------------------------------

def _find_git(project: Path) -> tuple[Path, Path]:
    for folder in (project, *project.parents):
        dot = folder / ".git"
        try:
            if dot.is_dir():
                return folder, dot
            if dot.is_file():
                text = _text(dot)
                if not text.startswith("gitdir:"):
                    raise Unreadable("the .git file does not say where the repository is")
                return folder, (folder / text[len("gitdir:"):].strip()).resolve()
        except OSError as exc:
            raise Unreadable("the .git folder could not be read") from exc
    raise NotGit("the project folder is not inside a git work tree")


def _common_dir(gitdir: Path) -> Path:
    f = gitdir / "commondir"
    try:
        if f.is_file():
            return (gitdir / _text(f).strip()).resolve()
    except OSError as exc:
        raise Unreadable("the repository's commondir file could not be read") from exc
    return gitdir


def _refuse_sha256(common: Path) -> None:
    try:
        config = _text(common / "config") if (common / "config").is_file() else ""
    except OSError as exc:
        raise Unreadable("the repository's config could not be read") from exc
    for line in config.splitlines():
        key, _, value = line.partition("=")
        if key.strip().lower() == "objectformat" and value.strip().lower() != "sha1":
            raise Unreadable("the repository does not use SHA-1 ids, which this reader does not read")


def _text(path: Path) -> str:
    return path.read_bytes()[:65536].decode("utf-8", "replace")


def _hex_id(s: str) -> bytes | None:
    s = s.strip().lower()
    return bytes.fromhex(s) if len(s) == 40 and set(s) <= _HEX else None


def _resolve_head(gitdir: Path, common: Path) -> bytes:
    name = "HEAD"
    for _ in range(_REF_DEPTH):
        value = _ref_value(gitdir, common, name)
        if value.startswith("ref:"):
            name = value[4:].strip()
            if not name.startswith("refs/") or ".." in name.split("/"):
                raise Unreadable("HEAD names something that is not a branch")
            continue
        oid = _hex_id(value)
        if oid is None:
            raise Unreadable("HEAD does not name a commit id")
        return oid
    raise Unreadable("HEAD points through too many names")


def _ref_value(gitdir: Path, common: Path, name: str) -> str:
    try:
        for base in ((gitdir,) if name == "HEAD" else (gitdir, common)):
            f = base / name
            if f.is_file():
                return _text(f).strip()
        packed = common / "packed-refs"
        if packed.is_file():
            for line in packed.read_bytes().decode("utf-8", "replace").splitlines():
                oid, _, ref = line.partition(" ")
                if ref.strip() == name and _hex_id(oid) is not None:
                    return oid
    except OSError as exc:
        raise Unreadable("a branch file could not be read") from exc
    raise Unreadable("HEAD names a branch that has no commit yet")


# ---- commits and trees ----------------------------------------------------------------------------------------------

def _tree_of(commit: bytes) -> bytes:
    first = commit.split(b"\n", 1)[0]
    if first.startswith(b"tree "):
        oid = _hex_id(first[5:].decode("ascii", "replace"))
        if oid is not None:
            return oid
    raise Unreadable("the commit does not name its tree")


def _entry(tree: bytes, name: bytes) -> tuple[bytes, bytes] | None:
    i = 0
    while i < len(tree):
        sp = tree.find(b" ", i)
        nul = tree.find(b"\0", sp + 1)
        if sp < 0 or nul < 0 or nul + 21 > len(tree):
            raise Unreadable("a tree in the last commit is damaged")
        if tree[sp + 1:nul] == name:
            return tree[i:sp], tree[nul + 1:nul + 21]
        i = nul + 21
    return None


# ---- the object store -----------------------------------------------------------------------------------------------

class _Store:
    def __init__(self, common: Path):
        self.objects = common / "objects"
        self._packs: list[tuple[bytes, Path]] | None = None
        self._data: dict[Path, bytes] = {}

    def read(self, oid: bytes, limit: int = _OBJECT_LIMIT, depth: int = 0) -> tuple[bytes, bytes]:
        """(type, body) of the object, checked against its id."""
        if depth > _DELTA_DEPTH:
            raise Unreadable("a delta chain in the repository is too long")
        h = oid.hex()
        loose = self.objects / h[:2] / h[2:]
        try:
            if loose.is_file():
                kind, body = _loose(loose.read_bytes(), limit)
                return _checked(oid, kind, body)
        except OSError as exc:
            raise Unreadable("an object in the repository could not be read") from exc
        for idx, pack in self._indexes():
            offset = _find_offset(idx, oid)
            if offset is not None:
                kind, body = self._packed(pack, offset, limit, depth)
                return _checked(oid, kind, body)
        raise Unreadable("an object the last commit needs is not in the repository")

    def _indexes(self) -> list[tuple[bytes, Path]]:
        if self._packs is None:
            self._packs = []
            folder = self.objects / "pack"
            try:
                names = sorted(folder.glob("pack-*.idx")) if folder.is_dir() else []
                for idx in names:
                    pack = idx.with_suffix(".pack")
                    if pack.is_file():
                        self._packs.append((idx.read_bytes(), pack))
            except OSError as exc:
                raise Unreadable("a pack index in the repository could not be read") from exc
        return self._packs

    def _pack_bytes(self, pack: Path) -> bytes:
        if pack not in self._data:
            try:
                if pack.stat().st_size > _PACK_LIMIT:
                    raise Unreadable("a pack file in the repository is too large to read")
                self._data[pack] = pack.read_bytes()
            except OSError as exc:
                raise Unreadable("a pack file in the repository could not be read") from exc
        return self._data[pack]

    def _packed(self, pack: Path, offset: int, limit: int, depth: int) -> tuple[bytes, bytes]:
        if depth > _DELTA_DEPTH:
            raise Unreadable("a delta chain in the repository is too long")
        data = self._pack_bytes(pack)
        if offset < 12 or offset >= len(data):
            raise Unreadable("a pack index points outside its pack")
        pos = offset
        byte = data[pos]
        pos += 1
        kind = (byte >> 4) & 7
        size = byte & 15
        shift = 4
        while byte & 0x80:
            if pos >= len(data) or shift > 63:
                raise Unreadable("a pack entry is damaged")
            byte = data[pos]
            pos += 1
            size |= (byte & 0x7F) << shift
            shift += 7
        if kind in _TYPES:
            if size > limit:
                raise Unreadable("an object in the repository is too large to read")
            return _TYPES[kind], _inflate(data, pos, size)
        if kind == 6:   # the base sits earlier in this pack, at a negative distance
            if pos >= len(data):
                raise Unreadable("a pack entry is damaged")
            byte = data[pos]
            pos += 1
            dist = byte & 0x7F
            while byte & 0x80:
                if pos >= len(data):
                    raise Unreadable("a pack entry is damaged")
                byte = data[pos]
                pos += 1
                dist = ((dist + 1) << 7) | (byte & 0x7F)
            if dist <= 0 or dist > offset:
                raise Unreadable("a pack entry is damaged")
            base_kind, base = self._packed(pack, offset - dist, _OBJECT_LIMIT, depth + 1)
        elif kind == 7:  # the base is named by its id
            if pos + 20 > len(data):
                raise Unreadable("a pack entry is damaged")
            base_kind, base = self.read(data[pos:pos + 20], _OBJECT_LIMIT, depth + 1)
            pos += 20
        else:
            raise Unreadable("a pack entry has a type this reader does not know")
        if size > _OBJECT_LIMIT:
            raise Unreadable("a delta in the repository is too large to read")
        return base_kind, _apply_delta(base, _inflate(data, pos, size), limit)


def _loose(raw: bytes, limit: int) -> tuple[bytes, bytes]:
    d = zlib.decompressobj()
    try:
        out = d.decompress(raw, limit + 64)
    except zlib.error as exc:
        raise Unreadable("an object in the repository is damaged") from exc
    head, nul, body = out.partition(b"\0")
    kind, _, size = head.partition(b" ")
    if not nul or not size.isdigit():
        raise Unreadable("an object in the repository is damaged")
    if int(size) > limit:
        raise Unreadable("an object in the repository is too large to read")
    if len(body) != int(size):
        raise Unreadable("an object in the repository is damaged")
    return kind, body


def _inflate(data: bytes, pos: int, size: int) -> bytes:
    d = zlib.decompressobj()
    try:
        out = d.decompress(memoryview(data)[pos:], size + 1)
    except zlib.error as exc:
        raise Unreadable("a pack entry is damaged") from exc
    if len(out) != size:
        raise Unreadable("a pack entry is damaged")
    return out


def _apply_delta(base: bytes, delta: bytes, limit: int) -> bytes:
    pos = 0

    def varint() -> int:
        nonlocal pos
        value = shift = 0
        while True:
            if pos >= len(delta) or shift > 63:
                raise Unreadable("a delta in the repository is damaged")
            byte = delta[pos]
            pos += 1
            value |= (byte & 0x7F) << shift
            shift += 7
            if not byte & 0x80:
                return value

    if varint() != len(base):
        raise Unreadable("a delta in the repository does not match its base")
    size = varint()
    if size > limit:
        raise Unreadable("an object in the repository is too large to read")
    out = bytearray()
    while pos < len(delta):
        op = delta[pos]
        pos += 1
        if op & 0x80:
            offset = length = 0
            for bit in range(4):
                if op & (1 << bit):
                    if pos >= len(delta):
                        raise Unreadable("a delta in the repository is damaged")
                    offset |= delta[pos] << (8 * bit)
                    pos += 1
            for bit in range(3):
                if op & (1 << (4 + bit)):
                    if pos >= len(delta):
                        raise Unreadable("a delta in the repository is damaged")
                    length |= delta[pos] << (8 * bit)
                    pos += 1
            length = length or 0x10000
            if offset + length > len(base):
                raise Unreadable("a delta in the repository reaches past its base")
            out += base[offset:offset + length]
        elif op:
            if pos + op > len(delta):
                raise Unreadable("a delta in the repository is damaged")
            out += delta[pos:pos + op]
            pos += op
        else:
            raise Unreadable("a delta in the repository is damaged")
        if len(out) > size:
            raise Unreadable("a delta in the repository is damaged")
    if len(out) != size:
        raise Unreadable("a delta in the repository is damaged")
    return bytes(out)


def _find_offset(idx: bytes, oid: bytes) -> int | None:
    if len(idx) < 8 + 1024 or idx[:4] != b"\377tOc" or int.from_bytes(idx[4:8], "big") != 2:
        raise Unreadable("a pack index in the repository is not of version 2, which this reader reads")
    first = oid[0]
    lo = int.from_bytes(idx[8 + 4 * (first - 1):8 + 4 * first], "big") if first else 0
    hi = int.from_bytes(idx[8 + 4 * first:12 + 4 * first], "big")
    n = int.from_bytes(idx[8 + 1020:8 + 1024], "big")
    names = 8 + 1024
    offsets = names + 20 * n + 4 * n
    if len(idx) < offsets + 4 * n or not 0 <= lo <= hi <= n:
        raise Unreadable("a pack index in the repository is damaged")
    while lo < hi:
        mid = (lo + hi) // 2
        here = idx[names + 20 * mid:names + 20 * mid + 20]
        if here == oid:
            value = int.from_bytes(idx[offsets + 4 * mid:offsets + 4 * mid + 4], "big")
            if value & 0x80000000:
                large = offsets + 4 * n + 8 * (value & 0x7FFFFFFF)
                if len(idx) < large + 8:
                    raise Unreadable("a pack index in the repository is damaged")
                value = int.from_bytes(idx[large:large + 8], "big")
            return value
        if here < oid:
            lo = mid + 1
        else:
            hi = mid
    return None


def _checked(oid: bytes, kind: bytes, body: bytes) -> tuple[bytes, bytes]:
    if hashlib.sha1(kind + b" " + str(len(body)).encode() + b"\0" + body, usedforsecurity=False).digest() != oid:
        raise Unreadable("an object in the repository does not match its id")
    return kind, body
