# Fase 0 — Fundação

## E00 — Planejamento, pesquisa e documentação ✅
Concluída em 2026-09-30. Registros: `docs/history/sessions/2026-09-30-E00.md` e
`2026-09-30-E00b.md` (complemento: domínio, portfólio, SESC, MEI, Supabase/Vercel, Gemini).

---

## E01 — Validação de fontes + baseline manual (spike)

**Objetivo:** confirmar, a partir de uma máquina com acesso normal à internet, que as
fontes prioritárias são acessíveis, estáveis e permitidas; e registrar um **baseline
manual** para medir depois se o sistema acha o que não acharíamos.

**Por que é a primeira etapa:** o ambiente de planejamento não conseguiu testar as fontes
(rede bloqueada). Descobrir agora que uma fonte não funciona custa minutos.
**Não é código de produto**: scripts descartáveis em `spikes/E01/`.

**Ler antes:** `docs/research/opportunity-sources.md`, `docs/research/organization-sources.md`,
`docs/research/legal-and-compliance.md` (checklist por fonte).

**Alterações:**
- `spikes/E01/*.py|*.sh` — chamadas simples a cada fonte, salvando 1 resposta de exemplo em
  `spikes/E01/samples/` (viram fixtures depois).
- `opportunity-sources.md` e `organization-sources.md` — preencher "Validado" (✅/❌/⚠ +
  formato, paginação, campos úteis, robots.txt, termos).
- `docs/research/baseline-manual.md` — **novo**: até 1 h de busca manual de oportunidades e
  instituições (SESC, similares, escolas), registrando o que foi achado e o tempo gasto.

**Fontes a validar (mínimo):** Devpost; itch.io (`/jams`, `.xml`); Querido Diário (cobertura
de Araraquara, São Carlos, Ribeirão Preto, Bauru, Matão, Américo Brasiliense); Mapas
Culturais (nacional e SP); FAPESP PIPE; ProAC/PNAB (arquivo de editais, incluindo a linha de
jogos eletrônicos); Oficinas Culturais (Poiesis); Sebrae-SP; InovAtiva; páginas de editais das
prefeituras dos polos; SESC-SP (lista de unidades; existe credenciamento/chamamento?);
SENAC/SESI/Centro Paula Souza/IFSP (listas de unidades); INEP Catálogo de Escolas; IBGE.

**Dependências:** nenhuma. Pode rodar em paralelo com a E01b.
**Modelo (desenvolvimento):** Claude Sonnet 5.5. **IA em runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** baixa.
**Riscos:** fonte exige JS/login (→ ❌ + alternativa); termos proíbem uso automatizado (→ fora);
cobertura do Querido Diário ausente em algum polo (→ `html_watch` do diário municipal).
**Testes:** evidência = amostras salvas + tabelas preenchidas.
**Critério de conclusão:**
- [ ] Todas as fontes prioritárias com status e observação.
- [ ] ≥ 1 amostra real por fonte ✅.
- [ ] `baseline-manual.md` com ≥ 10 itens e tempo gasto.
- [ ] Lista de fontes do MVP confirmada/ajustada em STATUS.

---

## E01b — Inventário do negócio e contas

**Objetivo:** reunir os dados reais da Scorpion Bits e preparar as contas gratuitas, para que
as etapas seguintes não inventem nada.
**Tarefa majoritariamente humana**; o Claude conduz com um checklist e registra.

**Ler antes:** `docs/research/business-analysis.md` (perguntas em aberto),
`docs/research/hosting.md`, ADR-010, ADR-011, ADR-013.

**Alterações:**
- `data/seeds/portfolio.csv` (versionado; só dados públicos — **repositório é público, ADR-014**): slug, título, tipo, ano,
  descrição curta, URL pública (itch.io etc.), serviços relacionados, tags de capacidade.
  Itens: Game Lab SESC, AstroDash, Tirania, protótipo, outros jogos do itch.io.
