"""Pipeline leve (E23, ADR-045): ritmo de follow-up e funil dos negócios. Sem IA, sem rede.

Regras de follow-up (docs/plan/fase-4-pos-mvp.md): no máximo **2** follow-ups depois do primeiro
contato e **7 dias** entre tentativas. Contam como tentativa as interações `message`, `call` e
`proposal_sent` com data, ligadas ao negócio, **depois da última resposta** (uma resposta zera a
contagem). O sistema só **alerta**; quem decide e contata é o humano (ADR-005).
"""

from dataclasses import dataclass
from datetime import date, timedelta

from core.models import Deal, Interaction
from core.models.deal import FUNNEL, OPEN_STAGES

MAX_FOLLOW_UPS = 2
FOLLOW_UP_INTERVAL_DAYS = 7

_K = Interaction.Kind
_ATTEMPT_KINDS = {_K.MESSAGE, _K.CALL, _K.PROPOSAL_SENT}


@dataclass(frozen=True)
class FollowUpState:
    state: str  # closed | no_contact | replied | wait | due | limit
    attempts: int = 0
    follow_ups: int = 0
    next_at: date | None = None
    message: str = ""

    @property
    def needs_attention(self):
        return self.state in ("due", "limit")


def follow_up_state(deal, today, interactions=None) -> FollowUpState:
    """Em que ponto do ritmo de follow-up o negócio está."""
    if not deal.is_open:
        return FollowUpState("closed", message="negócio encerrado")
    items = interactions if interactions is not None else list(deal.interactions.all())
    dated = [i for i in items if i.occurred_at]
    replies = [
        i.occurred_at
        for i in dated
        if i.kind == _K.RESPONSE_RECEIVED or i.outcome == Interaction.Outcome.POSITIVE
    ]
    last_reply = max(replies) if replies else None
    attempts = sorted(
        i.occurred_at
        for i in dated
        if i.kind in _ATTEMPT_KINDS and (last_reply is None or i.occurred_at > last_reply)
    )
    if not attempts:
        if last_reply:
            return FollowUpState("replied", message="responderam; a próxima jogada é sua")
        return FollowUpState("no_contact", message="ainda sem primeiro contato registrado")
    follow_ups = len(attempts) - 1
    if last_reply and last_reply > attempts[-1]:
        return FollowUpState("replied", len(attempts), follow_ups, message="responderam")
    next_at = attempts[-1] + timedelta(days=FOLLOW_UP_INTERVAL_DAYS)
    if follow_ups >= MAX_FOLLOW_UPS:
        return FollowUpState(
            "limit",
            len(attempts),
            follow_ups,
            next_at,
            f"limite de {MAX_FOLLOW_UPS} follow-ups sem resposta: encerrar ou pausar",
        )
    if today >= next_at:
        late = (today - next_at).days
        when = "hoje" if late == 0 else f"há {late} dia(s)"
        return FollowUpState(
            "due", len(attempts), follow_ups, next_at, f"follow-up {follow_ups + 1} devido {when}"
        )
    return FollowUpState(
        "wait",
        len(attempts),
        follow_ups,
        next_at,
        f"aguardar até {next_at:%d/%m} (intervalo de {FOLLOW_UP_INTERVAL_DAYS} dias)",
    )


def advance_stage(deal):
    """Próximo estágio do funil (Interessante → … → Fechado). `None` se já encerrado."""
    if not deal.is_open:
        return None
    return FUNNEL[FUNNEL.index(deal.stage) + 1]


def funnel():
    """Negócios por estágio e quantos **alcançaram** cada um (perdido conta até onde foi)."""
    deals = list(Deal.objects.all())
    current = {s: 0 for s in (*FUNNEL, Deal.Stage.LOST)}
    reached = {s: 0 for s in FUNNEL}
    for d in deals:
        current[d.stage] += 1
        peak = FUNNEL.index(d.peak_stage) if d.peak_stage in FUNNEL else 0
        for s in FUNNEL[: peak + 1]:
            reached[s] += 1
    open_value = sum((d.estimated_value or 0 for d in deals if d.stage in OPEN_STAGES), 0)
    won_value = sum((d.estimated_value or 0 for d in deals if d.stage == Deal.Stage.WON), 0)
    return {
        "total": len(deals),
        "current": current,
        "reached": reached,
        "open_value": open_value,
        "won_value": won_value,
    }


def deals_needing_follow_up(today):
    """Negócios abertos com follow-up devido ou no limite, do mais atrasado para o mais novo."""
    rows = []
    qs = Deal.objects.filter(stage__in=OPEN_STAGES).select_related("organization")
    for deal in qs.prefetch_related("interactions"):
        st = follow_up_state(deal, today)
        if st.needs_attention:
            rows.append((deal, st))
    rows.sort(key=lambda r: (r[1].next_at or today, r[0].pk))
    return rows
