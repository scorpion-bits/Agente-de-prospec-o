# Pontuação explicável

## Pergunta que o score responde

> **"Vale a pena a Scorpion Bits gastar tempo nisso — e mais do que naquilo?"**

Não é "quão bom é o lead" em abstrato; é **retorno esperado, ajustado por chance,
esforço, tempo e confiança nos dados**.

## Princípios

1. **Determinístico** (mesma entrada → mesmo score). LLM **não** dá nota; no máximo extrai
   insumos (ex.: valor do prêmio), que entram como `Evidence` rastreável.
2. **Explicável**: cada ponto vem de um fator com texto e evidências ligadas.
3. **Perfis por tipo**: pesos diferentes para edital, hackathon, escola, SESC, empresa.
4. **Gates antes de pontos**: o que é impossível não compete com o que é possível.
5. **Dados incertos puxam o score para baixo**, não para cima.
6. **Versionado e recalculável**: mudar pesos = nova `scoring_version`, recalcula tudo.
7. **Calibrado pelo uso**: triagem humana (interessante/descartado) ajusta pesos (E30).

## Etapa 1 — Gates (eliminatórios)

| Gate | Aplica a | Resultado |
|---|---|---|
| Prazo vencido | Oportunidades | `gated`, some do digest |
| Território inelegível (ex. "só proponentes do RJ") | Oportunidades | `gated` |
| Público inelegível explícito (ex. "somente universidades públicas") | Oportunidades | `gated` |
| Requisito explícito da empresa não atendido pelo `CompanyProfile` (ex.: "não aceita MEI", CNPJ/sede com menos tempo que o mínimo na data do prazo) | Oportunidades | `gated` com motivo "bloqueado por requisito da empresa" (vai para seção própria do digest) |
| Organização/contato em `Suppression` ou `relationship_status=do_not_contact` | Leads | `gated` |
| Contato recente (última interação < 21 dias, sem próxima ação vencida) | Leads | Sai da lista de "novos contatos"; aparece só em "em andamento" |
| Duplicata | Todos | `gated` |
| Já descartado pelo humano | Todos | Fora do digest (não recalcula) |

**Elegibilidade da empresa (ADR-013).** A Scorpion Bits é **MEI**. Não é gate, mas alerta +
ajuste de Chance: requisito ambíguo ("pessoa jurídica" sem especificar), CNAE que precisaria
ser incluído no MEI, valor acima do limite anual do MEI ("exigiria migrar para ME").
**Bônus** de Chance: cota exclusiva ME/EPP/MEI. O digest soma o valor das oportunidades
bloqueadas por requisito da empresa — insumo para decisões de negócio (quando virar ME, que
CNAE incluir).

**Cobertura de atividade (ADR-015).** Serviço do match com `mei_coverage=not_covered` (software, web,
sites) → alerta "exigiria ME" e redução de Chance; `verify` → alerta leve; `covered` (cursos, oficinas,
treinamento em informática) → sem alerta. O digest soma o valor potencial que depende de serviços
não cobertos ("receita que exigiria ME").

**Memória comercial (ADR-012).** Organizações já contatadas nunca aparecem como novas.
Leads com `next_action_at` vencendo ou vencido aparecem na seção **"Follow-ups"** do digest,
com o resumo da última interação.

## Etapa 2 — Fatores (cada um de 0 a 1)

| Fator | Significado | Insumos (exemplos) |
|---|---|---|
| **V — Valor** | Retorno potencial | Prêmio/valor em R$ (faixas), tipo de benefício (dinheiro/contrato > clientes/parceria > visibilidade/networking/portfólio), ticket típico do serviço |
| **F — Fit** | Compatibilidade com o que sabemos fazer | Força do `Match` (categorias, palavras-chave, CNAE, tipo de organização) + **existe item de portfólio que prova a capacidade** (ex.: Game Lab SESC para cursos; AstroDash/Tirania para jogos) |
| **C — Chance** | Probabilidade de sucesso | Elegibilidade vs. `CompanyProfile` (MEI), cota exclusiva ME/EPP/MEI ↑, concorrência provável (nacional aberto ↓, local ↑), **relacionamento**: mesma rede de quem já nos contratou (SESC) ↑↑, resposta positiva anterior ↑, "perdido" recente ↓ |
| **T — Timing** | Janela certa | Prazo: <5 dias ↓ (inviável), 7–45 dias ↑, >90 dias médio; sazonalidade (escolas: out–dez ↑; SESC: planejamento semestral — confirmar na E01b); follow-up vencendo ↑ |
| **A — Acesso** | Dá para chegar lá / falar com eles | Relevância geográfica `G` (ver `geo-relevance.md`) × contatabilidade (e-mail/telefone institucional ↑, só formulário ↓, nada ↓↓) |
| **L — Leveza** | Inverso do esforço | `effort_estimate`: low 1,0 · medium 0,6 · high 0,25 · unknown 0,5 |

Cada fator devolve `(valor, explicação, evidence_ids)`. Fator sem dado → valor neutro
0,5 e explicação "sem dado".

## Etapa 3 — Confiança

`K = 0,7 + 0,3 × q`, onde `q` = fração dos fatores sustentados por evidência
`observed`/`manual` (inferência conta 0,5; ausência conta 0). Resultado: dados fracos
reduzem até 30% do score.

## Fórmula

