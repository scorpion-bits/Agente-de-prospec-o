"""Perfis de pontuação: pesos, faixas e rótulos como **dados** (docs/architecture/scoring.md).

Mudar um peso ou uma faixa = subir `SCORING_VERSION`; `rescore` recalcula tudo e cada `Score`
guarda a versão com que foi calculado (ADR-006). Pesos são hipótese: calibrar na E30.
"""

from __future__ import annotations

FACTORS = ("V", "F", "C", "T", "A", "L")
FACTOR_LABELS = {
    "V": "Valor",
    "F": "Fit",
    "C": "Chance",
    "T": "Timing",
    "A": "Acesso",
    "L": "Leveza",
}

SCORING_VERSION = "v1"

# Fatores na ordem de FACTORS; cada perfil soma 1.
WEIGHTS: dict[str, dict[str, float]] = {
    "opp.edital": {"V": 0.30, "F": 0.20, "C": 0.15, "T": 0.15, "A": 0.05, "L": 0.15},
    "opp.hackathon_jam": {"V": 0.20, "F": 0.25, "C": 0.15, "T": 0.15, "A": 0.10, "L": 0.15},
    "opp.event": {"V": 0.15, "F": 0.20, "C": 0.10, "T": 0.20, "A": 0.25, "L": 0.10},
    # Leads (E21): escolas e SESC valem pela chance e pelo valor recorrente.
    "lead.school_course": {"V": 0.25, "F": 0.25, "C": 0.20, "T": 0.10, "A": 0.15, "L": 0.05},
    "lead.sesc": {"V": 0.25, "F": 0.20, "C": 0.25, "T": 0.10, "A": 0.15, "L": 0.05},
}
LEAD_PROFILES = ("lead.sesc", "lead.school_course")

# Tipo de `Opportunity` -> perfil. Tipo ausente da tabela cai em `opp.event` (o mais neutro).
PROFILE_BY_KIND = {
    "edital": "opp.edital",
    "program": "opp.edital",
    "contest": "opp.edital",
    "procurement": "opp.edital",
    "call_for_partners": "opp.edital",
    "hackathon": "opp.hackathon_jam",
    "game_jam": "opp.hackathon_jam",
    "event": "opp.event",
    "other": "opp.event",
}
DEFAULT_PROFILE = "opp.event"

# Memória comercial (ADR-012): contato há menos que isto não volta como «lead novo».
RECONTACT_DAYS = 21
# Follow-up com data até daqui a tantos dias (ou vencido) vale como timing alto.
FOLLOW_UP_AHEAD_DAYS = 7
FOLLOW_UP_VALUE = 0.95
# Sazonalidade por perfil de lead: mês -> valor de Timing. Escolas planejam o ano seguinte em
# out–dez (hipótese). SESC: planejamento semestral ainda não confirmado (E01b): sem sazonalidade.
SEASONALITY: dict[str, dict[int, float]] = {
    "lead.school_course": {
        10: 0.95,
        11: 0.95,
        12: 0.95,
        1: 0.7,
        2: 0.7,
        3: 0.5,
        4: 0.5,
        5: 0.5,
        6: 0.5,
        7: 0.4,
        8: 0.6,
        9: 0.6,
    },  # fmt: skip
}

# (pontuação mínima, rótulo): do maior para o menor.
BANDS = ((75, "prioritize"), (55, "evaluate"), (35, "low"), (0, "ignore"))

# Confiança: K = K_BASE + K_RANGE × q, com q = fração de fatores sustentados por evidência.
K_BASE = 0.7
K_RANGE = 0.3


def profile_for_kind(kind: str) -> str:
    return PROFILE_BY_KIND.get(kind, DEFAULT_PROFILE)


def label_for(total: int) -> str:
    return next(label for floor, label in BANDS if total >= floor)
