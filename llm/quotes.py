"""Campos com citação (ADR-004): `{value | "unknown", quote}` e verificação contra o texto-fonte.

Uma citação só vale se existir no texto original (comparação sem acento, caixa ou espaços extras).
Valor sem citação confirmada vira **inferência** (``verified=False``) para quem grava a evidência.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from pydantic import BaseModel

UNKNOWN = "unknown"


class Quoted(BaseModel):
    """Um valor extraído e o trecho do texto que o sustenta."""

    value: Any = UNKNOWN
    quote: str = ""
    verified: bool = False  # preenchido por `verify_quotes`; ignorado se vier do modelo


def normalize_for_match(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", stripped).casefold().strip()


def is_unknown(field: Quoted) -> bool:
    return field.value in (None, "", UNKNOWN)


def verify_quotes(model: BaseModel, source_text: str) -> list[str]:
    """Marca ``verified`` em cada ``Quoted`` achado e devolve os caminhos dos **não** verificados.

    Valor ``unknown`` não conta como falha (o modelo disse que não sabe).
    """
    haystack = normalize_for_match(source_text)
    failed: list[str] = []

    def visit(node: Any, path: str) -> None:
        if isinstance(node, Quoted):
            needle = normalize_for_match(node.quote)
            node.verified = bool(needle) and needle in haystack and not is_unknown(node)
            if not node.verified and not is_unknown(node):
                failed.append(path)
        elif isinstance(node, BaseModel):
            for name in type(node).model_fields:
                visit(getattr(node, name), f"{path}.{name}" if path else name)
        elif isinstance(node, list | tuple):
            for index, item in enumerate(node):
                visit(item, f"{path}[{index}]")

    visit(model, "")
    return failed
