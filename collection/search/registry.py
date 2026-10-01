from django.conf import settings

from collection.search.base import SearchError, SearchProvider
from collection.search.brave import BraveProvider
from collection.search.serper import SerperProvider

PROVIDERS = {"serper": SerperProvider, "brave": BraveProvider}


def get_provider(name: str | None = None, *, client=None, max_calls=None) -> SearchProvider:
    """Provedor escolhido em `SEARCH_PROVIDER` (`serper` | `brave`) com a chave do `.env`."""
    name = (name or settings.SEARCH_PROVIDER or "").lower()
    cls = PROVIDERS.get(name)
    if cls is None:
        raise SearchError(f"Provedor de busca desconhecido: {name!r} (use {', '.join(PROVIDERS)}).")
    key = {"serper": settings.SERPER_API_KEY, "brave": settings.BRAVE_API_KEY}[name]
    return cls(key, client=client, max_calls=max_calls)
