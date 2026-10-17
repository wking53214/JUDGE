"""Judge: the third party that decides whether a run of the loop is acceptable."""

import logging

from ._version import __version__
from .seat import Judge

# A library installs no handlers of its own; the application (or ``judge.cli``) decides where logs go.
logging.getLogger("judge").addHandler(logging.NullHandler())

__all__ = ["Judge", "__version__"]
