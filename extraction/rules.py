"""Regras sem IA para editais (E11, ADR-003): datas, R$, MEI, ME/EPP, idade do CNPJ e CNAE.

Servem a três usos: (1) confirmar o que o modelo disse (data que não aparece no texto não passa),
(2) extrair sozinhas quando nenhum modelo está disponível, (3) nunca chutar: na dúvida devolvem
nada. Cada achado traz o trecho literal do texto (`quote`), para virar evidência (ADR-004).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

MONTHS = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}  # fmt: skip
NUMBER_WORDS = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "três": 3, "quatro": 4, "cinco": 5,
    "seis": 6, "doze": 12, "dezoito": 18, "vinte e quatro": 24,
}  # fmt: skip

NUMERIC_DATE = re.compile(r"\b(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})\b")
WRITTEN_DATE = re.compile(
    r"\b(\d{1,2})(?:º|°|o)?\s+de\s+(" + "|".join(MONTHS) + r")(?:\s+de\s+|\s*,?\s+)(\d{4})\b",
    re.IGNORECASE,
)
DEADLINE_CONTEXT = re.compile(
    r"(inscri[cç][õo]es?|prazo|encerr\w+|at[ée] (?:o dia|dia)?|limite|submiss[ãa]o|envio)",
    re.IGNORECASE,
)
MONEY = re.compile(r"R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?|\d+(?:,\d{1,2})?)")
PRIZE_CONTEXT = re.compile(r"(pr[êe]mi\w+|valor|total|investimento|bolsa|cach[êe])", re.IGNORECASE)
CNAE = re.compile(r"\b\d{4}-\d/\d{2}\b")
AGE = re.compile(
    r"(?:h[áa]|com|de)\s+(?:mais de|pelo menos|no m[íi]nimo|m[íi]nimo de)\s+"
    r"(\d{1,2}|[a-zçã ]{2,14}?)\s*(\(\w+\)\s*)?(anos?|meses|m[êe]s)",
    re.IGNORECASE,
)
AGE_CONTEXT = re.compile(r"(cnpj|empresa|constitu\w+|atividade|exist[êe]ncia|inscri\w+ no)", re.I)
MEI_WORD = re.compile(r"\b(MEI|microempreendedor(?:es)? individua(?:l|is))\b", re.IGNORECASE)
EXCLUDES = re.compile(
    r"(vedad\w+|n[ãa]o (?:poder[ãa]o|podem|ser[ãa]o aceit\w+)|exceto|exclu\w+)", re.I
)
ACCEPTS = re.compile(r"(poder[ãa]o participar|podem participar|aceit\w+|admitid\w+|aberto)", re.I)
SMALL_EXCLUSIVE = re.compile(
    r"exclusiv\w+\s+(?:de|para|a)\s+(?:participa[çc][ãa]o de\s+)?"
    r"(?:microempresas?|ME\b|EPP|empresas de pequeno porte|ME/EPP|MEI)",
    re.IGNORECASE,
)
SENTENCE_BREAK = re.compile(r"(?<=[.;!?])\s+")


@dataclass(frozen=True)
class Found:
    value: object
    quote: str


def _squash(text: str) -> str:
    return " ".join(text.split())


def _snippet(text: str, start: int, end: int, radius: int = 70) -> str:
    return _squash(text[max(0, start - radius) : end + radius])


def _make_date(day: int, month: int, year: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def find_dates(text: str) -> list[tuple[date, int, int]]:
    """Todas as datas completas do texto (dd/mm/aaaa e «30 de setembro de 2026») com a posição."""
    found: list[tuple[date, int, int]] = []
    for match in NUMERIC_DATE.finditer(text):
        day = _make_date(int(match[1]), int(match[2]), int(match[3]))
        if day:
            found.append((day, match.start(), match.end()))
    for match in WRITTEN_DATE.finditer(text):
        day = _make_date(int(match[1]), MONTHS[match[2].lower()], int(match[3]))
        if day:
            found.append((day, match.start(), match.end()))
    return sorted(found, key=lambda item: item[1])


def date_in_text(day: date, text: str) -> bool:
    """A data aparece no texto, escrita de um dos jeitos reconhecidos?"""
    return any(found == day for found, _s, _e in find_dates(text))


def deadline(text: str) -> Found | None:
    """Prazo só quando UMA data distinta aparece junto de «inscrições/prazo/até…»; senão nada."""
    candidates = {}
    for day, start, end in find_dates(text):
        if DEADLINE_CONTEXT.search(text[max(0, start - 60) : start]):
            candidates.setdefault(day, _snippet(text, start, end, 50))
    if len(candidates) != 1:
        return None
    ((day, quote),) = candidates.items()
    return Found(day, quote)


def parse_brl(raw: str) -> Decimal | None:
    try:
        return Decimal(raw.replace(".", "").replace(",", "."))
    except InvalidOperation:
        return None


def prize(text: str) -> Found | None:
    """Maior valor em R$ que aparece junto de «prêmio/valor/total…». Texto = o próprio trecho."""
    best: tuple[Decimal, str] | None = None
    for match in MONEY.finditer(text):
        amount = parse_brl(match[1])
        near = text[max(0, match.start() - 60) : match.start()]
        if amount and amount > 0 and PRIZE_CONTEXT.search(near):
            if best is None or amount > best[0]:
                best = (amount, _snippet(text, match.start(), match.end(), 40))
    return Found(best[0], best[1]) if best else None


def cnaes(text: str) -> Found | None:
    codes = list(dict.fromkeys(CNAE.findall(text)))
    if not codes:
        return None
    match = CNAE.search(text)
    return Found(codes, _snippet(text, match.start(), match.end(), 40))


def company_age_months(text: str) -> Found | None:
    for match in AGE.finditer(text):
        context = text[max(0, match.start() - 90) : match.end() + 90]
        if not AGE_CONTEXT.search(context):
            continue
        raw = match[1].strip().lower()
        number = int(raw) if raw.isdigit() else NUMBER_WORDS.get(raw)
        if number is None:
            continue
        months = number * 12 if match[3].lower().startswith("ano") else number
        return Found(months, _snippet(text, match.start(), match.end(), 50))
    return None


def exclusive_small_business(text: str) -> Found | None:
    match = SMALL_EXCLUSIVE.search(text)
    return Found("yes", _snippet(text, match.start(), match.end(), 40)) if match else None


def mei_acceptance(text: str) -> Found | None:
    """«yes»/«no» só se uma frase fala de MEI e traz verbo claro de aceitação ou exclusão."""
    for sentence in SENTENCE_BREAK.split(text):
        if not MEI_WORD.search(sentence) or len(sentence) > 400:
            continue
        if EXCLUDES.search(sentence) and not ACCEPTS.search(sentence):
            return Found("no", _squash(sentence))
        if ACCEPTS.search(sentence) and not EXCLUDES.search(sentence):
            return Found("yes", _squash(sentence))
    return None


def mentions_company_requirements(text: str) -> bool:
    """Há alguma pista de requisito de empresa no texto? (decide se vale mandar ao modelo)."""
    return bool(
        MEI_WORD.search(text)
        or CNAE.search(text)
        or SMALL_EXCLUSIVE.search(text)
        or AGE.search(text)
    )
