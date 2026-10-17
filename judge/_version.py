"""The installed version of this package. The single source of truth is ``version`` in pyproject.toml."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("judge")
except PackageNotFoundError:  # run from a source tree that was never installed
    __version__ = "0+unknown"
