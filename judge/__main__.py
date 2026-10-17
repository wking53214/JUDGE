"""``python -m judge`` runs the same command line as the ``judge`` script."""

from .cli import main

raise SystemExit(main())
