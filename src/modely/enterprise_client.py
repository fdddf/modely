"""Enterprise Python SDK client — compatibility facade.

Re-exports the enterprise client from ``modely.application.client``.
Import ``from modely.enterprise_client import Client`` continues to work.
"""

from .application.client import *  # noqa: F401,F403
