from __future__ import annotations

from ..models import SourceConfig
from .base import BaseConnector
from .feed import FeedConnector
from .gazzetta_ufficiale import GazzettaUfficialeConnector
from .normattiva_collection import NormattivaCollectionConnector
from .sitemap_or_static import SitemapOrStaticConnector
from .static_urls import StaticUrlsConnector


def create_connector(source: SourceConfig) -> BaseConnector:
    if source.connector == "normattiva_collection":
        return NormattivaCollectionConnector(source)
    if source.connector == "feed":
        return FeedConnector(source)
    if source.connector == "gazzetta_ufficiale":
        return GazzettaUfficialeConnector(source)
    if source.connector == "sitemap_or_static":
        return SitemapOrStaticConnector(source)
    if source.connector == "static_urls":
        return StaticUrlsConnector(source)
    raise ValueError(f"Connector non supportato: {source.connector}")
