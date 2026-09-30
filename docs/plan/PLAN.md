# Plano de implementação

Cada etapa cabe em **uma sessão** do Claude Code (ciclo em `docs/operations/claude-workflow.md`).
Detalhes completos de cada etapa ficam no arquivo da fase. Estado atual: `STATUS.md`.

## Fases e etapas

### Fase 0 — Fundação → `fase-0-fundacao.md`
| ID | Etapa | Complexidade | IA em runtime |
|---|---|---|---|
| E00 | Planejamento, pesquisa e documentação | — | — |
| E01 | Validação de fontes + baseline manual (spike) | Baixa | Nenhuma |
| E02 | Esqueleto do projeto (uv, Django, ruff, pytest, CI, make) | Baixa | Nenhuma |
| E03 | Modelo de dados núcleo + admin básico + catálogo de serviços | Média | Nenhuma |
| E04 | Infra de coleta: PoliteFetcher, RawDocument, runner de conectores | Média | Nenhuma |

### Fase 1 — Radar de oportunidades (MVP-A) → `fase-1-radar-oportunidades.md`
| ID | Etapa | Complexidade | IA em runtime |
|---|---|---|---|
| E05 | Conector Devpost (hackathons) | Baixa | Nenhuma |
| E06 | Conector itch.io (game jams) | Baixa | Nenhuma |
| E07 | Conector genérico `html_watch` + primeiras páginas (FAPESP, ProAC, Sebrae-SP…) | Média | Nenhuma |
| E08 | Conector Querido Diário (diários oficiais da região) | Média | Nenhuma |
| E09 | Conector Mapas Culturais | Baixa | Nenhuma |
| E10 | Camada `llm/` (provedores, cache, custo, teto, FakeProvider) | Média | Infra |
| E11 | Extração estruturada de oportunidades com verificação de citação | Alta | Gemini Flash-Lite free → Haiku 4.5 |

### Fase 2 — Priorização (MVP-B) → `fase-2-priorizacao.md`
| ID | Etapa | Complexidade | IA em runtime |
|---|---|---|---|
| E12 | Municípios IBGE, distância e perfis geográficos | Baixa | Nenhuma |
| E13 | Scoring v1 de oportunidades + breakdown no admin | Média | Nenhuma |
| E14 | Triagem humana, motivos de descarte e métricas básicas | Baixa | Nenhuma |
| E15 | Digest semanal (HTML/Markdown; e-mail opcional para a equipe) | Baixa | Nenhuma |
| E16 | Agendamento, backups, logs e runbook de operação | Baixa | Nenhuma |

### Fase 3 — Leads institucionais (MVP-C) → `fase-3-leads-institucionais.md`
| ID | Etapa | Complexidade | IA em runtime |
|---|---|---|---|
| E17 | Importação de escolas privadas (INEP) + lista semente SESC-SP | Média | Nenhuma |
| E18 | Descoberta de site oficial (API de busca + validação) | Média | Nenhuma (desempate opcional) |
| E19 | Extração de contatos públicos institucionais | Média | Nenhuma |
| E20 | Matching serviço ↔ organização por regras | Média | Opcional (justificativa curta) |
| E21 | Score de leads + digest integrado | Baixa | Nenhuma |
| E22 | **Avaliação do MVP** (métricas, baseline, decisão go/no-go) | Baixa | Nenhuma |

### Fase 4 — Pós-MVP (só após E22 positiva) → `fase-4-pos-mvp.md`
| ID | Etapa | Complexidade | IA em runtime |
|---|---|---|---|
| E23 | Pipeline leve (negócios, interações, follow-up, opt-out na UI) | Média | Nenhuma |
| E24 | Rascunho de abordagem assistido | Média | Claude Sonnet 5.5 |
| E25 | Empresas via dados abertos do CNPJ (região + CNAEs) | Alta | Nenhuma |
| E26 | Sinais de necessidade web (site ausente, sem HTTPS, não responsivo) | Média | Nenhuma |
| E27 | Conector PNCP (contratações públicas) | Média | Reusa E11 |
| E28 | Agente de pesquisa sob demanda (condicional) | Alta | Claude Sonnet 5.5 com teto |
| E29 | Deploy compartilhado (VPS, PostgreSQL, HTTPS, backups) | Média | Nenhuma |
| E30 | Calibração de pesos com dados de triagem | Baixa | Nenhuma |

## Ordem e paralelismo

```
E01 → E02 → E03 → E04 ─┬─► Fase 1 (E05…E11) ─┐
                       │                      ├─► E13 → E14 → E15 → E16 ─► E21 → E22 → Fase 4
                       ├─► E12 ───────────────┤
                       └─► Fase 3 (E17…E20) ──┘
```

**Ordem alternativa (recomendada se a janela escolar out–dez for prioridade):**
E01–E04 → E12 → E17 → E18 → E19 → E20 → (E13 adaptado a leads) → Fase 1 → restante.
A decisão é do humano; registrar em STATUS.

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

Sobre "Modelo (desenvolvimento)": Sonnet 5.5 atende a maioria das etapas mecânicas;
Opus 5.5 é sugerido onde há desenho de modelo de dados, extração com LLM ou avaliação
(E03, E11, E13, E22, E28). É sugestão — o humano escolhe no Claude Code.
