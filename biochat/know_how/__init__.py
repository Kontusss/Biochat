"""Deprecated compatibility adapter for the know-how layer.

The know-how implementation now lives in :mod:`biochat.knowledge`
(registry / sources / loaders).  This package exists only so legacy
imports such as ``from biochat.know_how import KnowHowLoader`` keep working.
"""

from biochat.know_how.loader import KnowHowLoader

__all__ = ["KnowHowLoader"]
