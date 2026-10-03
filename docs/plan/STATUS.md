# STATUS — Radar Scorpion Bits

> Estado vivo do projeto. Atualizar ao fim de **toda** etapa. Limite: 120 linhas.
> Última atualização: **2026-10-03** (E21)

## Onde estamos

**Fase 0 — Fundação.** Prontos E00–E04, E12 (geografia), E17/E17b (SESC-SP, escolas e parecidas), E18 (site oficial),
E19 (contatos públicos, migration `core.0005`) e E20 (matching por regras, sem migration); detalhes na tabela abaixo.
Marco **M1** (memória comercial) funcional. Comandos do dia a dia: `make help`.
**E05–E09** (Devpost, itch.io, `html_watch`, Querido Diário, Mapas Culturais; ADR-028–032) são conectores de oportunidades, com
fontes desabilitadas até conferir termos. **E10 (camada de IA `llm/`, ADR-033)** pronta (fumaça Gemini OK); **E11 (extração, ADR-034)** pronta, acurácia a medir (P22). **E13 (score, ADR-035)** pronta (migration `scoring.0001`, P23); **E14 (triagem e métricas, ADR-036)**, **E15 (digest, ADR-037)**, **E16 (agendamento e backups, ADR-038)** e **E21 (score de leads, ADR-039; migration `scoring.0002`)** prontas (P24–P27).
**E01b parcial**; migrations aplicadas no Supabase pelo titular (P4 concluído). **Repositório público** → regras de dados em ADR-014.

## Próxima etapa

➡️ **E22 — Avaliação do MVP** (go/no-go), em thread nova; exige ≥ 4 semanas de uso real. Antes, o humano faz o P26 (Secrets, 1ª execução
do pipeline, teste de restauração) e o P27 (`make match`, `make rescore`, ler 5 leads).
➡️ **E01 (validação de fontes)** segue pendente: precisa de internet normal (o ambiente do Claude bloqueia as fontes e o supabase.co) (P11, P12).

## Concluído

