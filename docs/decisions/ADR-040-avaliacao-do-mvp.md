# ADR-040 — Avaliação do MVP: relatório do banco, sugestão por regras, decisão humana

- **Status:** aceito
- **Data:** 2026-10-03

## Contexto
A E22 decide, com números, se o sistema vale o investimento contínuo (`docs/plan/fase-3-leads-institucionais.md`). Exige ≥ 4 semanas
de uso real com triagem semanal, que ainda não existem: o código da E22 só prepara a avaliação. A decisão é do humano (ADR-005) e o
repositório é público (ADR-014).

## Decisão
1. **`reports/evaluation.py` + `make evaluate`** (reaproveita `reports.metrics`, sem IA, sem rede, sem migration): grava
   `data/evaluations/AAAA-MM-DD.md` (pasta ignorada pelo git) com prontidão, M1–M9, custos e a sugestão. `DRY=1` imprime.
   `M3=n` e `M6=min` preenchem as duas métricas autodeclaradas (novidade vs. baseline manual; tempo de triagem).
2. **Prontidão**: ≥ 28 dias desde a primeira coleta real ou triagem **e** ≥ 20 triagens decididas. Sem isso a sugestão é sempre
   **estender** (pouco uso → estender o período em vez de decidir no escuro).
3. **Sugestão por regras** (só sugestão; a decisão é humana e vai em ADR):
   - **Parar**: M1, M2 e M4 (valor entregue) todas abaixo da meta.
   - **Estender**: não pronto, ou alguma entre M1, M2, M4 sem dados.
   - **Ajustar**: M1, M2, M4 com dados e qualquer métrica com dados abaixo da meta (M5, M7, M9, e M3/M6 se informadas).
   - **Continuar**: M1, M2 e M4 na meta e nenhuma outra com dados abaixo dela; vale seguir para a Fase 4, E27 (PNCP) primeiro.
   Metas são as de `docs/product/metrics.md`.
4. **Relatório final** (`docs/history/mvp-evaluation.md`) é escrito pelo humano na hora da decisão, a partir do arquivo gerado, com o
   baseline manual (E01, `docs/research/baseline-manual.md`, ainda pendente), casos de sucesso e fracasso e a decisão; sem dados
   pessoais. O arquivo no repositório é só o modelo, marcado «pendente».

## Consequências
- Rodar `make evaluate` antes das 4 semanas é seguro: devolve «estender» com os motivos.
- Sem o baseline da E01, M3 fica «sem dados» e não bloqueia «continuar»; M1, M2 e M4 sem dados mantêm «estender».
- Metas e regras são hipóteses; ajustar aqui e em `metrics.md` se a primeira avaliação mostrar que são frouxas ou rígidas.
