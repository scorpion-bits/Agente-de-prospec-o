# STATUS — Radar Scorpion Bits

> Estado vivo do projeto. Atualizar ao fim de **toda** etapa. Limite: 120 linhas.
> Última atualização: **2026-10-01** (E17b)

## Onde estamos

**Fase 0 — Fundação.** Prontos: planejamento (E00, E00b), esqueleto (E02), **modelo de dados núcleo +
admin + catálogo de serviços (E03)** e **memória comercial, portfólio e perfil da empresa (E03b, marco M1)**:
`Interaction`, `PortfolioItem`, `CompanyProfile`, status de relacionamento derivado, "próximas ações" no admin,
`make memory`, `core/models/` em pacote. **E04 (infra de coleta)**: `PoliteFetcher`, `CollectionRun`/`RawDocument`,
runner e `collect`, conector `seed_csv`, `purge_raw_documents`. **E12 (geografia)**: tabela `Municipality` (IBGE),
`scoring/geo.py` com anéis R0–R5 e os 5 perfis, `make seed` carrega os municípios.
**E17 (SESC-SP + escolas)**: 42 unidades SESC em `data/seeds/sesc_sp.csv` (filhas de "SESC-SP"), conector `inep-escolas`
(arquivo local do Catálogo de Escolas), `load_sources`, `count_organizations`.
**E17b (parecidas com o SESC)**: `data/seeds/similar_orgs.csv`, conector `orgs-parecidas-sesc`, tags de similaridade
(vocabulário fechado) e filtro «parecida com o SESC» no admin.
**E01b parcial**; **P4 concluído** (migrations aplicadas no Supabase pelo titular; faltam outras ações do humano, abaixo).
**Repositório público** → regras de dados em ADR-014. Comandos: `make help`.

## Próxima etapa

➡️ **E18 — Descoberta de site oficial** (`fase-3-leads-institucionais.md`; ordem do `PLAN.md`:
E18 → E19, **M2**). Depende de E17 e E04.

➡️ **E01 — Validação de fontes + baseline manual** continua pendente: precisa de máquina com internet
normal (o ambiente do Claude bloqueia itch.io, devpost.com, queridodiario, gov.br e supabase.co). Ela também
confere as listas SESC e de parecidas e o layout real do INEP (P11, P12).

## Concluído

| Etapa | Data | Resumo | Registro |
|---|---|---|---|
| E00 | 2026-09-30 | Planejamento, pesquisa, arquitetura, plano, ADR-001–009 | `docs/history/sessions/2026-09-30-E00.md` |
| E00b | 2026-09-30 | Complemento: Supabase/GitHub Actions, Gemini, memória comercial, MEI; ADR-010–013 | `…-E00b.md` |
| E01b (parcial) | 2026-09-30 | Seeds (portfólio, perfil MEI, template de interações), `.env.example`, checklist de contas, ADR-014/015 | `…-E01b.md` |
| E02 | 2026-10-01 | Django 5.2 + psycopg3, schema `radar`, admin, Makefile, CI com Postgres, `repo_checks`, ADR-016. CI verde | `…-10-01-E02.md` |
| E03 | 2026-10-01 | 9 entidades, `record_evidence` (ADR-004), opt-out (`usable()`), admin com selos observado × inferido, catálogo de 12 serviços (`make seed`); 202 testes; ADR-017/018/019. CI verde. Aplicado no Supabase pelo titular (P4) | `…-10-01-E03.md` |
| E03b | 2026-10-01 | `Interaction`, `PortfolioItem`, `CompanyProfile`, derivados por signals, admin (histórico na organização, "próximas ações"), `load_company_profile`/`import_portfolio`/`import_interactions`, dedupe de organização; 271 testes; ADR-020. **M1 funcional; datas das propostas aguardam P1/P2** | `…-10-01-E03b.md` |
| E04 | 2026-10-01 | `collection/`: fetcher educado (robots, rate limit, 304, retry, limites), `CollectionRun`/`RawDocument`/`Evidence.raw_document`, runner + `collect` (`--all/--dry-run/--limit`), `seed_csv`, retenção; 337 testes; ADR-021 | `…-10-01-E04.md` |
| E12 | 2026-10-01 | `Municipality` (5.571 linhas, `load_municipalities`), FK `municipality` com resolução ao salvar (`resolve_municipalities`), `scoring/geo.py` (R0–R5, 5 perfis, gate, dado ausente); 395 testes; ADR-022. **Bauru está a ≈ 111 km, não ~100** | `…-10-01-E12.md` |
| E17 | 2026-10-01 | `sesc-sp-unidades` (42 unidades curadas, mãe "SESC-SP", dedupe com E03b), `inep-escolas` (privadas ativas ≤ 150 km + polos, colunas por nome, arquivo local), `parent_name` no upsert, `load_sources`, `count_organizations`; 418 testes; ADR-023. **Lista SESC e layout do INEP não conferidos na fonte (P11)** | `…-10-01-E17.md` |
| E17b | 2026-10-01 | `similar_orgs.csv` (redes, prefeituras e universidades dos 4 polos), conector `orgs-parecidas-sesc`, tags de vocabulário fechado que somam no upsert, filtro no admin; 431 testes; ADR-024. **Lista e URLs de memória, não conferidas (P12)** | `…-10-01-E17b.md` |