| Etapa | Data | Resumo | Registro |
|---|---|---|---|
| E00–E01b | 2026-09-30 | Planejamento, pesquisa, arquitetura, plano; Supabase/GitHub Actions, Gemini, memória comercial, MEI; seeds (portfólio, perfil MEI, interações), `.env.example`; ADR-001–015. **E01b parcial** | `docs/history/sessions/2026-09-30-E00.md`, `…-E00b.md`, `…-E01b.md` |
| E02 | 2026-10-01 | Django 5.2 + psycopg3, schema `radar`, admin, Makefile, CI com Postgres, `repo_checks`, ADR-016. CI verde | `…-10-01-E02.md` |
| E03 | 2026-10-01 | 9 entidades, `record_evidence` (ADR-004), opt-out (`usable()`), admin com selos observado × inferido, catálogo de 12 serviços (`make seed`); 202 testes; ADR-017/018/019. CI verde. Aplicado no Supabase pelo titular (P4) | `…-10-01-E03.md` |
| E03b | 2026-10-01 | `Interaction`, `PortfolioItem`, `CompanyProfile`, derivados por signals, admin (histórico na organização, "próximas ações"), `load_company_profile`/`import_portfolio`/`import_interactions`, dedupe de organização; 271 testes; ADR-020. **M1 funcional; datas das propostas aguardam P1/P2** | `…-10-01-E03b.md` |
| E04 | 2026-10-01 | `collection/`: fetcher educado (robots, rate limit, 304, retry, limites), `CollectionRun`/`RawDocument`/`Evidence.raw_document`, runner + `collect` (`--all/--dry-run/--limit`), `seed_csv`, retenção; 337 testes; ADR-021 | `…-10-01-E04.md` |
| E12 | 2026-10-01 | `Municipality` (5.571 linhas, `load_municipalities`), FK `municipality` com resolução ao salvar (`resolve_municipalities`), `scoring/geo.py` (R0–R5, 5 perfis, gate, dado ausente); 395 testes; ADR-022. **Bauru está a ≈ 111 km, não ~100** | `…-10-01-E12.md` |
| E17/E17b | 2026-10-01 | `sesc-sp-unidades` (42 curadas), `inep-escolas` (privadas ≤ 150 km + polos) e `similar_orgs.csv`, tags de vocabulário fechado; ADR-023/024. **Listas e layout do INEP não conferidos (P11, P12)** | `…-10-01-E17.md`, `…-E17b.md` |
| E18 | 2026-10-01 | `collection/search/` (Serper/Brave, cache `SearchQuery`, teto), `extraction/website.py`, `find_websites`; evidência inferida; ADR-025. **Busca real não testada (P13)** | `…-10-01-E18.md` |
| E19 | 2026-10-01 | `extraction/contacts.py`, `contact_finder.py`, `extract_contacts`; evidência observada, opt-out antes e depois; ADR-026. **Sites reais não testados (P14)** | `…-10-01-E19.md` |
| E20 | 2026-10-01 | `scoring/match_rules.py` + `matching.py` (regras em dados), `match_services`; razões com evidência, prova só de portfólio público e confirmado (sem prova: força ×0,7), máx. 3 por organização; 19 testes; ADR-027. **Regras e forças são hipóteses; nada rodado em dados reais (P15)** | `…-10-01-E20.md` |
| E05–E09 | 2026-10-01 | Conectores de oportunidades em `collection/connectors/`: `devpost` (**rodou de verdade**, P16), `itch_jams` (+ prazo e `stats` no fetcher), `html_watch` (genérico, 9 `Source`), `querido_diario`, `mapas_culturais`; todos desabilitados até conferir termos, datas só se inequívocas, fixtures **sintéticas**; ADR-028–032. **Formatos reais não conferidos (P17–P20)** | `…-10-01-E05.md` a `…-E09.md` |
| E10 | 2026-10-01 | `llm/`: `AIService.run(tarefa, entrada)`, estratégias por tarefa, cache, teto de custo, `LLMCall`; HTTP direto; ADR-033. **Fumaça real do Gemini free OK (P21)** | `…-10-01-E10.md` |
| E11 | 2026-10-01 | `extraction/` (regras + Gemini free → Haiku), campo crítico só na coluna se a citação é verificada, `make extract`; 709 testes; ADR-034. **Sem PDF; acurácia não medida (P22)** | `…-10-01-E11.md` |
| E13 | 2026-10-01 | `scoring/`: `Score` (migration `scoring.0001`), gates (prazo, território, requisito da empresa), 6 fatores, elegibilidade MEI, confiança K, perfis em dados, `make rescore`, breakdown no admin; 784 testes; ADR-035. **Pesos são hipótese; nada rodado em dados reais (P23)** | `…-10-01-E13.md` |
| E14 | 2026-10-03 | `core/services/triage.py` + ações em massa no admin de oportunidades (interessante, em andamento, concluído, descartar com motivo, voltar), coluna e filtro «Não triadas»; `reports/metrics.py` + `make metrics` (M1–M9, «sem dados» quando vazio); sem migration; 799 testes; ADR-036. **Nada medido com dados reais (P24)** | `…-10-03-E14.md` |
| E15 | 2026-10-03 | `reports/digest.py` + `make digest`: `data/digests/AAAA-Www.html/.md` (follow-ups, top-10 com «por quê», prazos ≤ 14 dias, novidades, bloqueadas por requisito com valor somado, fontes, custo do mês); nada gated/descartado nas listas; e-mail opcional só para a lista `DIGEST_EMAIL_TO`; sem migration; 817 testes; ADR-037. **Nada lido com dados reais (P25)** | `…-10-03-E15.md` |
| E16 | 2026-10-03 | `manage.py run_pipeline` (`make pipeline`: collect→extract→match→rescore→digest, falha isolada por etapa, log só com contagens); `pipeline.yml` (diário + `workflow_dispatch`, migrate antes, digest só por e-mail às segundas, renova o agendamento); `backup.yml` + `scripts/backup.sh`/`restore_backup.sh` (`pg_dump` → age, artefato 30 dias); `docs/operations/runbook.md`; sem migration; ADR-038. **Restauração testada só em PostgreSQL local; Actions nunca rodou com Secrets (P26)** | `…-10-03-E16.md` |
| E21 | 2026-10-03 | `scoring/leads.py` + `factors/lead.py`: `lead.sesc` (SESC e parecidas) e `lead.school_course`; V (ticket do catálogo), F (match + prova), C (rede com case, relacionamento, resposta, MEI), T (sazonalidade escolar, follow-up), A (geo × contato); gate de opt-out; contatados saem como «em andamento», nunca como novos; `make rescore` cobre leads; admin de organizações com nota e breakdown; digest com «Leads da semana» e «Em andamento»; migration `scoring.0002`; 837 testes; ADR-039. **Pesos e faixas são hipótese (P27)** | `…-10-03-E21.md` |

