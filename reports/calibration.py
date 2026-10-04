"""Calibração de pesos (E30): compara fatores entre interessantes e descartadas e propõe pesos.

Só leitura, sem IA e sem rede. **Nada é aplicado sozinho** (ADR-005/006, ADR-044): a saída é uma
proposta com simulação retroativa; quem muda `scoring/profiles.py` e sobe `SCORING_VERSION` é
o humano. Usa o `breakdown` já gravado em cada `Score` (valor bruto `raw` por fator), então não
recalcula nada e não toca em dado de contato (repositório público, ADR-014).

Amostra: oportunidades não bloqueadas, com pontuação e triagem decidida. Descarte por
«duplicada» ou «dados ruins» não diz nada sobre preferência e fica de fora. Interessante =
interessante, em andamento ou concluída.
"""

from dataclasses import dataclass, field

from django.contrib.contenttypes.models import ContentType

from core.models import Opportunity, Triage
from core.services.triage import DECIDED
from scoring.models import Score
from scoring.profiles import FACTORS, K_BASE, K_RANGE, WEIGHTS

MIN_SAMPLE = 50  # plano da E30: ≥ 50 itens triados
MIN_PER_CLASS = 10  # interessantes e descartadas, cada
MIN_PER_PROFILE = 15  # por perfil, para propor pesos dele
TOP_N = 10
STEP = 0.25  # cada peso muda no máximo ±25% (relativo) por rodada: ajuste gradual
IGNORED_REASONS = (Triage.DiscardReason.DUPLICATE, Triage.DiscardReason.BAD_DATA)


@dataclass
class Item:
    positive: bool
    raw: dict  # fator -> valor bruto 0..1
    support: dict  # fator -> suporte (0, 0,5, 1)
    total: int


@dataclass
class FactorStat:
    factor: str
    mean_pos: float
    mean_neg: float
    auc: float  # P(fator de um interessante > o de uma descartada); 0,5 = não separa


@dataclass
class ProfileReport:
    profile: str
    n_pos: int
    n_neg: int
    enough: bool
    stats: list = field(default_factory=list)
    old_weights: dict = field(default_factory=dict)
    new_weights: dict = field(default_factory=dict)
    before: dict = field(default_factory=dict)  # {"precision": x, "auc": y}
    after: dict = field(default_factory=dict)
    improves: bool = False


@dataclass
class Calibration:
    sample: int
    positives: int
    negatives: int
    ready: bool
    reasons: list
    profiles: list