## Pendências do humano

| # | Ação | Onde registrar |
|---|---|---|
| P1 | Game Lab (SESC Araraquara): data, nº de alunos, cargo do contato | copiar `data/seeds/interactions.template.csv` → `data/private/interactions.csv`, preencher e rodar `make memory` (completa os registros `pendente`) |
| P2 | Propostas SESC Bauru, Ribeirão Preto, São Carlos: data, canal, cargo, serviço proposto, status, próxima ação | idem (**não** commitar) |
| P3 | Protótipo: nome e URL; gênero/ano/engine de AstroDash e Tirania; confirmar se scorpionbits.com foi feito por vocês | `data/seeds/portfolio.csv` |
| P4 | **CONCLUÍDO (2026-10-01).** O titular aplicou as migrations no Supabase pela própria máquina e funcionou. O projeto se chama **Prospection** (não `radar-dev`/`radar-prod`: não há par dev/prod por enquanto). Identificador e chaves seguem **fora do git** | `docs/operations/supabase-setup.md` |
| P5 | Ativar benefícios Google AI Pro (conta pessoal do titular) + chaves AI Studio | A2, A3 |
| P6 | Escolher busca (Serper ou Brave); gerar chaves age para backup | A4, A5 |
| P7 | Falar com o **contador** sobre CNAEs de software/web/jogos e migração para ME; ajustar `mei_coverage` no admin | ADR-015 |
| P8 | Decidir: manter repositório público (recomendado agora, com ADR-014) ou privado | ADR-014 |
| P9 | **Vercel** está conectado a este repositório (ADR-010: sem Vercel no MVP): tenta um deploy a cada push, sem ter o que construir, e, se receber `DATABASE_URL`, exporia o admin com contatos (LGPD). Desconectar ou usar *Ignored Build Step* até existir o front | painel do Vercel |
| P10 | **UI nova** decidida: web + API do Django, visual do site (ADR-019). Falta replanejar a E29 (front + API) e escolher tecnologia/hospedagem, **depois** de E03b/E04 | `docs/product/ui-direction.md` |
| P11 | **E17:** (a) conferir `data/seeds/sesc_sp.csv` contra sescsp.org.br (unidades faltando/sobrando) e preencher `website`/`source_url`; (b) baixar o Catálogo de Escolas do INEP para `data/inep/catalogo_escolas.csv`, rodar `make seed`, habilitar a fonte `inep-escolas` no admin, `make collect`, e `uv run python manage.py count_organizations school`; conferir 5 escolas à mão; se o CSV tiver outros nomes de coluna, o erro aponta qual | `docs/decisions/ADR-023-sesc-sp-e-escolas-inep.md` |
| P12 | **E17b:** conferir `data/seeds/similar_orgs.csv` (unidades faltando/sobrando, URLs oficiais) e rodar `make seed` seguido de `make collect` no terminal da sua máquina (não no SQL Editor); sem migration nova | `docs/decisions/ADR-024-organizacoes-parecidas-com-o-sesc.md` |

