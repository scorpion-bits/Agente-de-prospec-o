"""Digest semanal (E15): o que importa da semana, sem abrir o sistema.

Só leitura do banco, sem IA e sem rede. Reaproveita `Score` (E13) e `Triage` (E14).
Oportunidades bloqueadas por gate ou já descartadas/concluídas nunca entram nas listas de ação;
as bloqueadas por requisito da empresa têm seção própria.
Cada lista tem limite rígido para o digest caber em minutos.
O arquivo traz dados pessoais (resumo de interações): fica em `data/digests/` (ignorado pelo git,
ADR-014) e o e-mail opcional só vai para endereços da própria empresa (ADR-005, ADR-037).
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.mail import EmailMultiAlternatives
from django.db.models import Sum
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from collection.models import CollectionRun
from core.models import Opportunity, Organization, Source, Triage
from llm.models import LLMCall
from scoring.models import Score

TOP_N = 10
DEADLINE_DAYS = 14
FOLLOW_UP_AHEAD_DAYS = 7
NEW_LIMIT = 10
LIST_LIMIT = 10
FIRST_WINDOW_DAYS = 7
STALE_SOURCE_DAYS = 7
SUMMARY_CHARS = 160
EXCLUDED = (Triage.Status.DISCARDED, Triage.Status.DONE)
STATE_FILE = ".state.json"
LEADS_NOTE = "Seções de leads entram com a E21 (leads institucionais)."


@dataclass
class Digest:
    generated_at: datetime
    since: datetime
    week: str
    base_url: str
    follow_ups: dict = field(default_factory=dict)
    top: list = field(default_factory=list)
    deadlines: list = field(default_factory=list)
    new: dict = field(default_factory=dict)
    blocked: dict = field(default_factory=dict)
    sources: dict = field(default_factory=dict)
    costs: dict = field(default_factory=dict)
    leads_note: str = LEADS_NOTE


def week_label(moment):
    year, week, _ = timezone.localtime(moment).isocalendar()
    return f"{year}-W{week:02d}"


def _excluded_ids():
    ct = ContentType.objects.get_for_model(Opportunity)
    return set(
        Triage.objects.filter(content_type=ct, status__in=EXCLUDED).values_list(
            "object_id", flat=True
        )
    )


def _link(base_url, opp):
    return base_url.rstrip("/") + reverse("admin:core_opportunity_change", args=[opp.pk])


def _reasons(score):
    """Linha de «por quê»: os dois fatores que mais pontuaram, com a explicação do Score."""
    rows = sorted(score.breakdown, key=lambda r: -r["points"])[:2]
    parts = [f"{r['label']}: {r['explanation']}" for r in rows]
    if score.alerts:
        parts.append(f"⚠ {score.alerts[0]}")
    return " · ".join(parts)


def _item(opp, score, base_url):
    return {
        "title": opp.title,
        "organizer": opp.organizer_name or (opp.organizer.name if opp.organizer_id else ""),
        "label": score.get_label_display() if score else "",
        "total": score.total if score else None,
        "why": _reasons(score) if score and not score.gated else "",
        "deadline": timezone.localtime(opp.deadline_at).date() if opp.deadline_at else None,
        "url": opp.official_url,
        "admin_url": _link(base_url, opp),
    }


def _live_scores(excluded):
    """Pontuações de oportunidades abertas: não bloqueadas, não descartadas/concluídas."""
    ct = ContentType.objects.get_for_model(Opportunity)
    return Score.objects.filter(content_type=ct, gated=False, total__isnull=False).exclude(
        object_id__in=excluded
    )


def follow_ups(today):
    """Organizações com próxima ação vencida ou nos próximos dias, com a última interação."""
    limit = today + timedelta(days=FOLLOW_UP_AHEAD_DAYS)
    qs = Organization.objects.filter(next_action_at__lte=limit).order_by("next_action_at", "name")
    rows = []
    for org in qs[:LIST_LIMIT]:
        last = org.interactions.order_by("-occurred_at", "-id").first()
        summary = (last.summary or "")[:SUMMARY_CHARS] if last else ""
        rows.append(
            {
                "name": org.name,
                "due": org.next_action_at,
                "overdue_days": max((today - org.next_action_at).days, 0),
                "last": (
                    f"{last.get_kind_display()} em {last.occurred_at:%d/%m/%Y}"
                    if last and last.occurred_at
                    else (last.get_kind_display() if last else "sem interação registrada")
                ),
                "outcome": last.get_outcome_display() if last else "",
                "summary": summary,
            }
        )
    return {"rows": rows, "total": qs.count()}


def top_opportunities(excluded, base_url):
    scores = (
        _live_scores(excluded)
        .exclude(label__in=[Score.Label.IGNORE])
        .order_by("-total", "object_id")[:TOP_N]
    )
    opps = Opportunity.objects.in_bulk([s.object_id for s in scores])
    return [_item(opps[s.object_id], s, base_url) for s in scores if s.object_id in opps]


def upcoming_deadlines(now, excluded, base_url):
    ct = ContentType.objects.get_for_model(Opportunity)
    live = dict(_live_scores(excluded).values_list("object_id", "id"))
    qs = (
        Opportunity.objects.filter(
            deadline_at__gte=now, deadline_at__lte=now + timedelta(days=DEADLINE_DAYS)
        )
        .exclude(pk__in=excluded)
        .exclude(status=Opportunity.Status.CLOSED)
        .order_by("deadline_at")
    )
    scores = {
        s.object_id: s
        for s in Score.objects.filter(content_type=ct, object_id__in=list(live), gated=False)
    }
    return [_item(o, scores[o.pk], base_url) for o in qs if o.pk in scores][:LIST_LIMIT]


def new_since(since, excluded, base_url):
    live = {s.object_id: s for s in _live_scores(excluded)}
    qs = Opportunity.objects.filter(first_seen_at__gt=since, pk__in=list(live)).order_by(
        "-first_seen_at"
    )
    return {
        "rows": [_item(o, live[o.pk], base_url) for o in qs[:NEW_LIMIT]],
        "total": qs.count(),
    }


def blocked_by_requirement(excluded, base_url):
    ct = ContentType.objects.get_for_model(Opportunity)
    scores = Score.objects.filter(
        content_type=ct, gated=True, gate_kind=Score.GateKind.COMPANY_REQUIREMENT
    ).exclude(object_id__in=excluded)
    opps = Opportunity.objects.in_bulk([s.object_id for s in scores])
    live = [(s, opps[s.object_id]) for s in scores if s.object_id in opps]
    live = [(s, o) for s, o in live if o.status != Opportunity.Status.CLOSED]
    live.sort(key=lambda p: -(p[1].prize_amount_brl or Decimal(0)))
    total = sum((o.prize_amount_brl or Decimal(0)) for _, o in live)
    with_value = sum(1 for _, o in live if o.prize_amount_brl)
    rows = [
        {
            "title": o.title,
            "reason": s.gate_reason,
            "amount": o.prize_amount_brl,
            "admin_url": _link(base_url, o),
        }
        for s, o in live[:LIST_LIMIT]
    ]
    return {"rows": rows, "total": len(live), "amount": total, "with_value": with_value}


def source_status(now):
    """Fontes habilitadas: execuções com erro e há quanto tempo foi a última coleta."""
    problems, stale = [], []
    for source in Source.objects.filter(enabled=True):
        last = source.runs.filter(dry_run=False).exclude(status=CollectionRun.Status.RUNNING)
        last = last.order_by("-started_at").first()
        if last is None:
            stale.append((source.slug, "nunca coletada"))
            continue
        age = (now - last.started_at).days
        if last.status in (CollectionRun.Status.ERROR, CollectionRun.Status.PARTIAL):
            problems.append((source.slug, last.get_status_display(), last.started_at))
        if age > STALE_SOURCE_DAYS:
            stale.append((source.slug, f"última coleta há {age} dias"))
    return {"problems": problems, "stale": stale}


def month_costs(now):
    start = timezone.localtime(now).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    qs = LLMCall.objects.filter(created_at__gte=start)
    by = {
        b: qs.filter(billing=b).aggregate(c=Sum("cost_usd"))["c"] or Decimal(0)
        for b in ("money", "credits")
    }
    return {
        "money": by["money"],
        "credits": by["credits"],
        "calls": qs.count(),
        "money_budget": settings.LLM_MONTHLY_BUDGET_USD,
        "credits_budget": settings.LLM_CREDITS_MONTHLY_USD,
    }


def read_state(out_dir):
    try:
        data = json.loads((Path(out_dir) / STATE_FILE).read_text())
        return datetime.fromisoformat(data["generated_at"])
    except (OSError, ValueError, KeyError):
        return None


def write_state(out_dir, moment):
    (Path(out_dir) / STATE_FILE).write_text(json.dumps({"generated_at": moment.isoformat()}))


def build(now=None, since=None, base_url=None):
    now = now or timezone.now()
    since = since or now - timedelta(days=FIRST_WINDOW_DAYS)
    base_url = base_url or settings.DIGEST_BASE_URL
    excluded = _excluded_ids()
    return Digest(
        generated_at=now,
        since=since,
        week=week_label(now),
        base_url=base_url,
        follow_ups=follow_ups(timezone.localtime(now).date()),
        top=top_opportunities(excluded, base_url),
        deadlines=upcoming_deadlines(now, excluded, base_url),
        new=new_since(since, excluded, base_url),
        blocked=blocked_by_requirement(excluded, base_url),
        sources=source_status(now),
        costs=month_costs(now),
    )


def _brl(value):
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _day(d):
    return f"{d:%d/%m/%Y}" if d else "sem prazo informado"


def render_html(digest):
    return render_to_string("reports/digest.html", {"d": digest, "brl": _brl})


def render_markdown(d):
    out = [f"# Digest semanal {d.week}", ""]
    out.append(
        f"Gerado em {timezone.localtime(d.generated_at):%d/%m/%Y %H:%M}. Novidades desde "
        f"{timezone.localtime(d.since):%d/%m/%Y %H:%M}."
    )

    out += ["", f"## Follow-ups ({d.follow_ups['total']})", ""]
    for r in d.follow_ups["rows"]:
        late = f" — **vencido há {r['overdue_days']} dias**" if r["overdue_days"] else ""
        out.append(
            f"- {r['name']}: ação em {_day(r['due'])}{late}. Última: {r['last']}"
            f" ({r['outcome'] or '—'}). {r['summary']}".rstrip()
        )
    if not d.follow_ups["rows"]:
        out.append("Nenhum follow-up vencido ou próximo.")

    out += ["", f"## Top {TOP_N} por pontuação", ""]
    for i, t in enumerate(d.top, 1):
        out.append(
            f"{i}. **{t['title']}** — {t['total']}/100 ({t['label']}); "
            f"prazo {_day(t['deadline'])}. "
            f"{t['why']} [admin]({t['admin_url']})"
            + (f" · [oficial]({t['url']})" if t["url"] else "")
        )
    if not d.top:
        out.append("Nenhuma oportunidade pontuada (rode `make rescore`).")

    out += ["", f"## Prazos em até {DEADLINE_DAYS} dias", ""]
    for t in d.deadlines:
        out.append(
            f"- {_day(t['deadline'])}: **{t['title']}** ({t['total']}/100) "
            f"[admin]({t['admin_url']})"
        )
    if not d.deadlines:
        out.append("Nenhum prazo próximo.")

    out += ["", f"## Novidades ({d.new['total']})", ""]
    for t in d.new["rows"]:
        out.append(f"- **{t['title']}** ({t['total']}/100, {t['label']}) [admin]({t['admin_url']})")
    if d.new["total"] > len(d.new["rows"]):
        out.append(f"- … e mais {d.new['total'] - len(d.new['rows'])}.")
    if not d.new["rows"]:
        out.append("Nada novo e elegível desde o último digest.")

    b = d.blocked
    out += ["", f"## Bloqueadas por requisito da empresa ({b['total']})", ""]
    if b["total"]:
        out.append(f"Valor somado (de {b['with_value']} com valor informado): {_brl(b['amount'])}.")
    for r in b["rows"]:
        val = f" ({_brl(r['amount'])})" if r["amount"] else ""
        out.append(f"- **{r['title']}**{val}: {r['reason']} [admin]({r['admin_url']})")
    if not b["rows"]:
        out.append("Nenhuma.")

    out += ["", "## Fontes", ""]
    for slug, status, when in d.sources["problems"]:
        out.append(
            f"- {slug}: última execução {status.lower()} ({timezone.localtime(when):%d/%m/%Y})"
        )
    for slug, what in d.sources["stale"]:
        out.append(f"- {slug}: {what}")
    if not (d.sources["problems"] or d.sources["stale"]):
        out.append("Todas as fontes habilitadas coletaram sem erro.")

    c = d.costs
    out += [
        "",
        "## Custo do mês (IA)",
        "",
        f"- Dinheiro novo: US$ {c['money']:.2f} de US$ {c['money_budget']:.2f}",
        f"- Créditos: US$ {c['credits']:.2f} de US$ {c['credits_budget']:.2f}",
        f"- Chamadas: {c['calls']} (a busca web ainda não registra custo)",
        "",
        f"_{d.leads_note}_",
        "",
    ]
    return "\n".join(out)


def write_files(digest, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"{digest.week}.html"
    md_path = out_dir / f"{digest.week}.md"
    html_path.write_text(render_html(digest), encoding="utf-8")
    md_path.write_text(render_markdown(digest), encoding="utf-8")
    write_state(out_dir, digest.generated_at)
    return html_path, md_path


class EmailNotAllowed(ValueError):
    pass


def team_recipients(addresses=None):
    """Destinatários do e-mail: só endereços do domínio da equipe (ADR-005, ADR-037)."""
    addresses = list(addresses if addresses is not None else settings.DIGEST_EMAIL_TO)
    domain = "@" + settings.DIGEST_EMAIL_DOMAIN
    bad = [a for a in addresses if not a.lower().endswith(domain)]
    if bad or not addresses:
        raise EmailNotAllowed(
            f"O digest só pode ser enviado a endereços {domain} (configure DIGEST_EMAIL_TO)."
        )
    return addresses


def send_email(digest, recipients=None):
    to = team_recipients(recipients)
    sender = settings.DIGEST_EMAIL_FROM
    if not sender.lower().endswith("@" + settings.DIGEST_EMAIL_DOMAIN):
        raise EmailNotAllowed("DIGEST_EMAIL_FROM precisa ser um endereço da equipe.")
    msg = EmailMultiAlternatives(
        f"Radar Scorpion Bits — digest {digest.week}", render_markdown(digest), sender, to
    )
    msg.attach_alternative(render_html(digest), "text/html")
    msg.send()
    return to
