# Mapa da documentação

A documentação é a **memória do projeto**. Ela existe para que qualquer sessão do
Claude Code (ou pessoa) consiga, depois de um `/clear`, entender o que estamos
construindo, por quê, onde estamos e o que fazer a seguir — lendo o mínimo possível.

## Estrutura

```text
CLAUDE.md                    contexto operacional (≤150 linhas) — sempre lido
docs/
  README.md                  este mapa
  product/                   O QUÊ e POR QUÊ
    vision.md                visão do produto e do negócio
    mvp.md                   escopo do MVP e fora do MVP
    metrics.md               métricas de sucesso
    risks.md                 riscos de produto, técnicos, financeiros e legais
    ui-direction.md          direção da interface futura (web + API) e identidade visual do site
  plan/                      QUANDO e EM QUE ORDEM
    STATUS.md                estado vivo: onde estamos, próxima etapa (atualizar sempre)
    PLAN.md                  índice de fases e etapas + template de etapa
    fase-0-fundacao.md       etapas detalhadas por fase
    fase-1-radar-oportunidades.md
    fase-2-priorizacao.md
    fase-3-leads-institucionais.md
    fase-4-pos-mvp.md
  architecture/              COMO (estado atual/alvo da arquitetura)
    overview.md              visão geral, diagrama, módulos, evolução
    data-model.md            entidades e relações
    connectors.md            contrato de fontes/conectores, coleta educada
    scoring.md               pontuação explicável
    geo-relevance.md         relevância geográfica contextual
    llm-strategy.md          quando e como usar IA; camada llm/
  agents/
    README.md                catálogo de agentes: quais existem, quais NÃO, por quê
  decisions/                 ADRs — decisões que podem ser questionadas depois
  research/                  pesquisas que embasam as decisões (negócio, ferramentas,
                             fontes, IA/custos, hospedagem, legal; baseline-manual.md vem na E01)
  history/                   conteúdo arquivado do CLAUDE.md, sessões, decisões antigas
  operations/                como operar: ciclo /clear, manutenção do CLAUDE.md, aplicar o banco no
                             Supabase (supabase-setup.md); runbook geral vem na E16
```

## Regras de manutenção

| Documento | Quando atualizar | Quem lê |
|---|---|---|
| `CLAUDE.md` | Só quando regras/estrutura mudarem | Toda sessão |
| `plan/STATUS.md` | **Fim de toda etapa** | Toda sessão |
| `plan/fase-*.md` | Ao refinar/dividir etapas | Sessão que executa a etapa |
| `architecture/*` | Quando a implementação mudar a arquitetura | Sob demanda |
| `decisions/ADR-*` | Nova decisão importante (nunca editar a decisão; criar nova que a substitui) | Sob demanda |
| `research/*` | Ao pesquisar algo relevante | Sob demanda |
| `history/*` | Ao arquivar conteúdo ou fechar sessão | Raramente |

## Hierarquia de verdade

Se dois documentos se contradizem: **ADR aceito mais recente > architecture > plan > research**.
Corrija o documento desatualizado na mesma sessão em que perceber o conflito.
