"""Compatibility adapter — full environment descriptor view.

The upstream dict literals now live in ``biomni/environment/catalog.yaml``
(see ``biomni/environment/``).  This module keeps the legacy import surface:

    from biomni.env_desc import data_lake_dict, library_content_dict

Field-level output is identical to the original module (verified by
``tests/test_environment_catalog.py``).
"""

from biomni.environment import get_environment_catalog

_catalog = get_environment_catalog()

data_lake_dict = _catalog.data_lake_dict
library_content_dict = _catalog.library_content_dict
