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
}

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

# (pontuação mínima, rótulo): do maior para o menor.
BANDS = ((75, "prioritize"), (55, "evaluate"), (35, "low"), (0, "ignore"))

# Confiança: K = K_BASE + K_RANGE × q, com q = fração de fatores sustentados por evidência.
K_BASE = 0.7
K_RANGE = 0.3


def profile_for_kind(kind: str) -> str:
    return PROFILE_BY_KIND.get(kind, DEFAULT_PROFILE)


def label_for(total: int) -> str:
    return next(label for floor, label in BANDS if total >= floor)
