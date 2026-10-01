"""V — Valor: retorno potencial (prêmio em R$ e tipo de benefício)."""

from __future__ import annotations

from core.models import Opportunity
from scoring.factors import EvidenceIndex, FactorResult, brl, build, fmt, no_data

FIELDS = ("prize_amount_brl", "prize_text", "benefits")

# (a partir de R$, valor): faixas do prêmio/contrato.
AMOUNT_BANDS = (
    (250_000, 0.95),
    (100_000, 0.85),
    (30_000, 0.7),
    (10_000, 0.55),
    (3_000, 0.4),
    (0, 0.3),
)
# Sem valor numérico: o melhor benefício declarado.
BENEFIT_VALUE = {
    "money": 0.6,
    "contract": 0.6,
    "clients": 0.5,
    "prize": 0.5,
    "partnership": 0.45,
    "investors": 0.45,
    "acceleration": 0.4,
    "infrastructure": 0.35,
    "visibility": 0.35,
    "networking": 0.35,
    "portfolio": 0.35,
    "mentoring": 0.3,
    "certification": 0.3,
}


def value_factor(opp: Opportunity, index: EvidenceIndex) -> FactorResult:
    amount = opp.prize_amount_brl
    if amount is not None and amount > 0:
        value = next(v for floor, v in AMOUNT_BANDS if amount >= floor)
        return build("V", value, f"valor de {brl(amount)} (faixa): {fmt(value)}", index, FIELDS)
    benefits = [b for b in opp.benefits if b in BENEFIT_VALUE]
    if benefits:
        best = max(benefits, key=BENEFIT_VALUE.get)
        label = dict(Opportunity.Benefit.choices)[best]
        value = BENEFIT_VALUE[best]
        return build(
            "V", value, f"sem valor em R$; melhor benefício: {label}: {fmt(value)}", index, FIELDS
        )
    return no_data("V", "nem valor em R$ nem benefício")
