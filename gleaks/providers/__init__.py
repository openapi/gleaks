"""Connectors. Only connectors reviewed and shipped with GLeaks are registered."""

from .base import ExposureProvider
from .hibp import HibpProvider
from .profiles import ProfileIndexProvider
from .web import WebSearchProvider

PROVIDERS: dict[str, ExposureProvider] = {
    provider.info.id: provider for provider in (ProfileIndexProvider(), WebSearchProvider(), HibpProvider())
}
