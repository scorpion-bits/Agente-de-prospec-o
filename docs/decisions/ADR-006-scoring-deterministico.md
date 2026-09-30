# ADR-006 — Pontuação determinística, explicável e por perfis

- **Status:** aceito
- **Data:** 2026-09-30

## Contexto
Precisamos responder "o que fazer primeiro?" e "por que este item recebeu 87?".

## Decisão
Score = gates eliminatórios → 6 fatores (Valor, Fit, Chance, Timing, Acesso, Leveza) em
[0,1] → soma ponderada por **perfil** (edital, hackathon/jam, evento, escola, SESC,
empresa) → multiplicador de confiança nos dados. Breakdown completo salvo. Pesos como
dados versionados. Detalhes em `docs/architecture/scoring.md`.

## Alternativas consideradas
| Alternativa | Por que não |
|---|---|
| LLM dá a nota | Não determinístico, caro, explicação não auditável |
| Modelo de ML treinado | Sem dados de treino ainda; pode vir depois como sugestão de pesos |
| Uma fórmula única para tudo | Distância/valor têm pesos opostos entre tipos |
| Sem score, só filtros | Não responde "o que primeiro" |

## Consequências
+ Explicável, barato, testável, recalculável. − Pesos iniciais são palpites → calibração na E30.

## Quando revisitar
Após ≥ 50 itens triados (E30) ou precisão do topo (M2) < 40% por 3 semanas.
