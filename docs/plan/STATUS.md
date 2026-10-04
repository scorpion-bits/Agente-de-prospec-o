# STATUS — Radar Scorpion Bits

> Estado vivo do projeto. Atualizar ao fim de **toda** etapa. Limite: 120 linhas.
> Última atualização: **2026-10-04** (E24)

## Onde estamos

**Fase 0 — Fundação.** Prontos E00–E04, E12, E17/E17b, E18 (site oficial), E19 (contatos) e E20 (matching); detalhes na tabela abaixo.
Marco **M1** (memória comercial) funcional. Comandos do dia a dia: `make help`. **E05–E09** (conectores de oportunidades; ADR-028–032)
com fontes desabilitadas até conferir termos. Prontas também: **E10** (IA `llm/`, ADR-033), **E11** (extração, P22), **E13** (score, P23),
**E14** (triagem/métricas), **E15** (digest), **E16** (agendamento/backups), **E21** (score de leads; migrations `scoring.0001/0002`) (P24–P27),
**E22** (ferramenta de go/no-go, ADR-040; a decisão espera uso real, P28), **E27** (PNCP, ADR-041, P29) **E26** (sinais de necessidade web,
ADR-042, P30) **E25** (empresas do CNPJ aberto, ADR-043, P31) a **ferramenta da E30** (calibração de pesos, ADR-044, P32) e a **E23** (pipeline leve com `Deal`, ADR-045, P33; migration `core.0006`) e a **E24** (rascunho de abordagem, ADR-046, P34; migration `core.0007`). **E01b parcial**; migrations aplicadas no Supabase pelo titular (P4). **Repositório público** → ADR-014.

## Próxima etapa

➡️ **Uso real, depois a decisão E22** (e `make calibrate` com ≥ 50 triagens, P32) (`make evaluate`, ≥ 4 semanas com triagem semanal). Antes, o humano faz P26, P27 e P28. Depois, o resto da Fase 4
(E28, E29…) só se a avaliação for «continuar». **E23 e E24 foram adiantadas** (E23 sem IA; E24 só gasta com chave paga, ~US$ 0,01/rascunho): adotá-las só depende do P28. Restam E28 (agente de pesquisa, condicional) e E29 (UI online). **E01 (validação de fontes)** segue pendente: precisa de internet normal (P11, P12).

## Concluído

