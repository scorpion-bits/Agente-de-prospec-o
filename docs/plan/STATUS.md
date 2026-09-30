# STATUS — Radar Scorpion Bits

> Estado vivo do projeto. Atualizar ao fim de **toda** etapa. Limite: 120 linhas.
> Última atualização: **2026-09-30** (E00b — complemento de contexto)

## Onde estamos

**Fase 0 — Fundação.** Planejamento concluído e revisado com o novo contexto (domínio,
portfólio, SESC validado, MEI, Supabase/Vercel, Gemini). **Nenhum código de produto ainda.**

## Próxima etapa

➡️ **E01 — Validação de fontes + baseline manual** e **E01b — Inventário do negócio e
contas** (podem ser feitas em paralelo; E01b é majoritariamente humana).
Detalhes: `docs/plan/fase-0-fundacao.md`.
⚠ A E01 precisa de máquina com internet normal (o ambiente de planejamento bloqueou
itch.io, devpost.com e queridodiario).

Depois (ordem recomendada em `PLAN.md`): E02 → E03 → **E03b (marco M1: memória comercial)**
→ E04 → E12 → E17 → E17b → E18 → E19 (**M2: instituições com contatos**) → E20 → radar.

## Concluído

| Etapa | Data | Resumo | Registro |
|---|---|---|---|
| E00 | 2026-09-30 | Pesquisa, produto, MVP, arquitetura, agentes, custos, fontes, riscos, plano, ADR-001–009, memória do projeto | `docs/history/sessions/2026-09-30-E00.md` |
| E00b | 2026-09-30 | Análise de impacto do novo contexto; ADR-010–013; hospedagem, IA multimodelo, memória comercial, portfólio, MEI, SESC e similares; plano reordenado (E01b, E03b, E17b) | `docs/history/sessions/2026-09-30-E00b.md` |

## Em andamento

Nada.

## Decisões vigentes (ver `docs/decisions/README.md`)

- ADR-001 Monólito Python/Django, admin como UI do MVP
- ADR-003 IA como último recurso · ADR-011 modelo por tarefa; Gemini principal na extração
- ADR-004 Evidência obrigatória; fato observado × inferência
- ADR-005 Sem envio automático de mensagens
- ADR-006 Score determinístico e explicável · ADR-013 elegibilidade pelo perfil MEI
- ADR-007 Fontes oficiais/abertas primeiro
- ADR-008 CLAUDE.md ≤ 150 linhas
- ADR-009 Escopo do MVP · ADR-012 memória comercial e portfólio no MVP
- ADR-010 Supabase Postgres + workers no GitHub Actions + admin local; sem Vercel no MVP
  (substitui ADR-002)

## Perguntas abertas (para o humano — maioria resolvida na E01b)

1. Unidade, data e nº de alunos do Game Lab; datas, cargos dos contatos e status das
   propostas a SESC Bauru, Ribeirão Preto e São Carlos.
2. URLs públicas de AstroDash, Tirania, protótipo e da página no itch.io.
3. Data de abertura e CNAEs do MEI (define elegibilidade — ex.: ProAC de jogos exige sede há > 2 anos).
4. E-mail `@scorpionbits.com` para User-Agent e digest.
5. Repositório privado ou público? (afeta minutos e `schedule` do GitHub Actions)
6. Ativar os benefícios de desenvolvedor do Google AI Pro (créditos ~US$ 10/mês) — quem é o titular?
7. Teto mensal de dinheiro novo com APIs (proposta: **US$ 5**).
8. Raio para cursos presenciais fora dos polos (proposta: interior até ~150 km).
9. Hardware disponível para modelo local (opcional; não bloqueia nada).

## Problemas abertos

- Endpoints das fontes **não testados** (E01).
- Limites de free tier (Supabase, GitHub Actions, Gemini, Brave) levantados por fontes
  secundárias — confirmar na E01b.
- `schedule` do GitHub Actions em repositório privado: relatos de restrição — testar na E01b.

## Riscos de negócio a acompanhar

- **Janela escolar 2027 (out–dez/2026)**: mesmo com a trilha de leads antecipada, prospecção
  manual de escolas e follow-up das propostas SESC devem continuar **em paralelo** agora.
- Limite do MEI (R$ 81 mil/ano): contratos maiores exigem migrar para ME.
- Editais com tempo mínimo de CNPJ/sede podem bloquear o MEI se for recente.

## Métricas (a partir da E14)

Ainda sem dados.
