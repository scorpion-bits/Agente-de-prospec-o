"""Registro de conectores. Fonte nova = uma classe + uma linha `Source` (connectors.md)."""

from __future__ import annotations

import importlib

_BY_SLUG: dict[str, type] = {}
_BY_KIND: dict[str, type] = {}

# Tipos que não acessam a rede: não precisam de `robots_ok` nem de fetcher.
OFFLINE_KINDS = {"seed_csv"}


class NoConnector(LookupError):
    """Nenhum conector registrado para a fonte."""


def register(*, slug: str | None = None, kind: str | None = None):
    """Decorador. `slug`: conector específico de uma fonte; `kind`: genérico para o tipo."""
    if bool(slug) == bool(kind):
        raise ValueError("Informe slug ou kind (um dos dois).")

    def decorator(cls):
        if slug:
            _BY_SLUG[slug] = cls
            cls.slug = slug
        else:
            _BY_KIND[kind] = cls
        return cls

    return decorator


def load_connectors():
    importlib.import_module("collection.connectors")


def for_source(source):
    """Instância do conector da fonte: o do `slug` se houver; senão o genérico do `kind`."""
    load_connectors()
    cls = _BY_SLUG.get(source.slug) or _BY_KIND.get(source.kind)
    if cls is None:
        raise NoConnector(f"Sem conector para a fonte {source.slug!r} (tipo {source.kind!r}).")
    return cls(source)


def needs_network(source) -> bool:
    """`dataset` lido de arquivo local (`config.path` sem `config.url`) também não usa a rede."""
    if source.kind in OFFLINE_KINDS:
        return False
    config = source.config or {}
    return not (source.kind == "dataset" and config.get("path") and not config.get("url"))