- `data/private/interactions.csv` (**fora do git**): histórico SESC (Game Lab — unidade,
  data, alunos; propostas a Bauru, Ribeirão Preto, São Carlos — data, canal, cargo do contato,
  serviço, status, próxima ação) e quaisquer outros contatos já feitos.
- `.env.example` com as chaves previstas; `.gitignore` com `data/private/`.
- `docs/research/accounts-checklist.md` — **novo**, sem segredos: o que foi criado/ativado e limites confirmados:
  - Supabase: projetos `radar-dev` e `radar-prod`; string do **pooler**; Data API desativada ou plano de schema dedicado.
  - Google: benefícios de desenvolvedor do AI Pro **ativados** (créditos ~US$ 10/mês); projeto
    Gemini API com faturamento pelos créditos; chave do AI Studio (free tier).
  - GitHub Actions: repositório **público** (confirmado) → minutos ilimitados e `schedule` disponível; testar um workflow vazio na E16.
  - Busca: Brave (crédito US$ 5/mês) ou Serper (2.500 grátis).
  - (Opcional) Anthropic API com limite de gasto.
  - E-mail de contato (Gmail por enquanto; `@scorpionbits.com` opcional) em `CONTACT_EMAIL` no `.env`.
- `CompanyProfile` (valores a carregar na E03b): natureza jurídica MEI, data de abertura,
  CNAEs, município da sede — **CNPJ só no `.env`/banco**.

**Dependências:** nenhuma.
**Status (2026-09-30): parcial.** Feito: seeds (`portfolio.csv`, `company_profile.json`,
`interactions.template.csv`), `.env.example`, `accounts-checklist.md`, ADR-014, ADR-015. Pendentes do
humano: A1–A9 do checklist e o preenchimento das datas/cargos/status do template de interações.
**Modelo (desenvolvimento):** Claude Sonnet 5.5 (ou Haiku 4.5). **IA em runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** baixa.
**Riscos:** informação incompleta → marcar como pendente, nunca preencher por suposição;
`schedule` indisponível → registrar e usar cron externo/local (ADR-010).
**Critério de conclusão:**
- [ ] `portfolio.csv` com URLs reais conferidas pelo humano.
- [ ] `interactions.csv` com todo o histórico conhecido (fora do git).
- [ ] Checklist de contas preenchido; limites relevantes confirmados e divergências anotadas em `hosting.md`/`ai-models-and-costs.md`.
- [ ] Perguntas em aberto de STATUS respondidas ou marcadas pendentes.

---

## E02 — Esqueleto do projeto

**Objetivo:** projeto Python/Django executável, conectado ao Postgres, com qualidade
automatizada desde o início.

**Ler antes:** `CLAUDE.md`, `docs/architecture/overview.md`, ADR-010.

**Alterações:**
- `pyproject.toml` (uv; deps: django, psycopg[binary], dj-database-url ou django-environ,
  httpx, pydantic; dev: pytest, pytest-django, ruff), `uv.lock`.
- `radar/` settings: `DATABASE_URL` (Supabase via pooler; `CONN_MAX_AGE` e opções
  compatíveis com o modo do pooler; `sslmode=require`), `TIME_ZONE="America/Sao_Paulo"`,
  `LANGUAGE_CODE="pt-br"`; apps vazios `core`, `collection`, `extraction`, `llm`, `scoring`, `reports`.
- Schema: **dedicado `radar`** (decidido e testado; ADR-016, `overview.md`).
- `Makefile`: `setup`, `run`, `test`, `lint`, `check` (lint + test + docs-check), `docs-check`
  (limites de linhas do CLAUDE.md/STATUS.md), `migrate`.
- `.env.example`, `.gitignore` (`.env`, `data/private/`, caches).
- `.github/workflows/ci.yml` — `make check` com **PostgreSQL em service container**.
- `README.md` — "Como rodar" (local apontando para `radar-dev`).