| Etapa | Data | Resumo | Registro |
|---|---|---|---|
| E00–E01b | 2026-09-30 | Planejamento, pesquisa, arquitetura, plano; Supabase/GitHub Actions, Gemini, memória comercial, MEI; seeds (portfólio, perfil MEI, interações), `.env.example`; ADR-001–015. **E01b parcial** | `docs/history/sessions/2026-09-30-E00.md`, `…-E00b.md`, `…-E01b.md` |
| E02–E03 | 2026-10-01 | Django 5.2 + psycopg3, schema `radar`, admin, Makefile, CI, `repo_checks` (ADR-016); 9 entidades, `record_evidence` (ADR-004), opt-out (`usable()`), admin com selos observado × inferido, catálogo de 12 serviços (`make seed`); ADR-017/018/019. Aplicado no Supabase pelo titular (P4) | `…-10-01-E02.md`, `…-E03.md` |
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
| E14–E16 | 2026-10-03 | **E14** triagem em massa no admin (interessante, em andamento, concluído, descartar com motivo) + `make metrics` (M1–M9; ADR-036, P24). **E15** digest semanal `make digest` (follow-ups, top-10 com «por quê», prazos, novidades, bloqueadas por requisito, custo; e-mail só para `DIGEST_EMAIL_TO`; ADR-037, P25). **E16** `make pipeline` (collect→extract→match→rescore→digest, falha isolada por etapa), `pipeline.yml` diário, `backup.yml` (`pg_dump` → age), runbook; sem migration; ADR-038. **Nada lido/rodado com dados reais; Actions nunca rodou com Secrets (P24–P26)** | `…-10-03-E14.md`, `…-E15.md`, `…-E16.md` |
| E21/E22 | 2026-10-03 | **E21** `scoring/leads.py`: `lead.sesc` e `lead.school_course` (V, F, C, T, A), gate de opt-out, contatados saem como «em andamento»; migration `scoring.0002`; ADR-039; pesos são hipótese (P27). **E22** `make evaluate`: prontidão (≥ 28 dias e ≥ 20 triagens), M1–M9, custos e **sugestão** continuar/ajustar/parar/estender; modelo `docs/history/mvp-evaluation.md`; ADR-040; **decisão em aberto: sem uso real (P28)** | `…-10-03-E21.md`, `…-E22.md` |
| E27/E26/E25 | 2026-10-04 | **E27** `pncp`: propostas abertas do PNCP (SP × 4 modalidades) como `Opportunity(procurement)`, valor/datas/cota ME-EPP só se informados; fonte desabilitada (ADR-041, P29). **E26** `extraction/web_signals.py` + `make signals`: sinais da página inicial como `Evidence` `web.signal.*` (frescor 30 dias; fora do score; ADR-042, P30). **E25** `cnpj_estabelecimentos`: empresas ativas da região por CNAE dos arquivos locais da Receita, só nome fantasia, **sem e-mail/telefone/endereço/sócios** (LGPD); fonte desabilitada (ADR-043, P31) | `…-10-04-E27.md`, `…-E26.md`, `…-E25.md` |
| E30 (ferramenta) | 2026-10-04 | `reports/calibration.py` + `make calibrate`: fatores × triagem (média e AUC por perfil), proposta de pesos (±25%/rodada) e simulação retroativa (precisão do topo e AUC); só proposta, amostra mínima 50; sem migration; ADR-044. **Sem triagens reais: nada calibrado (P32)** | `…-10-04-E30.md` |
| E23 | 2026-10-04 | `core/models/deal.py` (`Deal`: organização + serviço + estágio + valor; `Interaction.deal`; migration `core.0006`), `core/services/pipeline.py` (máx. 2 follow-ups, 7 dias, funil «alcançaram»), admin de negócios + opt-out em massa, funil no `make metrics` (fora de M1–M9); sem IA; ADR-045. **Nunca usado com dados reais (P33)** | `…-10-04-E23.md` |
| E24 | 2026-10-04 | `core/services/outreach.py` + `OutreachDraft` (migration `core.0007`): ação «Gerar rascunho de abordagem» na organização e `make draft` (`CMP=1` = A/B Gemini 3.1 Pro × Claude Sonnet 5.5, `REPORT=1` resume avaliações); só fatos com origem (observado, portfólio público, histórico), **validador** (afirmação cita fato do tipo certo; link/número só dos fatos), estratégia `rules` como modelo sem IA; opt-out barra; nada é enviado; ADR-046. **Nunca testado com modelo real (P34)** | `…-10-04-E24.md` |

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
| P28 | **E22:** usar o radar ≥ 4 semanas (pipeline diário, triagem semanal); anotar o tempo de triagem (M6) e fazer o baseline manual da E01 (`docs/research/baseline-manual.md`, ≥ 10 itens); então `make evaluate M3=<n> M6=<min>` e preencher `docs/history/mvp-evaluation.md` com a decisão (ADR) | `docs/decisions/ADR-040-avaliacao-do-mvp.md` |
| P29 | **E27:** `git pull`, `make seed`; conferir termos/robots do PNCP e os parâmetros no Swagger (`/contratacoes/proposta`, códigos de modalidade), marcar «coleta permitida» e habilitar `pncp` no admin; `make collect DRY=1` e `make collect` (não no SQL Editor); revisar 10 contratações, ajustar `keywords`/`exclude_patterns` e salvar uma resposta real como fixture | `docs/decisions/ADR-041-conector-pncp.md` |
| P30 | **E26:** `git pull` (sem migration); depois do P13, `make signals DRY=1 N=20` e `make signals` na sua máquina (não no SQL Editor); conferir à mão 10 sites com sinal (meta: nenhum falso positivo grave; `no_viewport` é inferido) e decidir se os sinais entram como fator de Fit | `docs/decisions/ADR-042-sinais-de-necessidade-web.md` |
| P31 | **E25:** baixar `Estabelecimentos0..9.zip` e `Municipios.zip` em dadosabertos.rfb.gov.br/CNPJ para `data/cnpj/` (descompacte só `Municipios`); `make seed`, habilitar `cnpj-estabelecimentos` no admin; `make collect` (mede o tempo; meta < 30 min); conferir 20 empresas no site da Receita/Cartão CNPJ e a coluna de município; se o layout mudou, o erro/zero resultados aponta `COL`/`Municipios` | `docs/decisions/ADR-043-empresas-do-cnpj-aberto.md` |
| P32 | **E30:** depois de ≥ 50 triagens com `make rescore` feito, `make calibrate DRY=1` (sem migration; não no SQL Editor); leia a proposta; se a simulação melhora, edite `scoring/profiles.py`, suba `SCORING_VERSION`, `make rescore` e registre em ADR. Rode de novo a cada ~50 triagens | `docs/decisions/ADR-044-calibracao-de-pesos.md` |
| P33 | **E23:** `git pull`, `make migrate` (`core.0006`); no admin (Negócios) criar 1 negócio por proposta SESC já enviada (P2), ligar as interações (campo «negócio») e mover pelo funil; conferir o ritmo («follow-up devido»/«limite») e `make metrics` (funil). Testar «Registrar opt-out» em organização de teste. Ajustar 2 follow-ups/7 dias em `core/services/pipeline.py` se não servir | `docs/decisions/ADR-045-pipeline-leve.md` |
| P34 | **E24:** `git pull`, `make migrate` (`core.0007`); chaves paga no `.env` (`GEMINI_API_KEY_PAID` e/ou `ANTHROPIC_API_KEY`; nunca no chat; confira preços em `llm/pricing.py`); `make draft ORG="id1 id2…" CMP=1` em 10 organizações com match (não no SQL Editor); avalie cada rascunho no admin (Rascunhos de abordagem: ≥ 7 usáveis e toda afirmação com fato); `make draft REPORT=1`; empate → Gemini. Ajuste `core/prompts/draft_outreach_v1.txt` (suba `PROMPT_VERSION`) | `docs/decisions/ADR-046-rascunho-de-abordagem.md` |

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
039 score de leads: mesmo motor, gate de opt-out, contatado = «em andamento» ·
040 avaliação do MVP: relatório do banco, sugestão por regras, decisão humana ·
041 PNCP: propostas abertas, filtro por objeto, valor e cota ME/EPP só se informados · 042 sinais de necessidade web: só a página inicial, ausência é inferida · 043 empresas do CNPJ aberto: arquivo local, por CNAE, sem dado pessoal · 044 calibração de pesos: só proposta, amostra mínima, mudança humana · 045 pipeline leve: `Deal` com estágio humano, alerta de follow-up, funil fora do go/no-go · **046 rascunho de abordagem: fatos com origem, validador, `rules` como piso, nada enviado**.

