# Plano de implementação

Cada etapa cabe em **uma sessão** do Claude Code (ciclo em `docs/operations/claude-workflow.md`).
Detalhes de cada etapa ficam no arquivo da fase. Estado atual: `STATUS.md`.

**IDs são estáveis** (não renumerar). Etapas inseridas depois recebem sufixo (`E01b`).
As fases são **agrupamentos temáticos**; a ordem de execução é a da seção abaixo.

## Ordem de execução recomendada (revisada em 2026-09-30)

Motivo da revisão: SESC é hipótese validada com propostas em andamento, a empresa é MEI,
há portfólio público e a janela escolar é out–dez → memória comercial e leads vêm antes do
radar de oportunidades (análise de impacto: `docs/history/sessions/2026-09-30-E00b.md`).

| # | Etapa | Marco |
|---|---|---|
| 1 | E01 Validação de fontes + baseline manual | |
| 2 | E01b Inventário do negócio e contas (portfólio, histórico SESC, MEI, Supabase, Gemini, GitHub Actions) | |
| 3 | E02 Esqueleto (Django + Postgres/Supabase + CI) | |
| 4 | E03 Modelo de dados núcleo | |
| 5 | E03b Memória comercial, portfólio e perfil da empresa | **M1: "Já falamos com eles?" respondido no admin** |
| 6 | E04 Infra de coleta | |
| 7 | E12 Municípios, polos e geografia contextual | |
| 8 | E17 Rede SESC-SP + escolas privadas (INEP) | |
| 9 | E17b Organizações parecidas com o SESC | |
| 10 | E18 Site oficial · 11. E19 Contatos institucionais | **M2: lista de instituições com contatos para a janela out–dez** |
| 12 | E20 Matching serviço ↔ organização ↔ portfólio | feita (ADR-027) |
| 13 | E05 Devpost (feita, ADR-028) · 14. E06 itch.io · 15. E07 páginas monitoradas (feita, ADR-030) · 16. E08 Querido Diário · 17. E09 Mapas Culturais | |
| 18 | E10 Camada de IA · 19. E11 Extração de oportunidades (inclui requisitos MEI) | **M3: radar de oportunidades** |
| 20 | E13 Score de oportunidades · 21. E21 Score de leads | |
| 22 | E14 Triagem e métricas · 23. E15 Digest (oportunidades, leads, follow-ups) · 24. E16 Agendamento (GitHub Actions) e backups | **M4: radar semanal automático** |
| 25 | E22 Avaliação do MVP (go/no-go) | |
| — | Fase 4 conforme E22 (E27 PNCP é a primeira candidata) | |

Ordem alternativa aceitável: radar (E05–E11) antes dos leads, se a janela escolar não for prioridade.

## Fases e etapas

### Fase 0 — Fundação → `fase-0-fundacao.md`
| ID | Etapa | Complexidade | IA em runtime |
|---|---|---|---|
| E00 | Planejamento, pesquisa e documentação (+ complemento E00b) | — | — |
| E01 | Validação de fontes + baseline manual (spike) | Baixa | Nenhuma |
| E01b | Inventário do negócio e contas | Baixa | Nenhuma |
| E02 | Esqueleto (uv, Django, Postgres/Supabase, ruff, pytest, CI, make) | Baixa | Nenhuma |
| E03 | Modelo de dados núcleo + admin básico + catálogo de serviços | Média | Nenhuma |
| E03b | Memória comercial (Interaction), portfólio, CompanyProfile, importação do histórico | Média | Nenhuma |
| E04 | Infra de coleta: PoliteFetcher, RawDocument, runner de conectores | Média | Nenhuma |

### Fase 1 — Radar de oportunidades → `fase-1-radar-oportunidades.md`
| ID | Etapa | Complexidade | IA em runtime |
|---|---|---|---|
| E05 | Conector Devpost (hackathons) | Baixa | Nenhuma |
| E06 | Conector itch.io (game jams) | Baixa | Nenhuma |
| E07 | Conector `html_watch` + páginas (FAPESP, ProAC, Oficinas Culturais, Sebrae-SP, InovAtiva, prefeituras dos polos) | Média | Nenhuma |
| E08 | Conector Querido Diário (polos e região) | Média | Nenhuma |
| E09 | Conector Mapas Culturais | Baixa | Nenhuma |
| E10 | Camada de IA (tarefas, estratégias, Gemini/Claude/local/regras, cache, custo, teto) | Média | Infra |
| E11 | Extração estruturada de oportunidades (inclui requisitos de empresa) | Alta | Gemini Flash-Lite → Flash → Haiku 4.5 |

