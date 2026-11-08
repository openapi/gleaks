"""Connectors. Only connectors reviewed and shipped with GLeaks are registered."""

from .base import ExposureProvider
from .hibp import HibpProvider

PROVIDERS: dict[str, ExposureProvider] = {HibpProvider.info.id: HibpProvider()}