## Problemas abertos

- Coordenadas dos municípios vêm de conjunto derivado do IBGE (sedes), não do IBGE direto (rede bloqueada): conferir quando possível (ADR-022).
- Lista SESC-SP, layout do INEP, organizações parecidas e URLs oficiais são de memória, nada conferido na fonte (P11, P12, ADR-023/024); chamamentos do SESC-SP ficam fora do `html_watch` até haver URL (ADR-030).
- E18: Serper/Brave só da documentação, sites só em JS caem em ambíguo (ADR-025). E19: nenhum site real testado; e-mail ofuscado/JS não é lido (ADR-026). E20: regras e forças não calibradas (ADR-027).
- Endpoints das fontes **não testados** (E01): Querido Diário, Mapas Culturais, itch.io, páginas do `html_watch` e PNCP (E27) só de documentação/memória (ADR-029–032, 041; P17–P20, P29). Devpost conferido pelo uso real, mas lento (2–3 min/página, P16, ADR-029).
- E10: preços do Gemini pago a conferir (P21). E11: PDF não é lido, prompt só testado com texto sintético (P22). Pesos, faixas e valores dos fatores (E13, E21) são hipótese (P23, P27).
- Supabase (projeto **Prospection**): migrations aplicadas pelo titular até a E03b. **Não conferido por nós:** a Data API sem as tabelas expostas; migrations seguintes só no PostgreSQL local, então `make migrate` após cada merge (P21 para `llm`).
- Valores iniciais do catálogo (palavras-chave, tipos-alvo, CNAEs) são **hipóteses** editáveis no admin; CNAEs a confirmar com o contador (P7). Preços ficam no banco.
- Dedupe de organização por nome varre a tabela em Python (ADR-020): indexar quando a base crescer (E25 pode trazer milhares). `COMPANY_CNPJ` e `CONTACT_EMAIL` só no `.env` (sem eles `make memory` deixa o perfil em branco).
- CI usa `checkout@v4`/`setup-uv@v5` (Node 20); aviso do Django 6 sobre `URLField`. Limites de free tier e créditos do AI Pro: confirmar ao criar as contas. `schedule` do Actions desliga após 60 dias sem commits (ADR-014).

## Riscos de negócio a acompanhar

- **Janela escolar 2027 (out–dez/2026)**: manter prospecção manual de escolas e follow-up das propostas SESC.
- **MEI**: CNAEs cobrem ensino e treinamento em informática, mas não software/web/jogos sob
  encomenda (ADR-015). Editais com exigência de 2 anos de CNPJ: elegível só a partir de **10/04/2027**. Limite de faturamento do MEI: R$ 81 mil/ano.
