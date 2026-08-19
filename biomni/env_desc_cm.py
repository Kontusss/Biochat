"""Compatibility adapter — commercial-mode environment descriptor view.

The upstream dict literals now live in ``biomni/environment/catalog.yaml``.
The commercial view is the catalog filtered by ``commercial_allowed``
(entries annotated in the original ``env_desc_cm.py`` are excluded).
Field-level output is identical to the original module (verified by
``tests/test_environment_catalog.py``).
"""

from biomni.environment import get_environment_catalog

_catalog = get_environment_catalog()

data_lake_dict = _catalog.data_lake_dict_cm
library_content_dict = _catalog.library_content_dict_cm
