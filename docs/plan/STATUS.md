# STATUS — Radar Scorpion Bits

> Estado vivo do projeto. Atualizar ao fim de **toda** etapa. Limite: 120 linhas.
> Última atualização: **2026-09-30** (E01b, parte automatizável)

## Onde estamos

**Fase 0 — Fundação.** Planejamento concluído (E00, E00b). **E01b parcial**: seeds e
documentação prontos; faltam ações do humano (lista abaixo). Nenhum código de produto ainda.
**Repositório público** → regras de dados em ADR-014.

## Próxima etapa

➡️ **E01 — Validação de fontes + baseline manual** (precisa de máquina com internet normal; o
ambiente de planejamento bloqueou itch.io, devpost.com e queridodiario).
Em paralelo, o humano fecha as pendências P1–P6 abaixo.

➡️ **E02 — Esqueleto** já pode começar sem esperar o Supabase: usar PostgreSQL local/CI e trocar
`DATABASE_URL` quando o projeto `radar-dev` existir (P4).

Depois (ordem em `PLAN.md`): E03 → **E03b (M1: memória comercial)** → E04 → E12 → E17 → E17b → E18 → E19 (**M2**).

## Concluído

| Etapa | Data | Resumo | Registro |
|---|---|---|---|
| E00 | 2026-09-30 | Planejamento, pesquisa, arquitetura, plano, ADR-001–009 | `docs/history/sessions/2026-09-30-E00.md` |
| E00b | 2026-09-30 | Complemento: Supabase/GitHub Actions, Gemini, memória comercial, MEI; ADR-010–013 | `…-E00b.md` |
| E01b (parcial) | 2026-09-30 | Seeds (portfólio, perfil MEI, template de interações), `.env.example`, checklist de contas, ADR-014/015 | `…-E01b.md` |

## Pendências do humano (fecham a E01b)

| # | Ação | Onde registrar |
|---|---|---|
| P1 | Game Lab (SESC Araraquara): data, nº de alunos, cargo do contato | copiar `data/seeds/interactions.template.csv` → `data/private/interactions.csv` |
| P2 | Propostas SESC Bauru, Ribeirão Preto, São Carlos: data, canal, cargo, serviço proposto, status, próxima ação | idem (**não** commitar) |
| P3 | Protótipo: nome e URL; gênero/ano/engine de AstroDash e Tirania; confirmar se scorpionbits.com foi feito por vocês | `data/seeds/portfolio.csv` |
| P4 | Criar Supabase `radar-dev` e `radar-prod`; pooler; senha em gerenciador | `accounts-checklist.md` A1 |
| P5 | Ativar benefícios Google AI Pro (conta pessoal do titular) + chaves AI Studio | A2, A3 |
| P6 | Escolher busca (Serper ou Brave); gerar chaves age para backup | A4, A5 |
| P7 | Falar com o **contador** sobre CNAEs de software/web/jogos e migração para ME | ADR-015 |
| P8 | Decidir: manter repositório público (recomendado agora, com ADR-014) ou privado | ADR-014 |

## Decisões vigentes (ver `docs/decisions/README.md`)

ADR-001 Django/admin · 003 IA último recurso · 004 evidência · 005 humano no controle ·
006 score explicável · 007 fontes oficiais · 008 CLAUDE.md ≤ 150 linhas · 009 escopo do MVP ·
010 Supabase + GitHub Actions + admin local · 011 modelo por tarefa (Gemini na extração) ·
012 memória comercial e portfólio · 013 elegibilidade MEI · **014 repositório público** ·
**015 cobertura de atividades do MEI (CNAE)**.

## Problemas abertos

- Endpoints das fontes **não testados** (E01).
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
