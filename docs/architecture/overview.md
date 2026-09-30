# Arquitetura — visão geral

## Decisão central

**Monólito modular em Python/Django**, rodando em uma única máquina, com SQLite no MVP
e jobs agendados por cron. (ADR-001, ADR-002)

Por quê: 1–3 usuários, volume de dados pequeno (milhares de registros, não milhões),
equipe mínima. O Django admin entrega listagem, filtros, busca, edição, autenticação e
histórico **sem escrever frontend** — é o "CRM/planilha estruturada" do MVP.
Python é a melhor linguagem para coleta, parsing de HTML/PDF e integração com LLMs.

## Diagrama

```text
                       ┌──────────────────────────── cron (semanal/diário) ──────────────────┐
                       │                                                                      │
 FONTES PÚBLICAS       ▼                                                                      │
 ┌───────────────┐  ┌─────────────────────────── collection/ ───────────────────────────┐    │
 │ APIs abertas  │  │  Connector registry ──► PoliteFetcher ──► RawDocument (cache, hash)│    │
 │ (Devpost, QD, │─►│   (1 classe/fonte)     robots.txt, UA, rate                        │    │
 │  Mapas, INEP) │  │                        limit/domínio, ETag                         │    │
 │ Páginas HTML  │  │        │ normaliza                                                 │    │
 │ (FAPESP,      │  │        ▼                                                           │    │
 │  Sebrae, ...) │  │  Candidate records (Opportunity / Organization) + dedupe           │    │
 │ Seeds CSV     │  └────────┬───────────────────────────────────────────────────────────┘    │
 │ (SESC)        │           │                                                                │
 │ Busca web     │           ▼                                                                │
 │ (cota grátis) │  ┌────────────────── extraction/ ──────────────────┐   ┌──── llm/ ──────┐   │
 └───────────────┘  │ HTML/PDF → texto                                │──►│ Provider iface │   │
                    │ Regras/regex (datas, valores, contatos)         │   │ cache por hash │   │
                    │ LLM só p/ campos não estruturados + verificação │◄──│ log de custo   │   │
                    │   de evidência (citação existe no texto?)       │   │ teto mensal    │   │
                    └────────┬────────────────────────────────────────┘   │ Gemini/Groq/   │   │
                             ▼                                            │ Ollama/Claude  │   │
                    ┌──────────────────── core/ (SQLite) ─────────────┐   └────────────────┘   │
                    │ Organization  Opportunity  ContactPoint         │                        │
                    │ Evidence (observed | inferred, fonte, trecho)   │                        │
                    │ ServiceOffering (catálogo como dado)            │                        │
                    │ Match (org ↔ serviço + razões)  TriageStatus    │                        │
                    └────────┬────────────────────────────────────────┘                        │
                             ▼                                                                 │
                    ┌──────────────────── scoring/ ───────────────────┐                        │
                    │ geo (IBGE + distância + perfil por tipo)        │                        │
                    │ gates (prazo, elegibilidade) → fatores → score  │                        │
                    │ ScoreBreakdown salvo ("por que 87/100")         │                        │
                    └────────┬────────────────────────────────────────┘                        │
                             ▼                                                                 │
             ┌───────────────┴──────────────┐                                                  │
             ▼                              ▼                                                  │
   Django admin (triagem humana)   reports/ digest semanal (HTML/MD, e-mail p/ equipe) ◄───────┘
             │
             ▼
   Humano decide e contata  (Fase 4: pipeline leve + rascunho de mensagem assistido)
```

## Módulos (apps Django)

| Módulo | Responsabilidade | Depende de |
|---|---|---|
| `core` | Entidades, evidências, catálogo de serviços, admin | — |
| `collection` | Fetcher educado, cache, conectores, execuções de coleta | `core` |
| `extraction` | Texto de HTML/PDF, regras, extração estruturada | `core`, `llm` |
| `llm` | Interface de provedores, cache, custo, orçamento | — |
| `scoring` | Geo, gates, fatores, perfis, breakdown | `core` |
| `reports` | Digest semanal, métricas | `core`, `scoring` |
| `pipeline` (Fase 4) | Estágios, interações, opt-out | `core` |

Regra: dependências apontam para `core`. `llm` não conhece o domínio (recebe prompt +
schema, devolve JSON validado).

## Decisões transversais

| Tema | Decisão MVP | Evolução |
|---|---|---|
| Frontend | Django admin customizado (list_display, filtros, ações) | Views HTMX pontuais se o admin limitar |
| Banco | SQLite WAL, backups por cópia de arquivo | PostgreSQL no deploy compartilhado (E29) |
| Filas/workers | Nenhum; comandos `manage.py` sequenciais via cron | `django-q2`/Huey (sem Redis) se jobs > 30 min ou precisarem de paralelismo |
| Scheduler | cron / systemd timer / Agendador do Windows | Mesmo no VPS |
| Armazenamento de documentos | Diretório `data/raw/` (conteúdo por hash) + metadado no banco | Objeto S3-compatível barato se passar de alguns GB |
| Busca web | API com cota gratuita (Brave/Serper), cache permanente por query | Troca de provedor via interface |
| Scraping | Fetch simples e educado; sem navegador headless no MVP | Playwright só para fonte valiosa que exija JS |
| Cache | Cache HTTP por URL (ETag/hash), cache LLM por hash(prompt+modelo+versão), cache de busca por query | — |
| Dedupe | Chave canônica por tipo (URL canônica, CNPJ, código INEP, título+org+prazo normalizados) | Similaridade fuzzy se aparecerem duplicatas reais |
| Autenticação | Usuários do Django; rodando local | Deploy com HTTPS + senha forte + 2FA via proxy (E29) |
| Observabilidade | `logging` estruturado para arquivo + tabela `CollectionRun` + `LLMCall` | Sentry free tier se houver deploy |
| Erros | Cada conector isolado: falha de uma fonte não derruba as outras; erro registrado no run | Alerta no digest ("fonte X falhou 3x") |
| Segurança | Segredos em `.env`; nenhum dado pessoal sensível; admin não exposto na internet no MVP | Ver E29 |
| Custos | Teto mensal configurável na camada `llm` e na de busca; bloqueia ao atingir | Relatório de custo no digest |

## Quando separar serviços (e por quê não agora)

Só considerar separar algo do monólito quando **um** destes for medido:

1. A coleta precisa rodar em horário/máquina diferente da UI (ex.: UI no VPS, coleta
   pesada de CNPJ em máquina local) → separar **só o worker**, mesmo código, mesmo banco.
2. Uma fonte exige navegador headless pesado → worker isolado para ela.
3. Mais de ~5 usuários simultâneos ou acesso externo → Postgres + deploy dedicado.

Nenhum desses se aplica ao MVP.