### Fase 2 — Priorização → `fase-2-priorizacao.md`
| ID | Etapa | Complexidade | IA em runtime |
|---|---|---|---|
| E12 | Municípios IBGE, polos prioritários, distância, perfis geográficos | Baixa | Nenhuma |
| E13 | Score v1 de oportunidades (elegibilidade MEI) + breakdown no admin | Média | Nenhuma |
| E14 | Triagem humana, motivos de descarte e métricas | Baixa | Nenhuma |
| E15 | Digest semanal (oportunidades, leads, follow-ups, bloqueios por requisito, custos) | Baixa | Nenhuma |
| E16 | Agendamento no GitHub Actions, backups `pg_dump`, logs, runbook | Baixa | Nenhuma |

### Fase 3 — Leads institucionais → `fase-3-leads-institucionais.md`
| ID | Etapa | Complexidade | IA em runtime |
|---|---|---|---|
| E17 | Rede SESC-SP (unidades) + escolas privadas (INEP) | Média | Nenhuma |
| E17b | Organizações parecidas com o SESC (seed + páginas de chamamento) | Baixa | Nenhuma |
| E18 | Descoberta de site oficial (API de busca + validação; grounding Gemini como experimento) | Média | Nenhuma (opcional) |
| E19 | Extração de contatos públicos institucionais | Média | Nenhuma |
| E20 | Matching serviço ↔ organização ↔ portfólio por regras | Média | Opcional |
| E21 | Score de leads (relacionamento, portfólio, geo) | Baixa | Nenhuma |
| E22 | **Avaliação do MVP** (métricas, baseline, go/no-go) | Baixa | Nenhuma |

### Fase 4 — Pós-MVP (só após E22 positiva) → `fase-4-pos-mvp.md`
| ID | Etapa | Complexidade | IA em runtime |
|---|---|---|---|
| E27 | Conector PNCP (licitações — viável com MEI) — **1ª candidata** | Média | Reusa E11 |
| E23 | Pipeline leve (Deal/estágios sobre as interações) | Média | Nenhuma |
| E24 | Rascunho de abordagem assistido (com portfólio) | Média | A/B Claude Sonnet 5.5 × Gemini 3.1 Pro |
| E25 | Empresas via dados abertos do CNPJ | Alta | Nenhuma |
| E26 | Sinais de necessidade web | Média | Nenhuma |
| E28 | Agente de pesquisa sob demanda (condicional) | Alta | Gemini + grounding ou Claude Sonnet 5.5, com teto |
| E29 | UI online em `app.scorpionbits.com` (Django no Cloud Run) | Média | Nenhuma |
| E30 | Calibração de pesos com dados de triagem | Baixa | Nenhuma |

## Template de etapa

```markdown
## EXX — Nome
**Objetivo:** o que será construído.
**Resultado esperado:** como saberemos que terminou (observável).
**Ler antes:** documentos mínimos para executar.
**Alterações:** arquivos/componentes criados ou alterados.
**Dependências:** etapas anteriores.
**Modelo (desenvolvimento):** modelo do Claude Code sugerido para a sessão.
**IA em runtime:** modelo usado pelo sistema nesta funcionalidade (ou "nenhum").
**Justificativa do modelo:** por quê.
**Custo:** estimativa (desenvolvimento e runtime).
**Complexidade:** baixa/média/alta.
**Riscos:** o que pode dar errado.
**Testes:** como validar.
**Critério de conclusão:** checklist verificável.
```

"Modelo (desenvolvimento)": Sonnet 5.5 atende a maioria das etapas; Opus 5.5 é sugerido
onde há desenho de modelo de dados, extração com LLM ou avaliação (E03, E03b, E11, E13, E22,
E28). É sugestão — o humano escolhe no Claude Code.
