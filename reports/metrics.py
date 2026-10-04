"""Métricas do MVP (E14): M1–M9 de `docs/product/metrics.md`, calculadas do que já está no banco.

Só leitura, sem IA e sem rede. A saída traz contagens e percentuais, nunca dados de contato
(logs públicos, ADR-014). Métrica sem dado devolve `None` e a linha diz «sem dados».
"""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Q, Sum
from django.utils import timezone

from collection.models import CollectionRun
from core.models import Deal, Opportunity, Organization, Triage
from core.services.triage import DECIDED
from llm.models import LLMCall
from scoring.models import Score

TOP_N = 10
WINDOW_DAYS = 28
OVERDUE_DAYS = 7
# Metas de `docs/product/metrics.md`.
INTERESTING_BY_WEEK_GOAL = 2
TOP_PRECISION_GOAL = 0.40
ACTING_GOAL = 3
COST_PER_INTERESTING_GOAL = Decimal("1")
SOURCE_ERROR_GOAL = 0.10


@dataclass
class Metric:
    code: str
    name: str
    value: object  # número, texto ou None (sem dados)
    goal: str
    detail: str = ""
    ok: bool | None = None  # None: sem meta ou sem dados


def _opp_triage(status=None, since=None):
    qs = Triage.objects.filter(content_type=ContentType.objects.get_for_model(Opportunity))
    if status:
        qs = qs.filter(status=status)
    if since:
        qs = qs.filter(decided_at__gte=since)
    return qs


def interesting_per_week(now, window=WINDOW_DAYS):
    """M1: oportunidades marcadas «interessantes» (ou além) por semana, na janela."""
    since = now - timedelta(days=window)
    count = (
        _opp_triage(since=since)
        .filter(status__in=DECIDED)
        .exclude(status=Triage.Status.DISCARDED)
        .count()
    )
    return count, count / (window / 7)


def top_precision(top_n=TOP_N):
    """M2: dos top-N por pontuação (não bloqueadas), % marcados interessantes entre os triados.

    O digest (E15) ainda não existe; o «top» é o ranking atual do `Score`.
    """
    ct = ContentType.objects.get_for_model(Opportunity)
    top_ids = list(
        Score.objects.filter(content_type=ct, gated=False, total__isnull=False)
        .order_by("-total", "object_id")
        .values_list("object_id", flat=True)[:top_n]
    )
    decided = {
        t.object_id: t.status
        for t in _opp_triage().filter(object_id__in=top_ids, status__in=DECIDED)
    }
    if not decided:
        return None, len(top_ids), 0
    good = sum(1 for s in decided.values() if s != Triage.Status.DISCARDED)
    return good / len(decided), len(top_ids), len(decided)


def source_health():
    """M7: por fonte, execuções com erro / total (ignora simulações)."""
    rows = (
        CollectionRun.objects.filter(dry_run=False)
        .values("source__slug")
        .annotate(
            total=Count("id"),
            bad=Count(
                "id",
                filter=Q(status__in=[CollectionRun.Status.ERROR, CollectionRun.Status.PARTIAL]),
            ),
        )
        .order_by("source__slug")
    )
    return [(r["source__slug"], r["bad"], r["total"]) for r in rows]


def discard_reasons():
    """M8: distribuição dos motivos de descarte (oportunidades)."""
    rows = (
        _opp_triage(Triage.Status.DISCARDED)
        .values("discard_reason")
        .annotate(n=Count("id"))
        .order_by("-n")
    )
    labels = dict(Triage.DiscardReason.choices)
    return [(labels.get(r["discard_reason"], r["discard_reason"]), r["n"]) for r in rows]


def overdue_follow_ups(today, days=OVERDUE_DAYS):
    """M9: organizações com próxima ação vencida há mais de `days` dias."""
    return Organization.objects.filter(next_action_at__lt=today - timedelta(days=days)).count()


