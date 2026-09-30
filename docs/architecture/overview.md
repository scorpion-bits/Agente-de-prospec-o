# Arquitetura — visão geral

## Decisões centrais

- **Monólito modular em Python/Django** (ADR-001). O Django admin é a UI do MVP.
- **PostgreSQL no Supabase** desde o início; **workers Python agendados no GitHub Actions**;
  admin rodando localmente no MVP; UI online depois em `app.scorpionbits.com` (ADR-010).
- **IA por tarefa**, com "sem IA" como padrão e Gemini como provedor principal de extração (ADR-003, ADR-011).
- **Memória comercial** (interações, relacionamento) e **portfólio** no núcleo (ADR-012).
- **Elegibilidade pelo perfil da empresa (MEI)** (ADR-013).

Por quê: 1–3 usuários, volume pequeno, equipe mínima, custo ≈ zero, sem lock-in
(Postgres puro + container). Python é o melhor ecossistema para coleta, HTML/PDF e LLMs.

## Diagrama

```text
                          ┌──────────── GitHub Actions (cron diário + manual) ────────────┐
                          │  run_pipeline: collect → extract → match → rescore → digest   │
                          │  backup: pg_dump semanal → artefato                            │
                          └───────────────┬───────────────────────────────────────────────┘
 FONTES PÚBLICAS                          │ (mesmo código roda na máquina do dev)
 ┌──────────────────┐   ┌─────────── collection/ ───────────┐
 │ APIs abertas     │──►│ conectores → PoliteFetcher        │  UA: RadarScorpionBits (+scorpionbits.com)
 │ (Devpost, QD,    │   │ robots.txt, rate limit, ETag      │
 │  Mapas, INEP,    │   │ RawDocument (hash, URL, texto gz) │
 │  PNCP*)          │   └──────────────┬────────────────────┘
 │ Páginas oficiais │                  ▼
 │ Seeds (SESC,     │   ┌─────────── extraction/ ───────────┐     ┌──────── llm/ ────────┐
 │  similares,      │   │ texto HTML/PDF · regex · regras   │────►│ tarefa → estratégia  │
 │  portfólio)      │   │ LLM só no texto livre + citação   │◄────│ rules | gemini |     │
 │ Busca (cota)     │   │ verificada                        │     │ claude | local       │
 └──────────────────┘   └──────────────┬────────────────────┘     │ cache·custo·teto     │
                                       ▼                          └──────────────────────┘
        ┌────────────── Supabase PostgreSQL (schema do Django) ─────────────────────┐
        │ Organization (rede/unidade, status de relacionamento)  ContactPoint       │
        │ Interaction (memória comercial)   Opportunity   Evidence (observed|inferred)│
        │ ServiceOffering ─ PortfolioItem   Match (org↔serviço↔portfólio)  Score     │
        │ CompanyProfile (MEI)   Triage   Suppression   LLMCall   SearchQuery        │
        └──────────────┬──────────────────────────────────────┬─────────────────────┘
                       ▼                                      ▼
        scoring/ (geo contextual, elegibilidade,     reports/ digest semanal
        gates, fatores, confiança, breakdown)        (top oportunidades, leads,
                       │                              follow-ups, prazos, custos)
                       ▼
        Django admin (local no MVP; Cloud Run em app.scorpionbits.com depois)
                       ▼
        Humano decide e contata → registra Interaction
```
`*` PNCP na Fase 4.

## Módulos (apps Django)

| Módulo | Responsabilidade | Depende de |
|---|---|---|
| `core` | Entidades, evidências, catálogo de serviços, portfólio, interações, perfil da empresa, admin | — |
| `collection` | Fetcher educado, conectores, execuções de coleta | `core` |
| `extraction` | Texto de HTML/PDF, regras, extração estruturada | `core`, `llm` |
| `llm` | Tarefas de IA com estratégias intercambiáveis, provedores, cache, custo, teto | — |
| `scoring` | Geo, elegibilidade, gates, fatores, perfis, matching | `core` |
| `reports` | Digest, métricas | `core`, `scoring` |
| `pipeline` (Fase 4) | Estágios de negócio, funil | `core` |

## Decisões transversais

| Tema | MVP | Evolução |
|---|---|---|
| Frontend | Django admin local | Django no Cloud Run (`app.scorpionbits.com`); Next.js/Vercel Pro + Supabase Auth só se houver usuários não técnicos |
| Banco | Supabase Postgres Free (projetos dev e prod), via pooler | Supabase Pro (US$ 25) quando backups gerenciados/sem pausa forem necessários |
| Exposição do Supabase | Data API desativada / schema dedicado; só o Django acessa | RLS explícito se um frontend usar o cliente Supabase |
| Jobs | `run_pipeline` no GitHub Actions (cron) ou local | Worker separado só se jobs > 1 h |
| Scheduler | GitHub Actions `schedule` + `workflow_dispatch` (fallback: cron externo/local) | — |
| Documentos brutos | Não guardados; URL + hash + ETag + texto extraído comprimido, com retenção | Supabase Storage/S3 se necessário |
| Busca web | API com cota grátis (Brave/Serper) + cache permanente; grounding Gemini como experimento | — |
| Scraping | Fetch simples e educado; sem headless | Playwright só para fonte valiosa com JS |
| Cache | ETag/hash por URL; LLM por hash (conteúdo+prompt+modelo); busca por query | — |
| Dedupe | Chaves canônicas (URL, CNPJ, INEP, domínio, nome+município) + consulta à memória comercial | Fuzzy se necessário |
| Auth | Local: usuários Django | Online: Django auth + HTTPS; opcional camada extra (Cloudflare Access/IAP) |
| Observabilidade | Logs do job no GitHub Actions + `CollectionRun` + `LLMCall` | Sentry free tier |
| Erros | Conector isolado; falha registrada; alerta no digest | — |
| Segredos | `.env` local; GitHub Secrets nos workers | Secret Manager no Cloud Run |
| Backups | `pg_dump` semanal → artefato do GitHub Actions + cópia local | Backups do Supabase Pro |
| Custos | Teto mensal na camada `llm/` e de busca | Relatório no digest |

## Quando separar serviços

Só com gatilho medido: jobs que não cabem no GitHub Actions (> 1 h ou headless pesado) →
worker dedicado (mesmo código/banco); usuários não técnicos → UI online; muitos usuários
ou dados → Supabase Pro/infra dedicada. Nenhum se aplica ao MVP.
