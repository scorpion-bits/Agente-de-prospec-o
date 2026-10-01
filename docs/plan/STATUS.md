# STATUS — Radar Scorpion Bits

> Estado vivo do projeto. Atualizar ao fim de **toda** etapa. Limite: 120 linhas.
> Última atualização: **2026-10-01** (E05)

## Onde estamos

**Fase 0 — Fundação.** Prontos E00–E04, E12 (geografia), E17/E17b (SESC-SP, escolas e parecidas), E18 (site oficial),
E19 (contatos públicos, migration `core.0005`) e E20 (matching por regras, sem migration); detalhes na tabela abaixo.
Marco **M1** (memória comercial) funcional. Comandos do dia a dia: `make help`.
**E05 (Devpost)**: conector `devpost` (hackathons online/Brasil por tema), fonte desabilitada até conferir termos (ADR-028); sem migration.
**E01b parcial**; **P4 concluído** (migrations aplicadas no Supabase). **Repositório público** → regras de dados em ADR-014.

## Próxima etapa

➡️ **E06 — Conector itch.io (game jams)** (próximo na ordem do `PLAN.md`; E21 vem depois de E13, na posição 20–21).
Antes, o humano roda `make websites` (P13), `make contacts` (P14) e `make match` (P15): sem dados reais o M2 não fecha.

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
| E18 | 2026-10-01 | `collection/search/` (Serper/Brave, cache `SearchQuery`, teto por execução), `extraction/website.py` (bloqueio, nome+município na página), `find_websites`; evidência inferida; 31 testes novos; ADR-025. **Busca real e amostra de 20 não testadas (P13)** | `…-10-01-E18.md` |
| E19 | 2026-10-01 | `extraction/contacts.py` (e-mail, telefone E.164, WhatsApp, JSON-LD, redes, formulário), `collection/contact_finder.py`, `extract_contacts`, `contacts_checked_at`; evidência observada, opt-out antes e depois, idempotente; 40 testes novos; ADR-026. **Sites reais e amostra de 20 não testados (P14)** | `…-10-01-E19.md` |
| E20 | 2026-10-01 | `scoring/match_rules.py` + `matching.py` (regras em dados), `match_services`; razões com evidência, prova só de portfólio público e confirmado (sem prova: força ×0,7), máx. 3 por organização; 19 testes; ADR-027. **Regras e forças são hipóteses; nada rodado em dados reais (P15)** | `…-10-01-E20.md` |
| E05 | 2026-10-01 | `collection/connectors/devpost.py` (JSON público, filtro tema + online/Brasil, datas só se inequívocas, dedupe por URL), `Source` `devpost` desabilitada; 33 testes (fixture **sintética**); ADR-028. **Formato real e termos não conferidos (P16)** | `…-10-01-E05.md` |

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
| P13 | **E18:** criar a chave Serper (ou Brave) em `.env` (`SEARCH_PROVIDER`, `SERPER_API_KEY`); rodar `make migrate` e `make websites DRY=1 N=20` na sua máquina (não no SQL Editor); conferir à mão os `found` (meta ≥ 85%) e anotar erros; depois `make websites` | `docs/decisions/ADR-025-descoberta-de-site-oficial.md` |
| P14 | **E19:** depois do P13, rodar `make migrate` e `make contacts DRY=1 N=20` na sua máquina (não no SQL Editor); conferir à mão os contatos contra os sites (meta: todos conferem) e a linha «Cobertura»; depois `make contacts`. Revisar `is_personal` no admin | `docs/decisions/ADR-026-contatos-publicos-institucionais.md` |
| P15 | **E20:** depois de `make seed`/`make memory`/`make collect`, rodar `make match DRY=1` e depois `make match` na sua máquina (não no SQL Editor; sem migration); conferir no admin (Matches) 10 sugestões: razão faz sentido, prova correta; ajustar `scoring/match_rules.py` se preciso. Marcar itens de portfólio como `public` só quando puderem ser citados | `docs/decisions/ADR-027-matching-por-regras.md` |
| P16 | **E05:** conferir termos de uso/robots.txt do Devpost; `make seed`, marcar «coleta permitida» e habilitar `devpost` no admin; `make collect DRY=1` e depois `make collect` na sua máquina (não no SQL Editor; sem migration); revisar 10 hackathons (meta ≥ 10 coletados). Se o JSON mudou, o erro diz; salvar uma resposta real como fixture | `docs/decisions/ADR-028-conector-devpost.md` |

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
023 SESC-SP (CSV curado) e escolas do INEP (arquivo local) ·
024 parecidas com o SESC ·
025 site oficial: busca com cache + validação que erra para «ambíguo» ·
026 contatos públicos: por regra, só do domínio da organização, opt-out antes e depois ·
027 matching por regras em dados ·
**028 conector Devpost: filtro de relevância, datas sem chute, fonte desabilitada até conferir**.

