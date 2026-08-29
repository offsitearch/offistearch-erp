"""Logging setup (kernel k0).

Simple module-level config on first use; each module uses
``logging.getLogger(__name__)``. Kept tiny and dependency-light.
"""

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
