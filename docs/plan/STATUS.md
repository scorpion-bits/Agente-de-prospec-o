# STATUS — Radar Scorpion Bits

> Estado vivo do projeto. Atualizar ao fim de **toda** etapa. Limite: 120 linhas.
> Última atualização: **2026-10-01** (E03)

## Onde estamos

**Fase 0 — Fundação.** Prontos: planejamento (E00, E00b), esqueleto (E02) e **modelo de dados núcleo +
admin + catálogo de serviços (E03)**: 9 entidades, `record_evidence`, opt-out, 12 serviços.
**E01b parcial** e **P4 parcial** (faltam ações do humano, abaixo).
**Repositório público** → regras de dados em ADR-014. Comandos: `make help`.

## Próxima etapa

➡️ **E03b — Memória comercial, portfólio e perfil da empresa** (`fase-0-fundacao.md`) → **M1: "Já falamos
com eles?" respondido no admin**. O código não depende do humano (linhas `pendente` entram sem datas
inventadas), mas o resultado útil depende de P1–P3. Dica: `core/models.py` tem ~1.000 linhas; ao somar
`Interaction`/`PortfolioItem`/`CompanyProfile`, dividir em pacote `core/models/` (não gera migration).

➡️ **E01 — Validação de fontes + baseline manual** continua pendente: precisa de máquina com internet
normal (o ambiente do Claude bloqueia itch.io, devpost.com, queridodiario e supabase.co). Só bloqueia a Fase 1/3.

Depois (ordem em `PLAN.md`): E04 → E12 → E17 → E17b → E18 → E19 (**M2**).

## Concluído

| Etapa | Data | Resumo | Registro |
|---|---|---|---|
| E00 | 2026-09-30 | Planejamento, pesquisa, arquitetura, plano, ADR-001–009 | `docs/history/sessions/2026-09-30-E00.md` |
| E00b | 2026-09-30 | Complemento: Supabase/GitHub Actions, Gemini, memória comercial, MEI; ADR-010–013 | `…-E00b.md` |
| E01b (parcial) | 2026-09-30 | Seeds (portfólio, perfil MEI, template de interações), `.env.example`, checklist de contas, ADR-014/015 | `…-E01b.md` |
| E02 | 2026-10-01 | Django 5.2 + psycopg3, schema `radar`, admin, Makefile, CI com Postgres, `repo_checks`, ADR-016. CI verde | `…-10-01-E02.md` |
| E03 | 2026-10-01 | 9 entidades, `record_evidence` (ADR-004), opt-out (`usable()`), admin com selos observado × inferido, catálogo de 12 serviços (`make seed`); 202 testes; ADR-017/018/019. CI verde. **Falta aplicar no Supabase (titular, P4)** | `…-10-01-E03.md` |

## Pendências do humano

| # | Ação | Onde registrar |
|---|---|---|
| P1 | Game Lab (SESC Araraquara): data, nº de alunos, cargo do contato | copiar `data/seeds/interactions.template.csv` → `data/private/interactions.csv` |
| P2 | Propostas SESC Bauru, Ribeirão Preto, São Carlos: data, canal, cargo, serviço proposto, status, próxima ação | idem (**não** commitar) |
| P3 | Protótipo: nome e URL; gênero/ano/engine de AstroDash e Tirania; confirmar se scorpionbits.com foi feito por vocês | `data/seeds/portfolio.csv` |
| P4 | **PARCIAL.** Projeto Supabase criado (identificador e chaves ficam **fora do git**). Falta: **você** rodar `make migrate` e `make seed` com a string do pooler em modo sessão, conferir pelo SQL Editor, e dizer se é `radar-dev` ou `radar-prod` (criar o outro) | `docs/operations/supabase-setup.md` |
| P5 | Ativar benefícios Google AI Pro (conta pessoal do titular) + chaves AI Studio | A2, A3 |
| P6 | Escolher busca (Serper ou Brave); gerar chaves age para backup | A4, A5 |
| P7 | Falar com o **contador** sobre CNAEs de software/web/jogos e migração para ME; ajustar `mei_coverage` no admin | ADR-015 |
| P8 | Decidir: manter repositório público (recomendado agora, com ADR-014) ou privado | ADR-014 |
| P9 | **Vercel** está conectado a este repositório (ADR-010: sem Vercel no MVP): tenta um deploy a cada push, sem ter o que construir, e, se receber `DATABASE_URL`, exporia o admin com contatos (LGPD). Desconectar ou usar *Ignored Build Step* até existir o front | painel do Vercel |
| P10 | **UI nova** decidida: web + API do Django, visual do site (ADR-019). Falta replanejar a E29 (front + API) e escolher tecnologia/hospedagem, **depois** de E03b/E04 | `docs/product/ui-direction.md` |

## Decisões vigentes (ver `docs/decisions/README.md`)

ADR-001 Django/admin · 003 IA último recurso · 004 evidência · 005 humano no controle ·
006 score explicável · 007 fontes oficiais · 008 CLAUDE.md ≤ 150 linhas · 009 escopo do MVP ·
010 Supabase + GitHub Actions + admin local · 011 modelo por tarefa (Gemini na extração) ·
012 memória comercial e portfólio · 013 elegibilidade MEI · 014 repositório público ·
015 cobertura de atividades do MEI (CNAE) · 016 schema `radar` + pooler em modo sessão ·
**017 Evidence/Triage por GenericForeignKey** · **018 listas como ArrayField** ·
**019 UI web + API do Django (sem executável, sem acesso direto ao Supabase)**.

## Problemas abertos

- Endpoints das fontes **não testados** (E01).
- Conexão ao **Supabase real** e Data API sem as tabelas: não verificado (P4); validado só em PostgreSQL 16 local.
- Valores iniciais do catálogo (palavras-chave, tipos-alvo, CNAEs exigidos) são **hipóteses** editáveis no admin;
  CNAEs a confirmar com o contador (P7). Preços não estão no repositório (ficam no banco).
- `core/models.py` com ~1.000 linhas: dividir em pacote na E03b (ver Próxima etapa).
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