## Decisões vigentes (ver `docs/decisions/README.md`)

ADR-001 Django/admin · 003 IA último recurso · 004 evidência · 005 humano no controle ·
006 score explicável · 007 fontes oficiais · 008 CLAUDE.md ≤ 150 linhas · 009 escopo do MVP ·
010 Supabase + GitHub Actions + admin local · 011 modelo por tarefa (Gemini na extração) ·
012 memória comercial e portfólio · 013 elegibilidade MEI · 014 repositório público ·
015 cobertura de atividades do MEI (CNAE) · 016 schema `radar` + pooler em modo sessão ·
017 Evidence/Triage por GenericForeignKey · 018 listas como ArrayField ·
019 UI web + API do Django (sem executável, sem acesso direto ao Supabase) ·
020 regras do relacionamento derivado (datas, pendentes sem data inventada, dedupe) ·
021 regras da coleta (robots, bloqueio, dry-run, retenção) ·
022 municípios do IBGE: texto × FK e perfis geográficos como dado ·
**023 SESC-SP (CSV curado) e escolas do INEP (arquivo local)**.

## Problemas abertos

- Coordenadas dos municípios vêm de conjunto derivado do IBGE (sedes), não do IBGE direto (rede bloqueada): conferir quando possível (ADR-022).
- Lista SESC-SP escrita de memória e layout do INEP supostos: nada conferido na fonte (P11, ADR-023).
- Lista de organizações parecidas e URLs oficiais também de memória (P12, ADR-024); `html_watch` das páginas de chamamento só na E07.
- Endpoints das fontes **não testados** (E01). Nenhum conector real existe ainda; só o genérico `seed_csv`.
- Migrations aplicadas no Supabase (projeto **Prospection**) pelo titular, que confirmou que funcionou. **Não conferido por nós:** a Data API sem as tabelas expostas e as migrations `collection.0001`/`core.0003` (E04), aplicadas só no PostgreSQL local; rodar `make migrate` de novo após o merge do PR da E04. A E17 **não** tem migration (só `make seed` para criar as fontes).
- Valores iniciais do catálogo (palavras-chave, tipos-alvo, CNAEs exigidos) são **hipóteses** editáveis no admin;
  CNAEs a confirmar com o contador (P7). Preços não estão no repositório (ficam no banco).
- `COMPANY_CNPJ` e `CONTACT_EMAIL` só no `.env` do titular: sem eles `make memory` deixa CNPJ/e-mail do perfil em branco.
- Dedupe de organização por nome varre a tabela em Python (ADR-020): indexar chave normalizada quando a base crescer (E04+).
- Sair de `do_not_contact` exige editar no banco/shell (derivado não é editável; tela de `Suppression` na Fase 4).
- Aviso do Django 6 sobre `URLField` (http→https) filtrado nos testes (`pyproject.toml`); remover ao migrar para o Django 6.
- CI usa `actions/checkout@v4` e `setup-uv@v5`, que o GitHub avisa serem Node 20 (hoje forçados para Node 24 e funcionando): subir as versões quando conveniente.
- Limites de free tier (Supabase, Gemini, Serper/Brave) por fontes secundárias — confirmar ao criar as contas.
- Créditos do AI Pro na Gemini API: 🔎 conferir em Billing após ativar.
- `schedule` do GitHub Actions desliga após 60 dias sem commits (repositório público) — mitigação em ADR-014.

## Riscos de negócio a acompanhar

- **Janela escolar 2027 (out–dez/2026)**: manter prospecção manual de escolas e follow-up das
  propostas SESC em paralelo ao desenvolvimento.
- **MEI**: CNAEs cobrem ensino e treinamento em informática, mas não software/web/jogos sob
  encomenda (ADR-015). Editais com exigência de 2 anos de CNPJ: elegível só a partir de **10/04/2027**.
- Limite de faturamento do MEI: R$ 81 mil/ano.

## Métricas (a partir da E14)

Ainda sem dados.
