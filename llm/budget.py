"""Orçamento (llm-strategy.md, item 6): teto mensal e por execução. Free tier nunca é bloqueado.

- ``money``: dinheiro novo (Anthropic), teto ``LLM_MONTHLY_BUDGET_USD`` (padrão US$ 5).
- ``credits``: créditos do Google AI Pro (Gemini pago), à parte (``LLM_CREDITS_MONTHLY_USD``).
- por execução: ``LLM_RUN_BUDGET_USD`` somando os dois (cada ``AIService`` é uma execução).

A checagem usa uma **estimativa** pessimista antes da chamada; o custo real entra no log depois.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from llm.models import LLMCall
from llm.types import BudgetExceeded

CHARS_PER_TOKEN = 3  # pessimista para português
PDF_BYTES_PER_TOKEN = 4


def month_start():
    now = timezone.localtime()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def monthly_cap(billing: str) -> Decimal | None:
    if billing == "money":
        return Decimal(str(settings.LLM_MONTHLY_BUDGET_USD))
    if billing == "credits":
        return Decimal(str(settings.LLM_CREDITS_MONTHLY_USD))
    return None  # free: sem teto


def month_spent(billing: str) -> Decimal:
    total = LLMCall.objects.filter(billing=billing, created_at__gte=month_start()).aggregate(
        total=Sum("cost_usd")
    )["total"]
    return total or Decimal("0")


def estimate_input_tokens(prompt: str, system: str, pdf_bytes: bytes | None) -> int:
    tokens = (len(prompt) + len(system)) // CHARS_PER_TOKEN + 1
    if pdf_bytes:
        tokens += len(pdf_bytes) // PDF_BYTES_PER_TOKEN
    return tokens


def check(billing: str, estimated_usd: Decimal, run_spent: Decimal) -> None:
    """Levanta ``BudgetExceeded`` se a chamada estimada passa de algum teto. Free passa sempre."""
    cap = monthly_cap(billing)
    if cap is None:
        return
    if month_spent(billing) + estimated_usd > cap:
        raise BudgetExceeded(f"teto mensal ({billing}) de US$ {cap} atingido")
    run_cap = Decimal(str(settings.LLM_RUN_BUDGET_USD))
    if run_spent + estimated_usd > run_cap:
        raise BudgetExceeded(f"teto da execução de US$ {run_cap} atingido")
