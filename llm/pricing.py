"""Tabela de preços (US$ por 1M de tokens) e cálculo de custo.

Levantamento de 30/09/2026 (docs/research/ai-models-and-costs.md): **revalidar antes de ativar
provedor pago**. Modelo pago que não está aqui não é chamado (sem preço não há teto).
Free tier custa 0 por definição; o teto mensal só vigia ``credits`` e ``money``.
"""

from __future__ import annotations

from decimal import Decimal

from llm.types import PricingError

PRICES_REVIEWED = "2026-09-30"

# (provedor, modelo) -> (entrada, saída) por 1M de tokens
PRICES: dict[tuple[str, str], tuple[Decimal, Decimal]] = {
    ("anthropic", "claude-haiku-4-5"): (Decimal("1.00"), Decimal("5.00")),
    ("anthropic", "claude-sonnet-5-5"): (Decimal("2.00"), Decimal("10.00")),
    ("anthropic", "claude-opus-5-5"): (Decimal("4.00"), Decimal("20.00")),
    # Gemini pago: Flash/Flash-Lite de referência 2.5 (conferir em ai.google.dev/pricing).
    ("gemini-paid", "gemini-2.5-flash-lite"): (Decimal("0.10"), Decimal("0.40")),
    ("gemini-paid", "gemini-2.5-flash"): (Decimal("0.30"), Decimal("2.50")),
    ("gemini-paid", "gemini-3.1-pro"): (Decimal("2.00"), Decimal("12.00")),
}

ONE_MILLION = Decimal(1_000_000)


def cost_usd(provider: str, model: str, billing: str, input_tokens: int, output_tokens: int):
    """Custo em US$. ``billing="free"`` é sempre 0; pago sem preço levanta ``PricingError``."""
    if billing == "free":
        return Decimal("0")
    try:
        price_in, price_out = PRICES[(provider, model)]
    except KeyError:
        raise PricingError(f"sem preço para {provider}:{model} em llm/pricing.py") from None
    return (price_in * input_tokens + price_out * output_tokens) / ONE_MILLION
