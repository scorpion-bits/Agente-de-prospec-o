"""Provedores de busca web (E18): `SearchProvider` com cache permanente e teto de chamadas."""

from collection.search.base import (
    SearchBudgetExceeded,
    SearchError,
    SearchProvider,
    SearchResult,
)
from collection.search.registry import get_provider

__all__ = [
    "SearchBudgetExceeded",
    "SearchError",
    "SearchProvider",
    "SearchResult",
    "get_provider",
]
