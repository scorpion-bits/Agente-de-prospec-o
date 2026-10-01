"""Normalização determinística de identificadores, contatos e nomes (sem rede, sem IA).

Funções puras. Os modelos as usam para que a **unicidade valha sobre o dado normalizado**
(ex.: "Contato@Escola.org " e "contato@escola.org" são o mesmo contato), e a lista de opt-out
(`Suppression`) as usa para comparar valores.
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit

# --- CNPJ ----------------------------------------------------------------------------------
# Desde jul/2026 a Receita emite CNPJ alfanumérico: 12 posições de letras/dígitos + 2 dígitos
# verificadores numéricos. O cálculo é o mesmo do CNPJ numérico (módulo 11), com cada caractere
# valendo `ord(c) - 48` (dígitos 0–9; letras A–Z = 17–42).
_CNPJ_SHAPE = re.compile(r"[0-9A-Z]{12}[0-9]{2}")
_CNPJ_WEIGHTS_12 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_CNPJ_WEIGHTS_13 = (6, *_CNPJ_WEIGHTS_12)


def normalize_cnpj(value: str | None) -> str:
    """Só letras e dígitos, em maiúsculas (descarta a máscara de pontos, barra e hífen)."""
    return re.sub(r"[^0-9A-Za-z]", "", value or "").upper()


def _cnpj_check_digit(chars: str, weights: tuple[int, ...]) -> str:
    total = sum((ord(c) - 48) * w for c, w in zip(chars, weights, strict=True))
    rest = total % 11
    return str(0 if rest < 2 else 11 - rest)


def is_valid_cnpj(value: str | None) -> bool:
    cnpj = normalize_cnpj(value)
    if not _CNPJ_SHAPE.fullmatch(cnpj) or len(set(cnpj)) == 1:
        return False
    return cnpj[12] == _cnpj_check_digit(cnpj[:12], _CNPJ_WEIGHTS_12) and cnpj[
        13
    ] == _cnpj_check_digit(cnpj[:13], _CNPJ_WEIGHTS_13)


# --- Contatos ------------------------------------------------------------------------------
def normalize_email(value: str | None) -> str:
    return (value or "").strip().removeprefix("mailto:").strip().lower()


def normalize_phone(value: str | None) -> str:
    """Telefone brasileiro em E.164 (`+55DDNNNNNNNNN`) quando reconhecível; senão, só os dígitos.

    Números com DDD têm 10 (fixo) ou 11 (celular) dígitos e não começam por 0; `0800` e afins
    ficam só com os dígitos, para não ganhar um `+55` indevido.
    """
    digits = re.sub(r"\D", "", value or "")
    if len(digits) in (12, 13) and digits.startswith("55"):
        return f"+{digits}"
    if len(digits) in (10, 11) and not digits.startswith("0"):
        return f"+55{digits}"
    return digits


def normalize_domain(value: str | None) -> str:
    """Domínio sem esquema, caminho, porta e `www.` (aceita URL, e-mail ou domínio)."""
    text = (value or "").strip().lower()
    if "@" in text:
        text = text.rsplit("@", 1)[1]
    if "//" not in text:
        text = "//" + text
    try:
        host = urlsplit(text).hostname or ""
    except ValueError:
        return ""
    return host.removeprefix("www.").strip(".")


def normalize_contact_value(kind: str, value: str | None) -> str:
    """Valor de `ContactPoint` normalizado conforme o tipo (base do dedupe do contato)."""
    if kind == "email":
        return normalize_email(value)
    if kind in ("phone", "whatsapp"):
        return normalize_phone(value)
    return (value or "").strip()


# --- Nomes ---------------------------------------------------------------------------------
def name_key(value: str | None) -> str:
    """Nome comparável: sem acentos, minúsculo, só letras/dígitos separados por um espaço."""
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.casefold()).split())


def normalize_suppression_value(kind: str, value: str | None) -> str:
    """Valor de `Suppression` normalizado conforme o tipo.

    Para `organization`, um CNPJ válido vale pelo CNPJ; qualquer outro texto, pelo nome comparável.
    """
    if kind == "email":
        return normalize_email(value)
    if kind == "phone":
        return normalize_phone(value)
    if kind == "domain":
        return normalize_domain(value)
    if kind == "organization":
        cnpj = normalize_cnpj(value)
        return cnpj if is_valid_cnpj(cnpj) else name_key(value)
    raise ValueError(f"Tipo de supressão desconhecido: {kind!r}")
