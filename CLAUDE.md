# CLAUDE.md — Radar Scorpion Bits

> Contexto operacional de alta prioridade. **Limite: 150 linhas (~2.000 tokens).**
> Se passar do limite, siga `docs/operations/claude-md-maintenance.md` antes de continuar.

## O que é

Plataforma **interna** da Scorpion Bits (estúdio de jogos/tecnologia em estágio inicial,
Araraquara/SP) para **encontrar, qualificar e priorizar** oportunidades comerciais
(escolas, SESCs, empresas, instituições) e institucionais (editais, hackathons,
game jams, programas). Pergunta central: **"o que devemos fazer primeiro, e por quê?"**

Visão completa: `docs/product/vision.md` · MVP: `docs/product/mvp.md`

## Ritual de início de sessão (obrigatório após /clear)

1. Leia este arquivo.
2. Leia `docs/plan/STATUS.md` → identifica a **próxima etapa** (ex.: `E03b`).
3. Abra a seção dessa etapa no arquivo de fase indicado em `docs/plan/PLAN.md`.
4. Leia **só** os documentos que a etapa lista em "Ler antes". Não leia tudo.
5. Execute **uma** etapa. Não avance para a seguinte sem o humano pedir.

## Ritual de fim de etapa (obrigatório)

1. `make check` passando.
2. Atualize `docs/plan/STATUS.md` (concluído, próxima etapa, problemas abertos).
3. Registre decisões questionáveis como ADR em `docs/decisions/`.
4. Registre o resumo da sessão em `docs/history/sessions/AAAA-MM-DD-EXX.md`.
5. Verifique o tamanho deste arquivo (`wc -l CLAUDE.md` ≤ 150).
6. Commit com mensagem clara referenciando a etapa (ex.: `E03: modelo de dados núcleo`).

## Princípios inegociáveis

1. **Custo primeiro.** Sem IA quando código, SQL, regex ou heurística resolvem.
   Ordem de preferência: determinístico → modelo gratuito/local → modelo barato → modelo forte.
   Ver `docs/architecture/llm-strategy.md`.
2. **Nada inventado.** Todo dado tem fonte (URL, data, trecho). Separe sempre
   **fato observado** (`kind=observed`) de **inferência** (`kind=inferred`). Ver ADR-004.
3. **Humano no controle.** O sistema recomenda; humano decide e contata. Sem envio
   automático de mensagens no MVP. Ver ADR-005.
4. **Prospecção responsável.** Respeitar robots.txt, termos de uso, LGPD, opt-out.
   Preferir contatos institucionais. Sem scraping de LinkedIn/Google Maps.
   Ver `docs/research/legal-and-compliance.md`.
5. **Pontuação explicável.** Todo score guarda o detalhamento ("por que 87/100").
   Ver `docs/architecture/scoring.md`.
6. **Pequeno e incremental.** Monólito modular. Sem microserviços, filas distribuídas,
   vector DB ou multi-agentes antes de haver necessidade medida.

## Stack (decidida — ADR-001, ADR-010, ADR-011, ADR-019)

- Python 3.12 · gerenciador `uv` · Django 5.2 (ORM, migrations, **admin como UI do MVP**, auth)
- PostgreSQL no **Supabase** (`radar-dev`/`radar-prod`, pooler em modo sessão); tabelas no schema `radar` (ADR-016)
- Jobs: comandos `manage.py`, agendados no **GitHub Actions** (sem fila, sem servidor)
- UI do MVP: Django admin **local**. UI futura: **web** (sem executável) que só fala com uma **API do
  Django**, no visual do site (ADR-019, `docs/product/ui-direction.md`). Sem Vercel no MVP (ADR-010)
- IA: camada `llm/` por **tarefa**, estratégias trocáveis (regras | Gemini | Claude | local);
  Gemini é o principal na extração; dados internos só em provedor pago (ADR-003, ADR-011)

## Estrutura

