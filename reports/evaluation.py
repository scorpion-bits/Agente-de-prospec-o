"""Avaliação do MVP (E22): relatório de go/no-go com M1–M9, prontidão e sugestão de decisão.

Só leitura, sem IA e sem rede. Reaproveita `reports.metrics`. A saída traz contagens e
percentuais, nunca dados de contato (repositório público, ADR-014). A decisão é humana
(ADR-005, ADR-040): aqui só há uma **sugestão** por regras explícitas.
"""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db.models import Min, Sum
from django.utils import timezone

from collection.models import CollectionRun
from core.services.triage import DECIDED
from llm.models import LLMCall
from reports import metrics as m

MIN_DAYS = 28  # ≥ 4 semanas de uso real (plano da E22)
MIN_DECIDED = 20  # triagens decididas mínimas para falar em precisão
M3_GOAL = 5
M6_GOAL_MINUTES = 30

# Valor entregue: se falhar junto, o sistema não se paga.
CORE = ("M1", "M2", "M4")

CONTINUE, ADJUST, STOP, EXTEND = "continuar", "ajustar", "parar", "estender"
LABELS = {
    CONTINUE: "Continuar (seguir para a Fase 4, E27 primeiro)",
    ADJUST: "Ajustar (corrigir o que falhou e reavaliar)",
    STOP: "Parar (o sistema não entregou valor)",
    EXTEND: "Estender o período (dados insuficientes para decidir)",
}


@dataclass
class Readiness:
    days: int | None  # dias desde o primeiro uso real
    decided: int
    ready: bool
    reasons: list


@dataclass
class Evaluation:
    generated_at: object
    readiness: Readiness
    metrics: list
    money_usd: Decimal
    credits_usd: Decimal
    suggestion: str
    rationale: list


def readiness(now):
    """Prontidão: ≥ 4 semanas desde a 1ª coleta real ou triagem, e ≥ 20 triagens decididas."""
    first_run = CollectionRun.objects.filter(dry_run=False).aggregate(t=Min("started_at"))["t"]
    first_triage = m._opp_triage().filter(status__in=DECIDED).aggregate(t=Min("decided_at"))["t"]
    firsts = [t for t in (first_run, first_triage) if t]
    days = (now - min(firsts)).days if firsts else None
    decided = m._opp_triage().filter(status__in=DECIDED).count()
    reasons = []
    if days is None:
        reasons.append("nenhum uso real registrado (coleta ou triagem)")
    elif days < MIN_DAYS:
        reasons.append(f"{days} dias de uso; mínimo {MIN_DAYS}")
    if decided < MIN_DECIDED:
        reasons.append(f"{decided} triagens decididas; mínimo {MIN_DECIDED}")
    return Readiness(days, decided, not reasons, reasons)


def apply_manual(metric_list, new_vs_manual=None, triage_minutes=None):
    """Preenche M3 (novidade vs. baseline) e M6 (tempo de triagem), que são autodeclarados."""
    by_code = {x.code: x for x in metric_list}
    if new_vs_manual is not None:
        by_code["M3"].value = new_vs_manual
        by_code["M3"].detail = "informado por --m3 (conferido contra o baseline manual da E01)"
        by_code["M3"].ok = new_vs_manual >= M3_GOAL
    if triage_minutes is not None:
        by_code["M6"].value = triage_minutes
        by_code["M6"].detail = "informado por --m6 (média semanal, autodeclarada)"
        by_code["M6"].ok = triage_minutes <= M6_GOAL_MINUTES
    return metric_list


def suggest(ready, metric_list):
    """Regras do ADR-040. Devolve (decisão sugerida, justificativas)."""
    if not ready.ready:
        return EXTEND, [f"Prontidão: {r}." for r in ready.reasons]
    by_code = {x.code: x for x in metric_list}
    core = [by_code[c] for c in CORE]
    why = []
    if all(x.ok is False for x in core):
        return STOP, ["M1, M2 e M4 abaixo da meta: sem valor entregue no período."]
    failing = [x for x in metric_list if x.ok is False]
    missing = [x.code for x in core if x.ok is None]
    if missing:
        return EXTEND, [f"Sem dados em {', '.join(missing)}: não dá para decidir."]
    for x in failing:
        why.append(f"{x.code} abaixo da meta ({x.value} vs {x.goal}).")
    if failing:
        return ADJUST, why
    return CONTINUE, ["M1, M2 e M4 dentro da meta e nenhuma outra métrica com dados abaixo dela."]


def build(now=None, new_vs_manual=None, triage_minutes=None):
    now = now or timezone.now()
    ready = readiness(now)
    metric_list = apply_manual(m.compute(now), new_vs_manual, triage_minutes)
    since = now - timedelta(days=m.WINDOW_DAYS)
    qs = LLMCall.objects.filter(created_at__gte=since)
    money = qs.filter(billing="money").aggregate(t=Sum("cost_usd"))["t"] or Decimal(0)
    credits = qs.filter(billing="credits").aggregate(t=Sum("cost_usd"))["t"] or Decimal(0)
    suggestion, why = suggest(ready, metric_list)
    return Evaluation(now, ready, metric_list, money, credits, suggestion, why)


def render_markdown(ev):
    r = ev.readiness
    lines = [
        f"# Avaliação do MVP — {timezone.localtime(ev.generated_at):%Y-%m-%d}",
        "",
        "> Gerado por `make evaluate`. Só contagens (sem dados de contato). "
        "A decisão é humana: registre-a em ADR.",
        "",
        "## Prontidão",
        f"- Dias de uso real: {'sem dados' if r.days is None else r.days} (mínimo {MIN_DAYS})",
        f"- Triagens decididas: {r.decided} (mínimo {MIN_DECIDED})",
        f"- Pronto para decidir: {'sim' if r.ready else 'não — ' + '; '.join(r.reasons)}",
        "",
        "## Métricas (últimos 28 dias)",
        "",
        "| # | Métrica | Valor | Meta | Situação | Detalhe |",
        "|---|---|---|---|---|---|",
    ]
    for x in ev.metrics:
        value = "sem dados" if x.value is None else x.value
        mark = {True: "✅", False: "⚠️", None: "·"}[x.ok]
        lines.append(f"| {x.code} | {x.name} | {value} | {x.goal} | {mark} | {x.detail} |")
    lines += [
        "",
        "## Custos (28 dias)",
        f"- Dinheiro novo (IA paga): US$ {ev.money_usd:.2f}",
        f"- Créditos (AI Pro): US$ {ev.credits_usd:.2f} equivalentes",
        "- Busca web ainda não registra custo: somar a fatura do provedor à mão.",
        "",
        "## Sugestão (regras do ADR-040)",
        f"**{LABELS[ev.suggestion]}**",
        "",
    ]
    lines += [f"- {w}" for w in ev.rationale]
    lines += [
        "",
        "## Falta preencher à mão (não vem do banco)",
        "- Comparação com o baseline manual (E01, `docs/research/baseline-manual.md`) e M3.",
        "- M6: tempo de triagem semanal (média das semanas, autodeclarada).",
        "- Casos de sucesso e de fracasso (2–3 de cada, sem dados pessoais).",
        "- Decisão final e etapas da Fase 4 escolhidas (ADR).",
    ]
    return "\n".join(lines) + "\n"
