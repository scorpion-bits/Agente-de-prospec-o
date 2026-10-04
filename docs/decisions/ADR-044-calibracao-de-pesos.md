# ADR-044 — Calibração de pesos: só proposta, amostra mínima, mudança humana

- **Status:** aceito
- **Data:** 2026-10-04

## Contexto
Os pesos do score (E13, E21) são hipótese (ADR-035, ADR-039). A E30 do plano os ajusta com a triagem real (≥ 50 itens), mas não há uso
real ainda e o resto da Fase 4 espera o go/no-go (E22, P28). A **ferramenta** não depende de dado real: roda vazia («sem dados») e
vale a partir do primeiro lote de triagens.

## Decisão
1. **`reports/calibration.py` + `make calibrate`** (sem IA, sem rede, sem migration; `DRY=1` imprime): grava
   `data/calibrations/AAAA-MM-DD.md` (pasta ignorada pelo git) usando o `breakdown` já gravado em cada `Score` (valor bruto por fator).
2. **Amostra**: oportunidades não bloqueadas, pontuadas e com triagem decidida. Interessante, em andamento e concluída contam como
   positivas; descartadas, como negativas, **exceto** «duplicada» e «dados ruins» (não dizem nada sobre preferência).
3. **Prontidão**: ≥ 50 triagens, ≥ 10 positivas e ≥ 10 negativas; por perfil, ≥ 15 para propor pesos. Abaixo disso o relatório mostra
   os números, avisa e não propõe.
4. **Por fator e perfil**: média nas duas classes e **AUC** (chance de um interessante ter fator maior que um descartado; 0,5 = não separa).
5. **Proposta**: peso novo ∝ peso atual × (AUC ÷ 0,5), limitado a ±25% por rodada e normalizado para somar 1 (ajuste gradual, nunca salto).
6. **Simulação retroativa** com a mesma fórmula do motor (`K × soma ponderada`): precisão do topo 10 e AUC do total, antes e depois. A
   proposta só é marcada «melhora» se o AUC sobe **e** a precisão do topo não cai (critério da E30). M3 depende do baseline manual e
   não entra na simulação.
7. **Nada é aplicado sozinho** (ADR-005/006): o humano edita `scoring/profiles.py`, sobe `SCORING_VERSION`, roda `make rescore` e
   registra a decisão em ADR.

## Consequências
- Rodar sem dados é seguro (devolve «não pronto»). Sobreajuste: a simulação usa a própria amostra, então com amostra pequena é pista,
  não prova; o relatório diz isso. Repetir a cada ~50 triagens novas.
- Triagens de leads (organizações) ainda não entram: só oportunidades. Estender quando houver desfecho de leads.
- Ideia aproveitada da análise do ZenonPB (`controlled-learning`): calibrar só com amostra mínima, com aprovação humana e versão gravada.