```
radar/            projeto Django (settings, urls)
tests/            testes (pytest); scripts/ verificações do repositório; Makefile; compose.yaml
core/             modelos núcleo em pacote `models/` (Organization, Opportunity, Evidence, Interaction…), admin,
                  services/ (evidência, opt-out, normalização), fixtures/ (catálogo de serviços)
collection/       fetcher educado, RawDocument, runner (`collect`), conectores em `connectors/`
extraction/       texto de HTML/PDF, extração estruturada (LLM opcional)
scoring/          geo, gates, fatores, perfis de pontuação
llm/              abstração de provedores, cache, log de custo, orçamento
reports/          digest semanal
docs/             memória do projeto (ver docs/README.md)
```

## Comandos

`make setup` · `make migrate` · `make seed` (catálogo) · `make memory` (perfil, portfólio, interações) · `make collect` · `make run` (admin) · `make test` ·
`make lint`/`make fmt` · `make check` (ruff, pytest, migrations, repo_checks: o que o CI roda).
Testes precisam de `DATABASE_URL` (PostgreSQL, ex. `docker compose up -d`).

## Convenções

- Código, identificadores e commits técnicos em **inglês**; documentação em **português**.
- Todo conector implementa a interface de `docs/architecture/connectors.md`.
- Toda chamada LLM passa por `llm/` (cache + log de custo + teto de orçamento). Nunca
  chame SDK de provedor direto em outro módulo.
- Evidência só por `core.services.evidence.record_evidence`; contato só exibido/usado via
  `ContactPoint.objects.usable()` (respeita opt-out/LGPD).
- Testes de conectores usam respostas gravadas (fixtures); nada de rede em teste.
- Segredos só em `.env` (nunca commitados). `.env.example` documenta as chaves.
- **Repositório PÚBLICO (ADR-014)**: nunca commitar CNPJ, endereço, e-mails/telefones/nomes de
  contatos, interações, digests, dumps ou chaves. Logs do Actions são públicos: sem dados pessoais.
  Dados privados ficam em `data/private/` (ignorado) ou no banco; `data/seeds/` só com dados públicos.
- Etapas pequenas: se uma etapa crescer demais, divida-a e atualize o plano.

## Onde encontrar o quê

Mapa completo: `docs/README.md` · estado e próxima etapa: `docs/plan/STATUS.md` · etapas: `PLAN.md`.
- `docs/architecture/`: `overview` (inclui bibliotecas), `data-model`, `scoring`, `geo-relevance`, `llm-strategy`, `connectors`
- `docs/research/`: fontes (`opportunity-sources`, `organization-sources`), `legal-and-compliance`, `hosting`, `ai-models-and-costs`
- `docs/decisions/` (ADRs) · `docs/product/` (visão, MVP, riscos, `ui-direction`) · `docs/agents/`
- `docs/history/` (arquivo morto) · `docs/operations/` (`claude-workflow` ciclo /clear, `supabase-setup`)

## Contexto de negócio mínimo

- Base: Araraquara/SP. Proximidade importa para cursos presenciais, SESCs, escolas e eventos; não para
  software, sites e eventos online. Polos: Araraquara, São Carlos, Ribeirão Preto, Bauru.
  Localização é **fator** de prioridade, nunca filtro absoluto.
- **SESC é hipótese validada**: Game Lab realizado; propostas enviadas a Bauru, Ribeirão Preto e
  São Carlos. O sistema **lembra** interações e nunca "redescobre" quem já foi contatado (ADR-012).
  Buscar também organizações parecidas com o SESC.
- Empresa é **MEI** desde 10/04/2025 (2 anos em 10/04/2027). CNAEs cobrem ensino e treinamento em
  informática; software/web/jogos sob encomenda podem exigir ME → alerta, não gate (ADR-013, ADR-015).
- Portfólio (AstroDash, Tirania, protótipo, itch.io, Game Lab) é **prova** no matching (`PortfolioItem`).
- Serviços: jogos (educativos, institucionais, gamificação), educação (cursos, oficinas, game jams),
  software sob demanda, web. Catálogo é **dado**, não código (`ServiceOffering`). Domínio: `scorpionbits.com`.
