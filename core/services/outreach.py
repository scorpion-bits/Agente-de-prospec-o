"""E24 — rascunho de abordagem assistido (ADR-046).

Fluxo: fatos com origem (organização, evidência **observada**, match, portfólio público, histórico)
→ tarefa de IA `draft_outreach` (Gemini 3.1 Pro × Claude Sonnet 5.5, por último a estratégia de
**regras**, um modelo de texto sem IA) → **validador** (cada afirmação cita fatos do tipo certo;
links e números só se estão nos fatos) → `OutreachDraft`. O sistema nunca envia nada (ADR-005):
o humano edita, copia e envia. Histórico é dado `internal`: só provedor pago ou local.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal

from django.contrib.contenttypes.models import ContentType
from pydantic import BaseModel, Field

from core.models import (
    Evidence,
    Interaction,
    Match,
    Organization,
    OutreachDraft,
    ServiceOffering,
)
from core.services.suppression import SuppressionIndex
from llm.router import AIService
from llm.tasks import Task, register_task
from llm.types import DataClass, LLMError, LLMInput

TASK_NAME = "draft_outreach"
PROMPT_VERSION = "v1"
SYSTEM_PROMPT = (
    Path(__file__).resolve().parent.parent / "prompts" / "draft_outreach_v1.txt"
).read_text()

# Gemini 3.1 Pro primeiro: empate no A/B → Gemini (ADR-011); `rules` garante um texto sempre.
DEFAULT_STRATEGIES = ["gemini-paid:gemini-3.1-pro", "anthropic:claude-sonnet-5-5", "rules"]

INTRO = (
    "A Scorpion Bits é um estúdio de jogos e tecnologia de Araraquara/SP que cria jogos "
    "educativos, cursos e oficinas de programação e jogos, e software e sites sob demanda."
)
SITE = "scorpionbits.com"
MAX_WORDS = {"email": 120, "whatsapp": 70}
MAX_EVIDENCE_FACTS = 4
MAX_HISTORY_FACTS = 5
HISTORY_KINDS = {"proposal_sent", "meeting", "call", "visit", "message", "course_delivered"}

URL_RE = re.compile(
    r"(?:https?://|www\.)[^\s)>\]»”\"']+|\b[\w-]+(?:\.[\w-]+)*\.(?:com|org|net|br)\b\S*"
)
NUMBER_RE = re.compile(r"\d[\d.,]*")


class OutreachBlocked(Exception):
    """Organização em opt-out/«não contatar»: nenhum rascunho é gerado."""


class OutreachError(Exception):
    """Não dá para gerar (sem serviço, sem match)."""


@dataclass(frozen=True)
class Fact:
    id: str
    kind: str  # intro | record | observed | hypothesis | offer | portfolio | history
    text: str
    url: str = ""


class DraftClaim(BaseModel):
    text: str = ""
    about: Literal["recipient", "scorpion", "offer", "history"]
    facts: list[str] = Field(default_factory=list)


class DraftOutput(BaseModel):
    subject: str = ""
    body: str
    claims: list[DraftClaim] = Field(default_factory=list)


# kind do fato exigido por tipo de afirmação (pelo menos um fato de cada lista)
ALLOWED_KINDS = {
    "recipient": {"record", "observed"},
    "scorpion": {"intro", "portfolio"},
    "offer": {"offer", "portfolio"},
    "history": {"history"},
}


# -- fatos -------------------------------------------------------------------------------------
def _date(value) -> str:
    return value.strftime("%d/%m/%Y") if value else "data não informada"


def build_facts(organization: Organization, service: ServiceOffering, match: Match | None):
    """Lista de fatos com id. Só observado/registrado; contato pessoal nunca entra."""
    facts: list[Fact] = []

    def add(kind, text, url=""):
        facts.append(Fact(f"F{len(facts) + 1}", kind, text, url))

    add("intro", INTRO, f"https://{SITE}")
    where = ", ".join(x for x in (organization.municipality_name, organization.uf) if x)
    add(
        "record",
        f"Organização: {organization.name}"
        f" ({organization.get_kind_display()})" + (f", em {where}" if where else ""),
    )
    ct = ContentType.objects.get_for_model(Organization)
    observed = (
        Evidence.objects.filter(
            content_type=ct, object_id=organization.pk, kind=Evidence.Kind.OBSERVED
        )
        .exclude(excerpt="")
        .exclude(field__startswith="contact")
        .order_by("-retrieved_at")[:MAX_EVIDENCE_FACTS]
    )
    for ev in observed:
        add(
            "observed",
            f"Em {ev.source_name or 'fonte pública'}: «{ev.excerpt[:200]}»",
            ev.source_url,
        )

    add("offer", f"Serviço a oferecer: {service.name}")
    if match is not None:
        for reason in match.reasons or []:
            text = (reason.get("text") or "").strip()
            if text and not text.startswith(("Prova:", "Sem item")):
                add("hypothesis", f"Hipótese (não confirmada): {text}")
                break
        for item in match.portfolio_refs.filter(public=True).exclude(status="to_confirm")[:2]:
            year = f", {item.year}" if item.year else ""
            add(
                "portfolio",
                f"Trabalho da Scorpion Bits: {item.title} ({item.get_kind_display()}{year})",
                item.public_url,
            )

    history = organization.interactions.filter(kind__in=HISTORY_KINDS).order_by(
        "-occurred_at", "-id"
    )[:MAX_HISTORY_FACTS]
    for it in history:
        svc = f", sobre {it.service.name}" if it.service_id else ""
        add(
            "history",
            f"Histórico: {_date(it.occurred_at)}, {it.get_kind_display()}{svc}"
            f" (resultado: {it.get_outcome_display()})",
        )
    return facts


def mode_for(facts: list[Fact]) -> str:
    has = any(f.kind == "history" for f in facts)
    return OutreachDraft.Mode.FOLLOW_UP if has else OutreachDraft.Mode.FIRST_CONTACT


def proposal_already_sent(
    organization: Organization, service: ServiceOffering
) -> Interaction | None:
    return (
        organization.interactions.filter(kind="proposal_sent", service=service)
        .order_by("-occurred_at", "-id")
        .first()
    )


# -- prompt e regras ---------------------------------------------------------------------------
def _facts_text(facts: list[dict]) -> str:
    return "\n".join(
        f"{f['id']} [{f['kind']}] {f['text']}" + (f" — {f['url']}" if f["url"] else "")
        for f in facts
    )


def build_prompt(data: LLMInput) -> str:
    plan = data.extra
    return (
        f"Modo: {plan['mode']}\nCanal: {plan['channel']}\n"
        f"Organização-alvo: {plan['organization_name']}\n\nFATOS:\n{_facts_text(plan['facts'])}"
    )


def rules_strategy(data: LLMInput) -> dict:
    """Modelo de texto sem IA: monta o rascunho só com os fatos (sempre passa no validador)."""
    plan = data.extra
    facts = plan["facts"]
    by_kind: dict[str, list[dict]] = {}
    for f in facts:
        by_kind.setdefault(f["kind"], []).append(f)
    org_fact = by_kind["record"][0]
    offer = by_kind["offer"][0]
    name = plan["organization_name"]
    service = offer["text"].split(": ", 1)[-1]
    short = plan["channel"] == "whatsapp"
    sentences: list[tuple[str, str, list[str]]] = []  # (texto, about, ids)

    sentences.append((f"Olá, equipe da {name}!", "recipient", [org_fact["id"]]))
    if short:
        intro_text = "Aqui é da Scorpion Bits, estúdio de jogos e tecnologia de Araraquara/SP."
    else:
        intro_text = INTRO
    sentences.append((intro_text, "scorpion", [by_kind["intro"][0]["id"]]))
    if by_kind.get("history"):
        last = by_kind["history"][0]
        when = last["text"].removeprefix("Histórico: ").split(" (")[0]
        sentences.append(
            (
                f"Retomamos nosso contato anterior ({when}).",
                "history",
                [last["id"]],
            )
        )
    if plan.get("proposal_sent"):
        sentences.append(
            (
                f"Sobre a proposta de {service} que enviamos: faz sentido para vocês?",
                "offer",
                [offer["id"]] + [h["id"] for h in by_kind.get("history", [])[:1]],
            )
        )
    else:
        sentences.append(
            (
                f"Queremos conversar sobre {service}, que talvez possa ajudar vocês.",
                "offer",
                [offer["id"]],
            )
        )
    if not short and by_kind.get("observed"):
        ev = by_kind["observed"][0]
        sentences.append(
            (
                f"Vimos publicado pela organização: {ev['text'].split(': ', 1)[-1]}",
                "recipient",
                [ev["id"]],
            )
        )
    for item in by_kind.get("portfolio", [])[: 1 if short else 2]:
        title = item["text"].split(": ", 1)[-1]
        link = f" {item['url']}" if item["url"] else ""
        sentences.append((f"Já realizamos {title}.{link}", "scorpion", [item["id"]]))
    sentences.append(("Podemos conversar rapidamente?", "offer", [offer["id"]]))

    body = (
        " ".join(s for s, _, _ in sentences) if short else "\n\n".join(s for s, _, _ in sentences)
    )
    return {
        "subject": "" if short else f"{service}: uma conversa com a Scorpion Bits",
        "body": body,
        "claims": [{"text": s, "about": a, "facts": ids} for s, a, ids in sentences],
    }


TASK = register_task(
    Task(
        name=TASK_NAME,
        schema=DraftOutput,
        system=SYSTEM_PROMPT,
        strategies=DEFAULT_STRATEGIES,
        prompt_version=PROMPT_VERSION,
        rules=rules_strategy,
        build_prompt=build_prompt,
        max_output_tokens=900,
    )
)


# -- validador ---------------------------------------------------------------------------------
def _digits(text: str) -> set[str]:
    return {re.sub(r"\D", "", m) for m in NUMBER_RE.findall(text)} - {""}


def _clean_url(url: str) -> str:
    url = url.rstrip(".,;:!?)]»”\"'")
    return re.sub(r"^(https?://)?(www\.)?", "", url).rstrip("/").casefold()


def validate_draft(output: DraftOutput, facts: list[Fact], channel: str) -> list[str]:
    """Problemas do rascunho (lista vazia = válido). Mensagens sem repetir o texto gerado."""
    issues: list[str] = []
    by_id = {f.id: f for f in facts}
    text = f"{output.subject}\n{output.body}"
    if not output.body.strip():
        issues.append("texto vazio")
    if not output.claims:
        issues.append("nenhuma afirmação ligada a fatos")
    for n, claim in enumerate(output.claims, 1):
        if not claim.facts:
            issues.append(f"afirmação {n} sem fato citado")
            continue
        unknown = [i for i in claim.facts if i not in by_id]
        if unknown:
            issues.append(f"afirmação {n} cita fato inexistente ({', '.join(unknown)})")
            continue
        kinds = {by_id[i].kind for i in claim.facts}
        if not kinds & ALLOWED_KINDS[claim.about]:
            issues.append(f"afirmação {n} ({claim.about}) sem fato do tipo certo")
    allowed_urls = {_clean_url(f.url) for f in facts if f.url} | {_clean_url(SITE)}
    for url in URL_RE.findall(text):
        if _clean_url(url) not in allowed_urls:
            issues.append("link que não está nos fatos")
            break
    fact_digits = set().union(*(_digits(f.text + " " + f.url) for f in facts)) if facts else set()
    invented = _digits(re.sub(URL_RE, " ", text)) - fact_digits
    if invented:
        issues.append("número que não está nos fatos")
    if len(output.body.split()) > MAX_WORDS[channel] * 1.5:
        issues.append(f"texto longo demais para {channel}")
    if channel == "whatsapp" and output.subject.strip():
        issues.append("WhatsApp não tem assunto")
    if re.search(r"[\w.+-]+@[\w-]+\.[\w.]+|\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}", text):
        issues.append("e-mail ou telefone no texto")
    return issues


# -- geração -----------------------------------------------------------------------------------
def pick_match(organization: Organization, service: ServiceOffering | None):
    matches = Match.objects.filter(organization=organization).select_related("service")
    if service is not None:
        return service, matches.filter(service=service).first()
    best = matches.first()  # ordenado por força
    if best is None:
        raise OutreachError("sem match para a organização: rode `make match` ou escolha o serviço")
    return best.service, best


def generate_draft(
    organization: Organization,
    *,
    service: ServiceOffering | None = None,
    channel: str = OutreachDraft.Channel.EMAIL,
    strategies: list[str] | None = None,
    fallback: bool = True,
    ai: AIService | None = None,
    user=None,
) -> OutreachDraft:
    """Gera e grava um rascunho. `fallback=False` (A/B): uma estratégia; o rejeitado é gravado."""
    if SuppressionIndex.load().organization_blocked(organization):
        raise OutreachBlocked("organização em opt-out ou «não contatar»")
    service, match = pick_match(organization, service)
    facts = build_facts(organization, service, match)
    mode = mode_for(facts)
    plan = {
        "mode": mode,
        "channel": channel,
        "organization_name": organization.name,
        "proposal_sent": proposal_already_sent(organization, service) is not None,
        "facts": [asdict(f) for f in facts],
    }
    llm_input = LLMInput(DataClass.INTERNAL, extra=plan)
    ai = ai or AIService()
    specs = strategies if strategies is not None else TASK.configured_strategies()
    attempts: list[dict] = []
    last: tuple[DraftOutput, str, Decimal, list[str]] | None = None

    for spec in specs:
        try:
            result = ai.run(TASK, llm_input, strategies=[spec])
        except LLMError as exc:
            attempts.append({"strategy": spec, "result": str(exc)[:200]})
            continue
        issues = validate_draft(result.data, facts, channel)
        attempts.append({"strategy": result.strategy, "result": "válido" if not issues else issues})
        last = (result.data, result.strategy, result.cost_usd, issues)
        if not issues:
            break
        if not fallback:
            break

    if last is None:
        raise OutreachError(
            "nenhuma estratégia produziu rascunho: "
            + "; ".join(f"{a['strategy']}: {a['result']}" for a in attempts)
        )
    output, strategy, cost, issues = last
    return OutreachDraft.objects.create(
        organization=organization,
        service=service,
        channel=channel,
        mode=mode,
        subject=output.subject,
        body=output.body,
        claims=[c.model_dump() for c in output.claims],
        facts=plan["facts"],
        status=OutreachDraft.Status.REJECTED if issues else OutreachDraft.Status.VALID,
        validation_issues=issues,
        attempts=attempts,
        strategy=strategy,
        prompt_version=PROMPT_VERSION,
        cost_usd=cost,
        created_by=user,
    )
