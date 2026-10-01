"""Elegibilidade da empresa × requisitos extraídos da oportunidade (ADR-013, ADR-015).

Compara os requisitos com o `CompanyProfile` (a Scorpion Bits é MEI). Devolve:
- um **gate** quando um requisito explícito não é atendido (natureza jurídica, idade mínima);
- **alertas** + ajustes de Chance quando o requisito é ambíguo, o CNAE não consta, o valor passa do
  limite do MEI ou o serviço do fit exigiria ME (ADR-015) — nunca gate;
- **bônus** de Chance para cota exclusiva ME/EPP/MEI.

Função pura: não toca no banco. Requisito desconhecido nunca barra (ADR-004).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from django.utils import timezone

from core.models import CompanyProfile, LegalForm, Opportunity, ServiceOffering
from scoring.factors import brl

MEI_REVENUE_CAP_BRL = 81_000  # usado só se o perfil não informa `annual_revenue_cap_brl`
SMALL_BUSINESS_FORMS = {LegalForm.MEI, LegalForm.ME, LegalForm.EPP}

BONUS_EXCLUSIVE = 0.2
PENALTY_AMBIGUOUS = -0.1
PENALTY_CNAE = -0.15
PENALTY_REVENUE = -0.15
PENALTY_NOT_COVERED = -0.2
PENALTY_VERIFY = -0.05
PENALTY_NO_PROFILE = -0.05


@dataclass
class Eligibility:
    gate: str | None = None
    alerts: list[str] = field(default_factory=list)
    adjustments: list[tuple[float, str]] = field(default_factory=list)  # (delta de Chance, motivo)

    def adjust(self, delta: float, reason: str, *, alert: bool = True) -> None:
        self.adjustments.append((delta, reason))
        if alert and delta < 0:
            self.alerts.append(reason)


def _digits(code: str) -> str:
    return re.sub(r"\D", "", code or "")


def company_cnaes(company: CompanyProfile) -> set[str]:
    codes = {_digits(company.primary_cnae)}
    for item in company.cnaes or []:
        codes.add(_digits(item.get("code", "") if isinstance(item, dict) else str(item)))
    return {c for c in codes if c}


def months_between(start: date, end: date) -> int:
    months = (end.year - start.year) * 12 + (end.month - start.month)
    return months - (1 if end.day < start.day else 0)


def _form_label(form: str) -> str:
    return dict(LegalForm.choices).get(form, form)


def check_eligibility(
    opp: Opportunity,
    company: CompanyProfile | None,
    service: ServiceOffering | None,
    today: date,
) -> Eligibility:
    result = Eligibility()
    if company is None:
        result.adjust(
            PENALTY_NO_PROFILE,
            "perfil da empresa não carregado (rode `make memory`): elegibilidade não conferida",
        )
        return result

    form = company.legal_form
    accepted = list(opp.eligible_legal_forms or [])
    if accepted and form not in accepted:
        names = ", ".join(_form_label(f) for f in accepted)
        result.gate = (
            f"bloqueado por requisito da empresa: aceita só {names}; somos {_form_label(form)}"
        )
    elif opp.requires_legal_entity == Opportunity.LegalEntityRequirement.YES and not accepted:
        result.adjust(
            PENALTY_AMBIGUOUS,
            "exige pessoa jurídica sem dizer quais naturezas aceita: confirmar se aceita MEI",
        )

    reference = today
    if opp.deadline_at is not None:
        reference = timezone.localtime(opp.deadline_at).date()
    if opp.min_company_age_months:
        if company.opened_at is None:
            result.adjust(
                PENALTY_AMBIGUOUS,
                "exige tempo mínimo de empresa e a data de abertura não está no perfil",
            )
        else:
            age = months_between(company.opened_at, reference)
            if age < opp.min_company_age_months and result.gate is None:
                result.gate = (
                    f"bloqueado por requisito da empresa: exige {opp.min_company_age_months} meses "
                    f"de empresa; teremos {max(age, 0)} na data do prazo ({reference:%d/%m/%Y})"
                )

    required = {_digits(c) for c in opp.required_cnaes or [] if _digits(c)}
    if required:
        mine = company_cnaes(company)
        if not any(m.startswith(r) or r.startswith(m) for m in mine for r in required):
            result.adjust(
                PENALTY_CNAE,
                f"exige CNAE {', '.join(sorted(required))} que não consta no perfil: "
                "exigiria incluir o CNAE",
            )

    if opp.exclusive_small_business is True and form in SMALL_BUSINESS_FORMS:
        result.adjust(BONUS_EXCLUSIVE, "cota exclusiva ME/EPP/MEI: somos elegíveis")

    cap = company.annual_revenue_cap_brl
    if cap is None and form == LegalForm.MEI:
        cap = MEI_REVENUE_CAP_BRL
    if cap is not None and opp.prize_amount_brl is not None and opp.prize_amount_brl > cap:
        result.adjust(
            PENALTY_REVENUE,
            f"valor de {brl(opp.prize_amount_brl)} passa do limite anual de {brl(cap)}: "
            "exigiria migrar para ME",
        )

    if service is not None and form == LegalForm.MEI:
        if service.mei_coverage == ServiceOffering.MeiCoverage.NOT_COVERED:
            result.adjust(
                PENALTY_NOT_COVERED,
                f"o serviço «{service.name}» exigiria ME (fora das atividades do MEI)",
            )
        elif service.mei_coverage == ServiceOffering.MeiCoverage.VERIFY:
            result.adjust(
                PENALTY_VERIFY, f"confirmar com o contador se o MEI cobre «{service.name}»"
            )
    return result