## Problemas abertos

- Coordenadas dos municípios vêm de conjunto derivado do IBGE (sedes), não do IBGE direto (rede bloqueada): conferir quando possível (ADR-022).
- Lista SESC-SP escrita de memória e layout do INEP supostos: nada conferido na fonte (P11, ADR-023).
- Lista de organizações parecidas e URLs oficiais também de memória (P12, ADR-024); `html_watch` das páginas de chamamento só na E07.
- E18: formatos de Serper/Brave só da documentação (nada testado com chave real); sites só em JavaScript caem em ambíguo (ADR-025).
- E20: regras e forças são hipóteses não calibradas; palavras-chave só enxergam o que virou evidência (ADR-027).
- E19: nenhum site real testado; heurística pessoal × institucional pode errar; e-mail ofuscado/JS não é lido (ADR-026).
- Endpoints das fontes **não testados** (E01); E05: formato do JSON do Devpost só da documentação de terceiros (ADR-028).
- Migrations aplicadas no Supabase (projeto **Prospection**) pelo titular, que confirmou que funcionou. **Não conferido por nós:** a Data API sem as tabelas expostas e as migrations `collection.0001`/`core.0003` (E04), aplicadas só no PostgreSQL local; rodar `make migrate` de novo após o merge do PR da E04. A E17 **não** tem migration (só `make seed` para criar as fontes).
- Valores iniciais do catálogo (palavras-chave, tipos-alvo, CNAEs exigidos) são **hipóteses** editáveis no admin;
  CNAEs a confirmar com o contador (P7). Preços não estão no repositório (ficam no banco).
- `COMPANY_CNPJ` e `CONTACT_EMAIL` só no `.env`: sem eles `make memory` deixa CNPJ/e-mail do perfil em branco.
- Dedupe de organização por nome varre a tabela em Python (ADR-020): indexar chave normalizada quando a base crescer (E04+).
- Aviso do Django 6 sobre `URLField` filtrado nos testes (`pyproject.toml`); remover ao migrar. CI usa `checkout@v4`/`setup-uv@v5` (Node 20, forçado para 24): subir quando conveniente.
- Limites de free tier (Supabase, Gemini, Serper/Brave) e créditos do AI Pro: confirmar ao criar as contas/Billing.
- `schedule` do GitHub Actions desliga após 60 dias sem commits (repositório público) — mitigação em ADR-014.

## Riscos de negócio a acompanhar

- **Janela escolar 2027 (out–dez/2026)**: manter prospecção manual de escolas e follow-up das
  propostas SESC em paralelo ao desenvolvimento.
- **MEI**: CNAEs cobrem ensino e treinamento em informática, mas não software/web/jogos sob
  encomenda (ADR-015). Editais com exigência de 2 anos de CNPJ: elegível só a partir de **10/04/2027**.
- Limite de faturamento do MEI: R$ 81 mil/ano.

## Métricas (a partir da E14)

Ainda sem dados.