## Pendências do humano

| # | Ação | Onde registrar |
|---|---|---|
| P1 | Game Lab (SESC Araraquara): data, nº de alunos, cargo do contato | copiar `data/seeds/interactions.template.csv` → `data/private/interactions.csv`, preencher e rodar `make memory` (completa os registros `pendente`) |
| P2 | Propostas SESC Bauru, Ribeirão Preto, São Carlos: data, canal, cargo, serviço proposto, status, próxima ação | idem (**não** commitar) |
| P3 | Protótipo: nome e URL; gênero/ano/engine de AstroDash e Tirania; confirmar se scorpionbits.com foi feito por vocês | `data/seeds/portfolio.csv` |
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
| P16 | **E05:** já coletou (45 vistos, 21 novos; formato confere). Falta revisar 10 hackathons no admin e salvar uma resposta real como fixture. **Demora (2–3 min/página, processo não saía):** rode de novo e mande a linha `tempo —` da saída (ADR-029) | `docs/decisions/ADR-028-conector-devpost.md` |
| P17 | **E06:** conferir termos/robots.txt do itch.io; `make seed`, marcar «coleta permitida» e habilitar `itch-jams` no admin; `make collect DRY=1` e `make collect` na sua máquina (não no SQL Editor); revisar 10 jams e salvar uma página real como fixture | `docs/decisions/ADR-029-conector-itch-jams-e-medicao-do-fetcher.md` |
| P18 | **E07:** conferir as 9 URLs de `html_watch` (de memória) e os termos; `make seed`, habilitar **uma** página por vez no admin; `make collect DRY=1` e `make collect`; ajustar `selector`/`link_patterns` em `Source.config` se vier ruído; revisar 10 itens e salvar uma página real como fixture | `docs/decisions/ADR-030-conector-html-watch-generico.md` |
| P19 | **E08:** conferir termos da API do Querido Diário; `git pull`, `make seed`, habilitar `querido-diario` no admin; `make collect DRY=1` e `make collect` (município sem diário vira erro); revisar 10 ocorrências, ajustar `queries`/`exclude_patterns` e salvar uma resposta real como fixture | `docs/decisions/ADR-031-conector-querido-diario.md` |
| P20 | **E09:** conferir as instâncias de `config.instances` (URLs de memória) e os termos; `git pull`, `make seed`, habilitar `mapas-culturais` no admin; `make collect DRY=1` e `make collect`; revisar 10 oportunidades, ajustar `keywords` e salvar uma resposta real como fixture | `docs/decisions/ADR-032-conector-mapas-culturais.md` |
| P21 | **E10:** `git pull`, `make migrate` (cria `llm_llmcall`), chaves só no `.env` (`GEMINI_API_KEY_FREE`, opcional `GEMINI_API_KEY_PAID`/`ANTHROPIC_API_KEY`; nunca no chat); `make llm-smoke` (**feito pelo titular: Gemini free `gemini-3.1-flash-lite` respondeu `OK`**; o `2.5-flash-lite` dá 404) e `make llm-usage`; confira preços em `llm/pricing.py` | `docs/decisions/ADR-033-camada-de-ia.md` |
| P22 | **E11:** `git pull` (sem migration); `make extract DRY=1 N=20` e depois `make extract N=20` na sua máquina (não no SQL Editor; usa a chave Gemini free já no `.env`); revise 20 no admin e preencha `docs/research/extraction-eval.md` (meta: prazo e requisitos ≥ 90% certos ou `unknown`, zero errado confiante); anote páginas PDF/`sem-texto` | `docs/decisions/ADR-034-extracao-de-oportunidades.md` |
| P23 | **E13:** `git pull`, `make migrate` (cria `scoring_score`), `make rescore DRY=1` e depois `make rescore` na sua máquina (não no SQL Editor); no admin (Oportunidades, coluna «pontuação») leia o breakdown de 10: nota faz sentido? Anote os erros e ajuste pesos em `scoring/profiles.py` (suba `SCORING_VERSION`) | `docs/decisions/ADR-035-score-de-oportunidades.md` |
| P24 | **E14:** `git pull`; `make rescore`; no admin (Oportunidades) filtre «Não triadas», cronometre a triagem de 20 itens (meta < 5 min) e rode `make metrics`; anote o tempo semanal (M6) aqui (M6 é autodeclarado) | `docs/decisions/ADR-036-triagem-e-metricas.md` |
| P25 | **E15:** `git pull`, `make rescore` e `make digest` na sua máquina (não no SQL Editor; sem migration); abra `data/digests/AAAA-Www.html`: leu em < 5 min? links do admin abrem (ajuste `DIGEST_BASE_URL`)? algo faltando ou sobrando? E-mail só se quiser (`DIGEST_EMAIL_TO` com os e-mails da equipe, SMTP no `.env`; `make digest MAIL=1`) | `docs/decisions/ADR-037-digest-semanal.md` |
| P26 | **E16:** seguir `docs/operations/runbook.md` §2: `age-keygen` (guardar a privada em 2 lugares), Secrets `DATABASE_URL`, `DJANGO_SECRET_KEY`, `BACKUP_AGE_PUBLIC_KEY` (+ chaves de IA/busca/SMTP que quiser); *Run workflow* `Pipeline` com `dry_run`, depois sem; *Run workflow* `Backup`, baixar o artefato e **restaurar no radar-dev** (`scripts/restore_backup.sh`) | `docs/decisions/ADR-038-agendamento-e-backups.md` |
| P27 | **E21:** `git pull`, `make migrate` (`scoring.0002`), `make match` e `make rescore` na sua máquina (não no SQL Editor); no admin (Organizações, coluna «pontuação») leia o breakdown de 5 leads; confira que SESC Bauru, Ribeirão Preto e São Carlos aparecem «Em andamento» (registre as propostas: P2) e que o digest traz «Leads da semana». Ajuste pesos/sazonalidade em `scoring/profiles.py` | `docs/decisions/ADR-039-score-de-leads.md` |

