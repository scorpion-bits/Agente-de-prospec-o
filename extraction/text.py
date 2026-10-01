"""Texto de páginas para a extração (E11): HTML -> texto visível e janelas por palavra-chave.

Menos tokens antes de qualquer modelo (llm-strategy.md): página longa vira o começo + trechos ao
redor das palavras que importam (prazo, elegibilidade, valor…). Citações continuam literais,
porque as janelas são cortes do texto original, sem reescrita.
"""

from __future__ import annotations

import re

from extraction.website import html_text

KEYWORDS = re.compile(
    r"(prazo|inscri[cç]|encerr|elegib|requisit|podem participar|poder[ãa]o participar|vedad|"
    r"\bMEI\b|microempreendedor|\bME\b|\bEPP\b|CNPJ|CNAE|pessoa jur[ií]dica|pessoa f[ií]sica|"
    r"pr[êe]mi|R\$|valor|taxa|gratuit|modalidade|online|presencial|cronograma|"
    r"\d{1,2}/\d{1,2}/\d{4}|\bde (?:janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|"
    r"setembro|outubro|novembro|dezembro)\b)",
    re.IGNORECASE,
)
HEAD_CHARS = 2000
WINDOW = 350
MIN_TEXT_CHARS = 200  # menos que isso = página vazia ou só JS: não vale chamar modelo


def page_text(body: str, content_type: str = "") -> tuple[str, str]:
    """(título, texto) de uma resposta. HTML passa pelo extrator; texto puro só normaliza."""
    kind = content_type.split(";")[0].strip().lower()
    if kind in ("", "text/html", "application/xhtml+xml") or "<html" in body[:500].lower():
        return html_text(body)
    return "", " ".join(body.split())


def select_windows(text: str, limit: int) -> str:
    """Texto inteiro se cabe em `limit`; senão o começo + janelas ao redor das palavras-chave."""
    if len(text) <= limit:
        return text
    spans = [(0, min(HEAD_CHARS, limit // 4))]  # o resto do orçamento é das palavras-chave
    for match in KEYWORDS.finditer(text):
        spans.append((max(0, match.start() - WINDOW), min(len(text), match.end() + WINDOW)))
    spans.sort()
    merged: list[list[int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    pieces, used = [], 0
    for start, end in merged:
        piece = text[start:end]
        if used + len(piece) > limit:
            piece = piece[: max(0, limit - used)]
        if piece:
            pieces.append(piece)
            used += len(piece)
        if used >= limit:
            break
    return " […] ".join(pieces)