**Status (2026-10-01): concluída, exceto a verificação contra o Supabase real** (aguarda P4).
**Dependências:** E01b (projeto Supabase criado; senão, Postgres local para começar).
**Modelo (desenvolvimento):** Claude Sonnet 5.5. **IA em runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** baixa.
**Riscos:** IPv6 da conexão direta → usar string do pooler; incompatibilidades do modo
transação do pooler (prepared statements/cursors) → preferir modo sessão ou ajustar opções.
**Testes:** fumaça (`manage.py check`, `/admin/` responde); migrations aplicam no Postgres do CI.
**Critério de conclusão:**
- [x] `make check` passa em PostgreSQL 16 (8 testes) e o admin responde (login verificado). CI do GitHub verde (run 1).
- [ ] `make run` conectado ao `radar-dev` do Supabase — **pendente de P4**.
- [ ] Supabase não expõe as tabelas pela Data API — **pendente de P4** (schema `radar` testado localmente).
- [x] CLAUDE.md "Estrutura" confere com o que existe.

---

## E03 — Modelo de dados núcleo + admin básico + catálogo de serviços

**Objetivo:** entidades centrais com evidência e o catálogo de serviços como dado.

**Ler antes:** `docs/architecture/data-model.md`, ADR-004.

**Alterações:**
- `core/models.py`: `Source`, `Organization` (com `network`, `parent`, `similarity_tags`;
  campos derivados de relacionamento podem ficar nulos até a E03b), `ContactPoint`,
  `Opportunity` (inclui campos de requisitos de empresa), `Evidence`, `ServiceOffering`,
  `Match`, `Triage`, `Suppression`. (`Score` na E13; `Municipality` na E12 — até lá
  `municipality_name`/`uf` provisórios.)
- `core/admin.py`: listas com filtros, busca, inlines de `Evidence` e `ContactPoint`;
  inferências visualmente distintas.
- `core/fixtures/services.json`: `course_gamedev`, `workshop_gamedev`, `game_jam_org`,
  `extracurricular_school`, `indie_game`, `educational_game`, `institutional_game`, `gamification`,
  `custom_software`, `web_app`, `landing_page`, `institutional_site` (palavras-chave, perfis geográficos). Cada serviço tem `mei_coverage`
  (`covered`/`verify`/`not_covered`, valores iniciais em ADR-015).
- `core/services/evidence.py`: `record_evidence(...)`. Testes.

**Dependências:** E02.
**Modelo (desenvolvimento):** Claude Opus 5.5. **IA em runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** média.
**Riscos:** modelagem excessiva → só o que está em `data-model.md`; `Evidence` genérica →
documentar a escolha (GenericForeignKey ou par de campos).
**Testes:** entidades; unicidade/dedupe; helper de evidência; fixture carrega.
**Status (2026-10-01): concluída**, exceto aplicar as migrations no **Supabase real**, que fica
com o titular (a rede do ambiente do Claude bloqueia `*.supabase.co`): `docs/operations/supabase-setup.md`.
Também entregue: `core/fields.py` (`ChoiceArrayField`), `core/services/{normalize,canonical,suppression}.py`,
comando `load_services` (+ `make seed`), ADR-017/018. Estado e desvios do modelo: `data-model.md`.
**Critério de conclusão:**
- [x] Migrations aplicam do zero no Postgres (banco vazio → tabelas do núcleo só no schema `radar`; 202 testes).
- [x] Admin cadastra oportunidade com 2 evidências (observed e inferred) exibidas de forma distinta
  (teste automatizado e conferido no navegador: ✅ borda cheia × 🔮 borda tracejada).
- [x] Catálogo de serviços editável no admin (cobertura do MEI e "ativo" direto na lista).
- [ ] Migrations aplicadas no Supabase — **a cargo do titular** (P4).

---

## E03b — Memória comercial, portfólio e perfil da empresa