## Decisões vigentes (ver `docs/decisions/README.md`)

ADR-001 Django/admin · 003 IA último recurso · 004 evidência · 005 humano no controle ·
006 score explicável · 007 fontes oficiais · 008 CLAUDE.md ≤ 150 linhas · 009 escopo do MVP ·
010 Supabase + GitHub Actions + admin local · 011 modelo por tarefa (Gemini na extração) ·
012 memória comercial e portfólio · 013 elegibilidade MEI · 014 repositório público ·
015 cobertura de atividades do MEI (CNAE) · 016 schema `radar` + pooler em modo sessão ·
017 Evidence/Triage por GenericForeignKey · 018 listas como ArrayField ·
019 UI web + API do Django (sem executável, sem acesso direto ao Supabase) ·
020 regras do relacionamento derivado (datas, pendentes sem data inventada, dedupe) · 021 regras da coleta (robots, bloqueio, dry-run, retenção) ·
022 municípios do IBGE e perfis geográficos como dado · 023 SESC-SP e escolas INEP · 024 parecidas com o SESC ·
025 site oficial: busca com cache + validação que erra para «ambíguo» · 026 contatos públicos institucionais · 027 matching por regras ·
028–032 conectores (Devpost, itch.io + medição, `html_watch`, Querido Diário, Mapas Culturais: datas sem chute, fonte desabilitada até conferir) ·
033 camada de IA: tarefas × estratégias, HTTP sem SDK · 034 extração: citação obrigatória, campo crítico só se verificado ·
035 score de oportunidades: gates, fatores, confiança, pesos como dado versionado · 036 triagem em massa e métricas M1–M9 ·
037 digest semanal: arquivo local, listas com limite, e-mail só para a equipe ·
038 agendamento diário no Actions, backup age semanal, nada de dado em artefato público ·
**039 score de leads: mesmo motor, gate de opt-out, contatado = «em andamento»**.

