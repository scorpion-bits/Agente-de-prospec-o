"""E11 — extração estruturada de oportunidades: schema com citação, tarefa de IA e gravação.

Fluxo (ADR-034): texto da página → janelas por palavra-chave → `AIService.run(...)` da tarefa
`extract_opportunity` (Gemini free → Claude Haiku → regras) → **conferência por regras** (data
que não está no texto não vale) → gravação. Campo crítico (datas, MEI/natureza jurídica, idade
do CNPJ, CNAE, valor) só entra na coluna se a citação for verificada; sem isso fica só como
evidência **inferida** (ADR-004). Colunas já preenchidas (por conector ou humano) nunca são
sobrescritas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.utils import timezone
from pydantic import BaseModel, Field

from core.models import LegalForm, Opportunity
from core.services.evidence import EvidenceError, quote_in_text, record_evidence
from extraction import rules
from extraction.text import select_windows
from llm.quotes import Quoted, is_unknown
from llm.router import AIService
from llm.tasks import Task, register_task
from llm.types import DataClass, LLMInput, LLMResult

TASK_NAME = "extract_opportunity"
PROMPT_VERSION = "v1"
EXTRACTION_VERSION = f"{TASK_NAME}@{PROMPT_VERSION}"
MAX_WINDOW_CHARS = 12_000
SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "extract_opportunity_v1.txt").read_text()


def _q() -> Quoted:
    return Field(default_factory=Quoted)


class OpportunityFields(BaseModel):
    """Um `Quoted {value|"unknown", quote}` por campo: sem trecho verificado, vira inferência."""

    summary: Quoted = _q()
    deadline: Quoted = _q()
    opens: Quoted = _q()
    starts: Quoted = _q()
    accepts_mei: Quoted = _q()
    legal_forms: Quoted = _q()
    requires_legal_entity: Quoted = _q()
    exclusive_small_business: Quoted = _q()
    min_company_age_months: Quoted = _q()
    required_cnaes: Quoted = _q()
    eligible_regions: Quoted = _q()
    scope: Quoted = _q()
    modality: Quoted = _q()
    prize_text: Quoted = _q()
    prize_amount_brl: Quoted = _q()
    benefits: Quoted = _q()
    participation_cost: Quoted = _q()
    effort: Quoted = _q()
    requirements: Quoted = _q()


def rules_strategy(data: LLMInput) -> dict | None:
    """Estratégia sem LLM: só o que regex acha sem ambiguidade. `None` = nada achado."""
    text = data.text
    out: dict[str, dict] = {}

    def put(name: str, found: rules.Found | None, value: Any = None) -> None:
        if found is not None:
            out[name] = {"value": found.value if value is None else value, "quote": found.quote}

    deadline = rules.deadline(text)
    put("deadline", deadline, deadline.value.isoformat() if deadline else None)
    put("accepts_mei", rules.mei_acceptance(text))
    put("exclusive_small_business", rules.exclusive_small_business(text))
    put("min_company_age_months", rules.company_age_months(text))
    put("required_cnaes", rules.cnaes(text))
    prize = rules.prize(text)
    put("prize_amount_brl", prize, str(prize.value) if prize else None)
    return out or None


def build_prompt(data: LLMInput) -> str:
    extra = data.extra
    head = f"URL: {data.url or extra.get('url', '')}\nTítulo conhecido: {extra.get('title', '')}\n"
    return head + "Texto da página:\n" + data.text


TASK = register_task(
    Task(
        name=TASK_NAME,
        schema=OpportunityFields,
        system=SYSTEM_PROMPT,
        # Free tier só recebe texto público (é o caso: páginas de edital). Claude Haiku só entra com
        # chave e preço; as regras fecham a lista para o sistema nunca ficar sem resposta.
        strategies=["gemini-free:gemini-3.1-flash-lite", "anthropic:claude-haiku-4-5", "rules"],
        prompt_version=PROMPT_VERSION,
        rules=rules_strategy,
        build_prompt=build_prompt,
        max_input_chars=MAX_WINDOW_CHARS + 600,
        max_output_tokens=1800,
    )
)


# -- conferência e conversão ---------------------------------------------------------------------
def _iso_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def _int(value: Any) -> int | None:
    try:
        number = int(str(value).strip())
    except ValueError:
        return None
    return number if number >= 0 else None


def _decimal(value: Any) -> Decimal | None:
    text = str(value).strip()
    try:
        number = Decimal(text) if "," not in text else rules.parse_brl(text)
    except ArithmeticError:
        return None
    return number if number is not None and number >= 0 else None


def _choice(value: Any, choices) -> str | None:
    text = str(value).strip().lower()
    return text if text in choices else None


def _list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [part for part in value.replace(";", ",").split(",")]
    return [str(item).strip() for item in value if str(item).strip()] if value else []


def _aware(day: date, at: time) -> datetime:
    return timezone.make_aware(datetime.combine(day, at))


def _consistent(name: str, value: Any, text: str) -> bool:
    """Confere o valor do modelo com as regras. Falhou = o campo não é confiável."""
    if name in ("deadline", "opens", "starts"):
        day = _iso_date(value)
        return day is not None and rules.date_in_text(day, text)
    if name == "min_company_age_months":
        found = rules.company_age_months(text)
        return found is not None and _int(value) == found.value
    if name == "required_cnaes":
        return bool(_list(value)) and all(code in text for code in _list(value))
    if name == "prize_amount_brl":
        amount = _decimal(value)
        found = [rules.parse_brl(m[1]) for m in rules.MONEY.finditer(text)]
        return amount is not None and amount in found
    if name == "accepts_mei":
        return bool(rules.MEI_WORD.search(text))
    return True


@dataclass
class Checked:
    """Um campo conferido: valor convertido, citação e se pode ir para a coluna."""

    name: str
    value: Any
    quote: str
    trusted: bool


@dataclass
class Extraction:
    fields: dict[str, Checked] = field(default_factory=dict)
    strategy: str = ""
    cost_usd: Decimal = Decimal("0")
    cached: bool = False
    unverified: list[str] = field(default_factory=list)


CRITICAL = {
    "deadline", "opens", "starts", "accepts_mei", "legal_forms", "requires_legal_entity",
    "exclusive_small_business", "min_company_age_months", "required_cnaes", "prize_amount_brl",
}  # fmt: skip
CHOICES = {
    "requires_legal_entity": {"yes", "no"},
    "accepts_mei": {"yes", "no"},
    "exclusive_small_business": {"yes", "no"},
    "scope": {c.value for c in Opportunity.Scope},
    "modality": {"online", "in_person", "hybrid"},
    "effort": {"low", "medium", "high"},
}


def review(result: LLMResult, text: str) -> Extraction:
    """Converte e confere cada campo; inválido é descartado, incoerente com o texto é rebaixado."""
    extraction = Extraction(
        strategy=result.strategy, cost_usd=result.cost_usd, cached=result.cached
    )
    for name in OpportunityFields.model_fields:
        quoted: Quoted = getattr(result.data, name)
        if is_unknown(quoted):
            continue
        value = quoted.value
        if name in CHOICES:
            value = _choice(value, CHOICES[name])
        elif name in ("deadline", "opens", "starts"):
            value = _iso_date(value)
        elif name in ("min_company_age_months",):
            value = _int(value)
        elif name == "prize_amount_brl":
            value = _decimal(value)
        elif name in ("legal_forms", "required_cnaes", "eligible_regions", "benefits"):
            value = _list(value)
            if name == "legal_forms":
                value = [v for v in value if v in LegalForm.values]
            elif name == "benefits":
                value = [v for v in value if v in Opportunity.Benefit.values]
        else:
            value = str(value).strip()
        if value in (None, "", []):
            continue
        trusted = quoted.verified and quote_in_text(quoted.quote, text)
        if name in CRITICAL:
            trusted = trusted and _consistent(name, quoted.value, text)
        if not trusted:
            extraction.unverified.append(name)
        extraction.fields[name] = Checked(name, value, quoted.quote, trusted)
    return extraction


# -- gravação ------------------------------------------------------------------------------------
def _blank(opp: Opportunity, attr: str) -> bool:
    current = getattr(opp, attr)
    return current in (None, "", [], "unknown")


def _derive_legal_forms(extraction: Extraction) -> Checked | None:
    """Naturezas aceitas: a lista do texto, ou «todas menos MEI» quando o texto veda MEI."""
    forms = extraction.fields.get("legal_forms")
    if forms is not None:
        return forms
    mei = extraction.fields.get("accepts_mei")
    if mei is not None and mei.value == "no":
        rest = [v for v in LegalForm.values if v != LegalForm.MEI]
        return Checked("legal_forms", rest, mei.quote, mei.trusted)
    return None


def _columns(extraction: Extraction) -> dict[str, tuple[Any, Checked]]:
    """Campo extraído -> (coluna de `Opportunity`, valor, campo) já na forma da coluna."""
    f = extraction.fields
    out: dict[str, tuple[Any, Checked]] = {}

    def add(attr: str, name: str, value: Any = None) -> None:
        if name in f:
            out[attr] = (f[name].value if value is None else value, f[name])

    add("description", "summary")
    for name, attr, at in (
        ("deadline", "deadline_at", time(23, 59)),
        ("opens", "opens_at", time.min),
        ("starts", "starts_at", time.min),
    ):
        if name in f:
            out[attr] = (_aware(f[name].value, at), f[name])
    add("requires_legal_entity", "requires_legal_entity")
    forms = _derive_legal_forms(extraction)
    if forms is not None:
        out["eligible_legal_forms"] = (forms.value, forms)
    if "exclusive_small_business" in f:
        out["exclusive_small_business"] = (
            f["exclusive_small_business"].value == "yes",
            f["exclusive_small_business"],
        )
    add("min_company_age_months", "min_company_age_months")
    add("required_cnaes", "required_cnaes")
    add("eligible_regions", "eligible_regions")
    add("scope", "scope")
    add("modality", "modality")
    add("prize_text", "prize_text")
    add("prize_amount_brl", "prize_amount_brl")
    add("benefits", "benefits")
    add("participation_cost_text", "participation_cost")
    add("effort_estimate", "effort")
    add("requirements_text", "requirements")
    return out


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _status_for(opp: Opportunity) -> str | None:
    if opp.status != Opportunity.Status.UNKNOWN or opp.deadline_at is None:
        return None
    now = timezone.now()
    if opp.opens_at and opp.opens_at > now:
        return Opportunity.Status.UPCOMING
    return Opportunity.Status.OPEN if opp.deadline_at >= now else Opportunity.Status.CLOSED


def apply_extraction(
    opp: Opportunity, extraction: Extraction, text: str, *, dry_run: bool = False
) -> dict[str, int]:
    """Grava colunas (só campos confiáveis e em branco) e uma evidência por campo extraído.

    Devolve contagens: `columns` (colunas preenchidas), `observed`, `inferred`.
    """
    counts = {"columns": 0, "observed": 0, "inferred": 0}
    method = (
        "regex:extract_opportunity"
        if extraction.strategy == "rules"
        else f"llm:{extraction.strategy}@{PROMPT_VERSION}"
    )
    changed: list[str] = []
    for attr, (value, source) in _columns(extraction).items():
        if source.trusted or source.name not in CRITICAL:
            if _blank(opp, attr):
                setattr(opp, attr, value)
                changed.append(attr)
        evidence_kind = "observed" if source.trusted else "inferred"
        counts[evidence_kind] += 1
        if dry_run:
            continue
        try:
            record_evidence(
                opp,
                attr,
                _json_safe(value),
                kind=evidence_kind,
                method=method,
                source_url=opp.official_url,
                source_name="extração de oportunidade",
                excerpt=source.quote,
                source_text=text,
            )
        except EvidenceError:
            counts[evidence_kind] -= 1  # citação inválida ou sem URL: o dado fica sem evidência
    status = _status_for(opp) if not dry_run else None
    if status:
        opp.status = status
        changed.append("status")
    counts["columns"] = len(changed)
    if not dry_run:
        opp.extraction_version = EXTRACTION_VERSION
        opp.save()
    return counts


def extract_opportunity(
    opp: Opportunity, text: str, service: AIService, *, title: str = ""
) -> Extraction:
    """Roda a tarefa sobre o texto da página (público) e devolve os campos já conferidos."""
    window = select_windows(text, MAX_WINDOW_CHARS)
    data = LLMInput(
        DataClass.PUBLIC,
        text=window,
        url=opp.official_url,
        extra={"title": title or opp.title},
    )
    result = service.run(TASK_NAME, data)
    return review(result, window)


__all__ = [
    "EXTRACTION_VERSION",
    "Extraction",
    "OpportunityFields",
    "apply_extraction",
    "extract_opportunity",
    "review",
]