```
Score = round(100 × K × Σ wᵢ·fᵢ)         (Σ wᵢ = 1 por perfil)
```

### Pesos iniciais por perfil (hipótese — calibrar com dados)

| Fator | `opp.edital` | `opp.hackathon_jam` | `opp.event` | `lead.school_course` | `lead.sesc` | `lead.company_service` |
|---|---|---|---|---|---|---|
| V Valor | 0,30 | 0,20 | 0,15 | 0,25 | 0,25 | 0,25 |
| F Fit | 0,20 | 0,25 | 0,20 | 0,25 | 0,20 | 0,25 |
| C Chance | 0,15 | 0,15 | 0,10 | 0,20 | 0,25 | 0,15 |
| T Timing | 0,15 | 0,15 | 0,20 | 0,10 | 0,10 | 0,05 |
| A Acesso | 0,05 | 0,10 | 0,25 | 0,15 | 0,15 | 0,20 |
| L Leveza | 0,15 | 0,15 | 0,10 | 0,05 | 0,05 | 0,10 |

Racional: editais valem pelo dinheiro; jams pelo fit e baixo esforço; eventos presenciais
pelo acesso; escolas/SESC pela chance e valor recorrente; empresas pelo fit e acesso.
O perfil `lead.sesc` também vale para organizações parecidas com o SESC (`similarity_tags`),
com Chance menor que as unidades SESC (sem o case direto). SESC é hipótese **validada**
(curso realizado + propostas enviadas) — por isso Chance tem o maior peso nesse perfil.

## Faixas de decisão

| Score | Rótulo | Ação sugerida |
|---|---|---|
| ≥ 75 | **Priorizar** | Agir nesta semana |
| 55–74 | **Avaliar** | Olhar no digest; decidir |
| 35–54 | **Baixa** | Só se sobrar tempo |
| < 35 | **Ignorar** | Fora do digest |

## Exemplo de breakdown (responde "por que recebeu N/100?")

```
Edital "PIPE Fase 1 — Soberania Digital" (FAPESP)          Perfil: opp.edital  v1
  V Valor   0,95 × 0,30 = 28,5   até R$ 500 mil não reembolsável (observado: fapesp.br, 20/05/2026)
  F Fit     0,80 × 0,20 = 16,0   categorias software/inovação ↔ serviço "software sob demanda"
  C Chance  0,55 × 0,15 =  8,3   concorrência estadual; ⚠ aceita MEI? não explícito no edital
  T Timing  0,90 × 0,15 = 13,5   prazo em 32 dias (janela ideal)
  A Acesso  0,80 × 0,05 =  4,0   estadual SP, Araraquara elegível
  L Leveza  0,25 × 0,15 =  3,8   esforço alto (proposta técnica + plano de negócios) [inferido]
  Soma 0,741 · K = 0,7 + 0,3×0,92 = 0,976  →  Score 72 (Avaliar)
```
(Números ilustrativos: mostram o formato, não um dado real.)

## Implementação (E13 oportunidades — ADR-035; E21 leads — ADR-039)

- `scoring/factors/{value,fit,chance,timing,access,lightness}.py`: uma função por fator, pura, testável.
- `scoring/eligibility.py` (requisitos × `CompanyProfile`), `scoring/gates.py`, `scoring/engine.py` (`score_opportunity`, `combine`).
- `scoring/profiles.py`: pesos, faixas e mapa tipo→perfil como dados, com `SCORING_VERSION`.
- `Score.breakdown` guarda as linhas `{factor, label, raw, weight, points, explanation, evidence_ids, support}`; o admin as mostra.
- `manage.py rescore [--profile X] [--limit N] [--dry-run]` (`make rescore`).
- **Valores iniciais dos fatores (hipótese, v1):** V por faixa de prêmio (≥ R$ 250 mil 0,95 · 100 mil 0,85 · 30 mil 0,7 · 10 mil
  0,55 · 3 mil 0,4 · abaixo 0,3; sem valor, melhor benefício 0,3–0,6); F 0,6–0,9 por palavra-chave do serviço, 0,45 só por
  categoria, 0,2 sem relação, +0,1 com portfólio público; C base 0,5 ± elegibilidade, abrangência e relacionamento; T por dias até
  o prazo (≤ 4: 0,1 · 5–6: 0,5 · 7–14: 0,85 · 15–45: 0,95 · 46–90: 0,7 · > 90: 0,5); A = `G` × contatabilidade (e-mail/telefone
  1,0 · página oficial 0,8 · formulário 0,7 · nada 0,3); L pelo esforço.
- **Leads (E21):** `scoring/leads.py` e `scoring/factors/lead.py`; mesmo `combine`, perfis `lead.sesc`/`lead.school_course`. Opt-out
  → `gated`; já contatado ou contato < 21 dias → rótulo «em andamento» (tem nota, nunca é lead novo). Detalhes e valores em ADR-039.
- **Fora do MVP:** frescor de evidência (E22/E30); perfil `lead.company_service`; duplicata de oportunidade já é barrada pela `canonical_key`.

## Calibração (E30)

Com ≥ 50 itens triados: comparar distribuição de fatores entre "interessante" e
"descartado"; ajustar pesos manualmente (ou regressão logística simples como sugestão)
e registrar a mudança em ADR. Não automatizar ajuste de pesos no MVP.