## Problemas abertos

- Coordenadas dos municípios vêm de conjunto derivado do IBGE (sedes), não do IBGE direto (rede bloqueada): conferir quando possível (ADR-022).
- Lista SESC-SP, layout do INEP, organizações parecidas e URLs oficiais são de memória, nada conferido na fonte (P11, P12, ADR-023/024); chamamentos do SESC-SP ficam fora do `html_watch` até haver URL (ADR-030).
- E18: Serper/Brave só da documentação, sites só em JS caem em ambíguo (ADR-025). E19: nenhum site real testado; e-mail ofuscado/JS não é lido (ADR-026). E20: regras e forças não calibradas (ADR-027).
- Endpoints das fontes **não testados** (E01); E08: formato da API do Querido Diário só da documentação (ADR-031); E09: instâncias e JSON do Mapas Culturais só de memória (ADR-032); E06: HTML do itch.io só de memória (ADR-029); E07: URLs das páginas monitoradas também (P18, ADR-030). Devpost conferido pelo uso real.
- Devpost lento (2–3 min/página, P16, ADR-029). E10: preços do Gemini pago a conferir (P21). E11: PDF não é lido, prompt só testado com texto sintético (P22). E13: pesos, faixas e valores dos fatores são hipótese (P23, ADR-035); pesos de leads (E21) também são hipótese (P27).
- Supabase (projeto **Prospection**): migrations aplicadas pelo titular até a E03b. **Não conferido por nós:** a Data API sem as tabelas expostas; migrations seguintes só no PostgreSQL local, então `make migrate` após cada merge (P21 para `llm`).
- Valores iniciais do catálogo (palavras-chave, tipos-alvo, CNAEs exigidos) são **hipóteses** editáveis no admin;
  CNAEs a confirmar com o contador (P7). Preços não estão no repositório (ficam no banco).
- `COMPANY_CNPJ` e `CONTACT_EMAIL` só no `.env`: sem eles `make memory` deixa CNPJ/e-mail do perfil em branco.
- Dedupe de organização por nome varre a tabela em Python (ADR-020): indexar chave normalizada quando a base crescer (E04+).
- Aviso do Django 6 sobre `URLField` nos testes; CI usa `checkout@v4`/`setup-uv@v5` (Node 20). Limites de free tier (Supabase, Gemini, Serper/Brave) e créditos do AI Pro: confirmar ao criar as contas.
- `schedule` do GitHub Actions desliga após 60 dias sem commits (repositório público) — mitigação em ADR-014.

## Riscos de negócio a acompanhar

- **Janela escolar 2027 (out–dez/2026)**: manter prospecção manual de escolas e follow-up das
  propostas SESC em paralelo ao desenvolvimento.
- **MEI**: CNAEs cobrem ensino e treinamento em informática, mas não software/web/jogos sob
  encomenda (ADR-015). Editais com exigência de 2 anos de CNPJ: elegível só a partir de **10/04/2027**.
- Limite de faturamento do MEI: R$ 81 mil/ano.