def compute(now=None):
    now = now or timezone.now()
    today = timezone.localtime(now).date()
    metrics = []

    n, per_week = interesting_per_week(now)
    metrics.append(
        Metric(
            "M1",
            "Itens interessantes por semana",
            round(per_week, 1) if n else None,
            f"≥ {INTERESTING_BY_WEEK_GOAL}/semana",
            f"{n} nos últimos {WINDOW_DAYS} dias",
            per_week >= INTERESTING_BY_WEEK_GOAL if n else None,
        )
    )

    precision, top_total, decided = top_precision()
    metrics.append(
        Metric(
            "M2",
            f"Precisão do topo {TOP_N}",
            None if precision is None else round(precision * 100),
            f"≥ {round(TOP_PRECISION_GOAL * 100)}%",
            f"{decided} triados de {top_total} no topo",
            None if precision is None else precision >= TOP_PRECISION_GOAL,
        )
    )

    metrics.append(
        Metric(
            "M3",
            "Novidade vs. baseline manual",
            None,
            "≥ 5 em 4 semanas",
            "depende do baseline da E01",
        )
    )

    acting = (
        _opp_triage(since=now - timedelta(days=WINDOW_DAYS))
        .filter(status__in=[Triage.Status.ACTING, Triage.Status.DONE])
        .count()
    )
    metrics.append(
        Metric(
            "M4",
            "Ações geradas (em andamento ou concluídas)",
            acting if acting else None,
            f"≥ {ACTING_GOAL} em 4 semanas",
            f"últimos {WINDOW_DAYS} dias",
            acting >= ACTING_GOAL if acting else None,
        )
    )

    money = LLMCall.objects.filter(
        billing="money", created_at__gte=now - timedelta(days=WINDOW_DAYS)
    ).aggregate(total=Sum("cost_usd"))["total"] or Decimal(0)
    cost_per = money / n if n else None
    metrics.append(
        Metric(
            "M5",
            "Custo variável por item interessante (US$)",
            None if cost_per is None else round(cost_per, 2),
            f"≤ US$ {COST_PER_INTERESTING_GOAL}",
            f"US$ {money:.2f} em IA paga (a busca web ainda não registra custo)",
            None if cost_per is None else cost_per <= COST_PER_INTERESTING_GOAL,
        )
    )

    metrics.append(
        Metric("M6", "Tempo de triagem semanal", None, "≤ 30 min", "autodeclarado: anote no STATUS")
    )

    health = source_health()
    runs = sum(t for _, _, t in health)
    bad = sum(b for _, b, _ in health)
    metrics.append(
        Metric(
            "M7",
            "Saúde das fontes (execuções com erro)",
            round(bad / runs * 100) if runs else None,
            f"< {round(SOURCE_ERROR_GOAL * 100)}%",
            "; ".join(f"{slug} {b}/{t}" for slug, b, t in health if b) or "nenhuma com erro",
            bad / runs < SOURCE_ERROR_GOAL if runs else None,
        )
    )

    reasons = discard_reasons()
    metrics.append(
        Metric(
            "M8",
            "Motivos de descarte",
            sum(n for _, n in reasons) or None,
            "diagnóstico",
            "; ".join(f"{label} {n}" for label, n in reasons),
        )
    )

    overdue = overdue_follow_ups(today)
    metrics.append(
        Metric(
            "M9", f"Follow-ups vencidos há > {OVERDUE_DAYS} dias", overdue, "0", "", overdue == 0
        )
    )

    return metrics


def render_funnel(data, due=0):
    """Funil do pipeline (E23): quantos negócios chegaram a cada estágio e onde estão agora.

    Fica fora de `compute()` de propósito: o go/no-go (E22) julga só M1–M9 (ADR-045).
    """
    if not data["total"]:
        return "Funil: sem negócios no pipeline (crie em «Negócios» no admin)."
    labels = dict(Deal.Stage.choices)
    lines = [f"Funil: {data['total']} negócios (valor aberto R$ {data['open_value']:,.2f})."]
    for stage, reached in data["reached"].items():
        lines.append(f"  {labels[stage]}: alcançaram {reached}, agora {data['current'][stage]}")
    lines.append(f"  Perdido: {data['current']['lost']}")
    lines.append(f"  Follow-ups devidos ou no limite: {due}")
    if data["won_value"]:
        lines.append(f"  Valor ganho: R$ {data['won_value']:,.2f}")
    return "\n".join(lines)


def triage_backlog():
    """Contagem de oportunidades por situação de triagem (não triadas incluídas)."""
    total = Opportunity.objects.count()
    by_status = dict(_opp_triage().values_list("status").annotate(n=Count("id")))
    decided = sum(n for s, n in by_status.items() if s != Triage.Status.NEW)
    return {"total": total, "untriaged": total - decided, **by_status}


def render(metrics, backlog):
    lines = [
        f"Triagem: {backlog['total']} oportunidades, {backlog['untriaged']} não triadas.",
        "",
    ]
    for m in metrics:
        if m.value is None:
            shown = "sem dados"
        else:
            shown = str(m.value)
        mark = {True: "✅", False: "⚠️", None: "·"}[m.ok]
        extra = f" ({m.detail})" if m.detail else ""
        lines.append(f"{mark} {m.code} {m.name}: {shown} — meta {m.goal}{extra}")
    return "\n".join(lines)