**Objetivo:** o sistema passa a **lembrar** — quem já contatamos, quando, sobre o quê,
resultado, próximo passo — e conhece o **portfólio** e o **perfil MEI**. Primeiro marco útil (M1).

**Ler antes:** ADR-012, ADR-013, `data-model.md` (Interaction, PortfolioItem, CompanyProfile, Organization).

**Alterações:**
- `core/models.py`: `Interaction`, `PortfolioItem` (M2M com `ServiceOffering`),
  `CompanyProfile` (linha única), `Match.portfolio_refs`; cálculo de `relationship_status`,
  `last_interaction_at`, `next_action_at` na `Organization` ao salvar interação.
- Admin: inline de interações na organização (mais recente primeiro); filtro por status de
  relacionamento; lista "próximas ações" ordenada por data; `PortfolioItem` editável;
  `CompanyProfile` como singleton.
- Comandos: `load_company_profile data/seeds/company_profile.json` (CNPJ vem do `.env`);
  `import_portfolio data/seeds/portfolio.csv`; `import_interactions data/private/interactions.csv`
  (começar copiando `data/seeds/interactions.template.csv` e preenchendo; linhas `pendente` são importadas sem datas inventadas) (cria organizações SESC com
  `network="SESC-SP"` e `parent`, e as interações — idempotente).
- Regra de dedupe: criar organização sempre passa por busca de existente (nome normalizado +
  município + rede) — base para "nunca redescobrir".

**Dependências:** E03, E01b.
**Modelo (desenvolvimento):** Claude Opus 5.5. **IA em runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** média.
**Riscos:** dados pessoais no CSV de interações → nunca commitar; manter mínimo (cargo > nome).
**Testes:** status derivado correto para cada tipo de interação; importação idempotente; dedupe de organização.
**Critério de conclusão:**
- [x] No admin, SESC Bauru/Ribeirão Preto/São Carlos mostram proposta enviada, data e próxima ação
  (status `proposal_sent` já; **data e próxima ação aguardam P2**: linhas `pendente`, sem data inventada).
- [x] Game Lab aparece como `PortfolioItem` e como interação `course_delivered` na unidade correta (SESC Araraquara).
- [x] `CompanyProfile` preenchido (sem CNPJ no git: `COMPANY_CNPJ` no `.env`).
- [x] `core/models/` dividido em pacote; `make check` passa (271 testes). Regras em ADR-020.

---

## E04 — Infra de coleta

**Objetivo:** base comum para todos os conectores.

**Ler antes:** `docs/architecture/connectors.md`, `legal-and-compliance.md` (scraping).

**Alterações:**
- `collection/fetcher.py`: `PoliteFetcher` (User-Agent com contato `@scorpionbits.com`,
  robots.txt com cache, rate limit por domínio, ETag/If-Modified-Since usando valores
  guardados no banco, retries com backoff, limite de tamanho).
- `collection/models.py`: `CollectionRun`, `RawDocument` (URL, hash, ETag, texto extraído
  comprimido, retenção — **sem binários**; ver ADR-010).
- `collection/base.py`, `registry.py`, comando `collect` (`<slug>`, `--all`, `--dry-run`, `--limit`).
- `collection/upsert.py`: dedupe por `canonical_key` **e consulta à memória comercial**
  (organização existente nunca vira nova).
- Conector genérico `seed_csv`. Testes com transport mock do httpx (sem rede).

**Dependências:** E03 (E03b recomendado).
**Modelo (desenvolvimento):** Claude Sonnet 5.5. **IA em runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** média.
**Riscos:** robots.txt estranho (fallback conservador); crescimento do banco (retenção).
**Testes:** robots bloqueia; rate limit; 304 reutiliza; retry em 503; upsert idempotente.
**Critério de conclusão:**
- [ ] `collect seed_csv --dry-run` funciona; execução registrada em `CollectionRun`.
- [ ] Rodar duas vezes não duplica; organização existente é reconhecida.
- [ ] Nenhum teste faz acesso de rede.
