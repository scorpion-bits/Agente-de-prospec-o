# STATUS — Radar Scorpion Bits

> Estado vivo do projeto. Atualizar ao fim de **toda** etapa. Limite: 120 linhas.
> Última atualização: **2026-09-30** (E00)

## Onde estamos

**Fase 0 — Fundação.** Planejamento concluído. **Nenhum código de produto ainda.**
Repositório contém apenas documentação.

## Próxima etapa

➡️ **E01 — Validação de fontes + baseline manual (spike)**
Detalhes: `docs/plan/fase-0-fundacao.md`, seção E01.
⚠ Deve rodar numa máquina com acesso normal à internet (o ambiente de planejamento
bloqueou itch.io, devpost.com e queridodiario). Se a sessão do Claude Code também estiver
sem acesso, o humano executa os scripts do spike localmente e cola os resultados.

Depois: E02 (esqueleto) → E03 (modelo de dados) → E04 (infra de coleta).

## Concluído

| Etapa | Data | Resumo | Registro |
|---|---|---|---|
| E00 | 2026-09-30 | Pesquisa, produto, MVP, arquitetura, agentes, custos, fontes, riscos, plano E00–E30, 9 ADRs, sistema de memória | `docs/history/sessions/2026-09-30-E00.md` |

## Em andamento

Nada.

## Decisões tomadas (ver `docs/decisions/README.md`)

- ADR-001 Monólito Python/Django, admin como UI do MVP
- ADR-002 SQLite → PostgreSQL no deploy compartilhado
- ADR-003 IA como último recurso; camada `llm/` multi-provedor com teto
- ADR-004 Evidência obrigatória; fato observado × inferência
- ADR-005 Sem envio automático de mensagens
- ADR-006 Score determinístico, explicável, por perfis
- ADR-007 Fontes oficiais/abertas primeiro; sem scraping de LinkedIn/Google
- ADR-008 CLAUDE.md ≤ 150 linhas; memória em docs/
- ADR-009 MVP = oportunidades + escolas/SESC; empresas (CNPJ) pós-MVP

## Perguntas abertas (para o humano)

1. **Ordem das fases:** seguir Fase 1 (oportunidades) antes da Fase 3 (escolas), ou a
   ordem alternativa que antecipa escolas por causa da janela de planejamento out–dez?
   (ver `PLAN.md` → "Ordem alternativa")
2. Em que máquina o sistema vai rodar no MVP (SO, RAM, GPU)? Define se Ollama local é viável.
3. Quantas pessoas vão usar? Precisa de acesso fora da máquina local já no MVP?
4. Existe e-mail/domínio institucional para o User-Agent e para o digest?
5. Teto mensal de gasto com APIs (proposta: **US$ 5**, máximo US$ 10)?
6. Raio máximo para cursos presenciais recorrentes (proposta: 120 km)?
7. Plano de formalização (MEI/ME)? Afeta elegibilidade em editais/licitações.
8. Quais unidades SESC já foram contatadas/atendidas? (entra na lista semente como relacionamento prévio)
9. Contas gratuitas a criar quando chegar a hora: Google AI Studio (Gemini), Groq,
   Brave Search API ou Serper, (opcional) Anthropic API com limite de gasto.

## Problemas abertos

- Endpoints das fontes **não testados** (ver E01).
- Preços/cotas de free tiers mudam com frequência — revalidar na E10/E18.

## Riscos de negócio a acompanhar

- **Janela escolar 2027 (out–dez/2026)**: o radar de escolas não ficará pronto a tempo
  se seguirmos a ordem padrão. Recomendação: prospecção manual de escolas/SESCs **em
  paralelo** agora, usando o próprio Game Lab como argumento.
- Editais que exigem CNPJ: sem formalização, parte relevante das oportunidades é inelegível.

## Métricas (a partir da E14)

Ainda sem dados.
