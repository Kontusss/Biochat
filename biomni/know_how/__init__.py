"""Deprecated compatibility adapter for the know-how layer.

The know-how implementation now lives in :mod:`biomni.knowledge`
(registry / sources / loaders).  This package exists only so legacy
imports such as ``from biomni.know_how import KnowHowLoader`` keep working.
"""

from biomni.know_how.loader import KnowHowLoader

__all__ = ["KnowHowLoader"]
