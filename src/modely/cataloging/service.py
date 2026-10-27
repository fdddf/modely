"""Catalog use-case services."""

from __future__ import annotations

from dataclasses import dataclass

from .catalog import diff_catalogs, scan_catalog
from ..types import CatalogReport


@dataclass
class CatalogService:
    """Thin service wrapper for catalog operations shared by CLI and future server routes."""

    def scan(self, root: str | None = None, **kwargs) -> CatalogReport:
        return scan_catalog(root, **kwargs)

    def diff(self, left: CatalogReport, right: CatalogReport) -> dict:
        return diff_catalogs(left, right)


__all__ = ["CatalogService"]