def auc(pos, neg):
    """AUC por comparação de pares (empate vale 0,5). `None` se faltar uma das classes."""
    if not pos or not neg:
        return None
    wins = sum(1.0 if p > n else 0.5 if p == n else 0.0 for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def collect():
    """Amostra por perfil: `{perfil: [Item]}`."""
    ct = ContentType.objects.get_for_model(Opportunity)
    decided = {
        t.object_id: t
        for t in Triage.objects.filter(content_type=ct, status__in=DECIDED).exclude(
            discard_reason__in=IGNORED_REASONS
        )
    }
    scores = Score.objects.filter(
        content_type=ct, gated=False, total__isnull=False, object_id__in=decided
    )
    by_profile: dict[str, list] = {}
    for s in scores:
        rows = {b["factor"]: b for b in s.breakdown}
        if set(rows) != set(FACTORS):
            continue
        by_profile.setdefault(s.profile, []).append(
            Item(
                positive=decided[s.object_id].status != Triage.Status.DISCARDED,
                raw={k: rows[k]["raw"] for k in FACTORS},
                support={k: rows[k].get("support", 0) for k in FACTORS},
                total=s.total,
            )
        )
    return by_profile


def total_with(weights, item):
    """Mesma fórmula do motor (`scoring.engine.combine`) com outros pesos."""
    q = sum(item.support.values()) / len(FACTORS)
    k = K_BASE + K_RANGE * q
    return round(100 * k * sum(item.raw[f] * weights[f] for f in FACTORS))


def propose(profile, stats):
    """Pesos novos: multiplica cada um por AUC/0,5 limitado a ±STEP e normaliza para somar 1."""
    old = WEIGHTS[profile]
    scaled = {}
    for st in stats:
        mult = min(1 + STEP, max(1 - STEP, st.auc / 0.5)) if st.auc is not None else 1.0
        scaled[st.factor] = old[st.factor] * mult
    total = sum(scaled.values())
    return {f: round(v / total, 3) for f, v in scaled.items()}


def evaluate(items, weights, top_n=TOP_N):
    """Precisão no topo (interessantes entre os top-N) e AUC do total, com `weights`."""
    ranked = sorted(items, key=lambda i: -total_with(weights, i))
    top = ranked[:top_n]
    precision = sum(i.positive for i in top) / len(top) if top else None
    totals = [total_with(weights, i) for i in items]
    pos = [t for t, i in zip(totals, items, strict=True) if i.positive]
    neg = [t for t, i in zip(totals, items, strict=True) if not i.positive]
    return {"precision": precision, "auc": auc(pos, neg)}


def profile_report(profile, items):
    pos = [i for i in items if i.positive]
    neg = [i for i in items if not i.positive]
    rep = ProfileReport(
        profile, len(pos), len(neg), len(items) >= MIN_PER_PROFILE and bool(pos) and bool(neg)
    )
    for f in FACTORS:
        a = auc([i.raw[f] for i in pos], [i.raw[f] for i in neg])
        rep.stats.append(
            FactorStat(
                f,
                sum(i.raw[f] for i in pos) / len(pos) if pos else 0.0,
                sum(i.raw[f] for i in neg) / len(neg) if neg else 0.0,
                a,
            )
        )
    rep.old_weights = dict(WEIGHTS[profile])
    if not rep.enough:
        return rep
    rep.new_weights = propose(profile, rep.stats)
    rep.before = evaluate(items, rep.old_weights)
    rep.after = evaluate(items, rep.new_weights)
    # Só vale propor se o AUC do total sobe e a precisão do topo não cai (critério da E30).
    rep.improves = (rep.after["auc"] or 0) > (rep.before["auc"] or 0) and (
        (rep.after["precision"] or 0) >= (rep.before["precision"] or 0)
    )
    return rep


def build():
    by_profile = collect()
    items = [i for v in by_profile.values() for i in v]
    pos = sum(i.positive for i in items)
    neg = len(items) - pos
    reasons = []
    if len(items) < MIN_SAMPLE:
        reasons.append(f"{len(items)} triagens com pontuação; mínimo {MIN_SAMPLE}")
    if pos < MIN_PER_CLASS:
        reasons.append(f"{pos} interessantes; mínimo {MIN_PER_CLASS}")
    if neg < MIN_PER_CLASS:
        reasons.append(f"{neg} descartadas; mínimo {MIN_PER_CLASS}")
    reports = [profile_report(p, by_profile[p]) for p in sorted(by_profile)]
    return Calibration(len(items), pos, neg, not reasons, reasons, reports)


def _fmt(x, pct=False):
    if x is None:
        return "sem dados"
    return f"{x:.0%}" if pct else f"{x:.2f}"


def render_markdown(cal, now):
    lines = [
        f"# Calibração de pesos — {now:%Y-%m-%d}",
        "",
        "> Gerado por `make calibrate`. Só proposta: nada é aplicado sozinho. Para adotar, edite "
        "`scoring/profiles.py`, suba `SCORING_VERSION`, rode `make rescore` e registre em ADR.",
        "",
        "## Amostra",
        f"- Triagens com pontuação: {cal.sample} (mínimo {MIN_SAMPLE}); interessantes "
        f"{cal.positives}, descartadas {cal.negatives} (mínimo {MIN_PER_CLASS} cada)",
        f"- Pronto para calibrar: {'sim' if cal.ready else 'não — ' + '; '.join(cal.reasons)}",
    ]
    if not cal.profiles:
        lines += ["", "Sem triagens de oportunidades pontuadas: nada a comparar ainda."]
    for r in cal.profiles:
        lines += [
            "",
            f"## Perfil `{r.profile}` ({r.n_pos} interessantes, {r.n_neg} descartadas)",
            "",
            "| Fator | Média (interess.) | Média (descart.) | AUC | Peso atual | Peso proposto |",
            "|---|---|---|---|---|---|",
        ]
        for st in r.stats:
            new = r.new_weights.get(st.factor)
            lines.append(
                f"| {st.factor} | {_fmt(st.mean_pos)} | {_fmt(st.mean_neg)} | {_fmt(st.auc)} | "
                f"{r.old_weights[st.factor]:.2f} | {'—' if new is None else f'{new:.2f}'} |"
            )
        if not r.enough:
            lines += ["", f"Amostra do perfil pequena (mínimo {MIN_PER_PROFILE}): sem proposta."]
            continue
        lines += [
            "",
            f"Simulação retroativa (mesma amostra): precisão do topo {TOP_N} "
            f"{_fmt(r.before['precision'], True)} → {_fmt(r.after['precision'], True)}; "
            f"AUC do total {_fmt(r.before['auc'])} → {_fmt(r.after['auc'])}.",
            "**Proposta "
            + ("melhora" if r.improves else "não melhora")
            + " a simulação"
            + ("." if r.improves else ": manter os pesos atuais.**"),
        ]
    lines += [
        "",
        "## Cuidados",
        "- AUC 0,5 = o fator não separa interessantes de descartadas; < 0,5 = separa ao contrário.",
        "- A simulação usa a própria amostra (sobreajuste): com amostra pequena, trate como pista, "
        "não como prova. Rode de novo a cada ~50 triagens novas.",
        "- Pesos mudam no máximo ±25% por rodada. Descartes por duplicada/dados ruins ficam fora.",
    ]
    return "\n".join(lines) + "\n"
