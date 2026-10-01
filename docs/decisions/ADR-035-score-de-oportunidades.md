# ADR-035 — Score de oportunidades: gates, fatores, confiança e pesos como dado versionado

- **Status:** aceito
- **Data:** 2026-10-01

## Contexto
Com a extração da E11 (prazo, requisitos de empresa, prêmio, esforço) e a geografia da E12, a E13 responde
«o que fazer primeiro, e por quê?» para oportunidades. O desenho está em `docs/architecture/scoring.md` (ADR-006);
aqui ficam as escolhas de implementação que o documento deixava abertas.

## Decisão
1. **`scoring.Score`** (migration `scoring.0001`): uma linha por entidade (relação genérica, ADR-017), com `profile`,
   `scoring_version`, `total` (nulo se barrada), `label`, `confidence`, `gate_kind`/`gate_reason`, `breakdown` (JSON),
   `alerts`. Duas constraints no banco: `total` entre 0 e 100 e «barrada ⇔ sem total».
2. **Determinístico e sem IA**: `scoring/engine.py` = gates → seis fatores (`scoring/factors/`) → `K` → `round(100·K·Σwᵢfᵢ)`.
   Pesos, faixas e o mapa tipo→perfil ficam em `scoring/profiles.py` (dado); mudar = subir `SCORING_VERSION` e rodar `rescore`.
3. **Perfis de oportunidade**: `opp.edital` (edital, programa, concurso, licitação, chamada), `opp.hackathon_jam`, `opp.event`
   (evento e «outro»). Leads (`lead.*`) ficam para a E21.
4. **Gates** (ordem fixa): prazo vencido (ou evento que já ocorreu, ou «encerrada» sem prazo) → território elegível
   (`eligible_regions`, via `scoring/geo.py`) → requisito da empresa (natureza jurídica não aceita; idade mínima na **data do
   prazo**). Barrada = sem total, com motivo e `gate_kind` (o digest soma o valor de `company_requirement`).
   Requisito desconhecido nunca barra (ADR-004). Oportunidade **descartada na triagem** não é recalculada.
5. **Elegibilidade (ADR-013/015) só alerta e ajusta a Chance**, nunca barra: exige PJ sem dizer naturezas (−0,10), CNAE exigido
   fora do perfil (−0,15), prêmio acima do limite do MEI (−0,15; usa `annual_revenue_cap_brl` ou R$ 81 mil), serviço do fit
   «exigiria ME» (−0,20) ou «verificar» (−0,05); cota ME/EPP/MEI = +0,20.
6. **Fit usa o catálogo como dado**: palavras-chave do `ServiceOffering` no texto (0,6 + 0,1 por palavra extra, máx. 0,9),
   senão categoria/tipo da oportunidade (0,45), senão 0,2; **+0,1 se há portfólio público e confirmado** que prova o serviço.
7. **Confiança**: `q` = média, por fator, de 1 (evidência observada/manual), 0,5 (inferida), 0 (nenhuma ou fator sem dado);
   `K = 0,7 + 0,3·q`. Dado fraco só **reduz** a nota (até 30%).
8. **Admin**: coluna «pontuação» ordenável na lista de oportunidades, painel «por que essa nota» (uma linha por fator, com
   evidências) e lista de `Score` somente leitura. `make rescore` / `manage.py rescore [--profile] [--limit] [--dry-run]`.

## Consequências
+ Explicável linha a linha; recalcular é barato e idempotente; sem custo de IA.
− Pesos, faixas de prêmio e prazo e os ajustes de Chance são **hipóteses** sem dado real; calibrar na E22/E30 com a triagem da E14.
− Fit por palavra-chave é grosseiro (sinônimos fora do catálogo viram 0,2): ajustar `keywords` no admin antes de mexer em código.
− Uma linha por entidade: o histórico de notas não é guardado (basta a `scoring_version` da última rodada).
