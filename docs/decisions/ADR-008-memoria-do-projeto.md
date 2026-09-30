# ADR-008 — Sistema de memória do projeto e limite do CLAUDE.md

- **Status:** aceito
- **Data:** 2026-09-30

## Contexto
O trabalho será feito em ciclos curtos com `/clear` entre etapas. Cada nova sessão do
Claude Code começa sem memória. O `CLAUDE.md` é carregado automaticamente em toda sessão
e compete com o trabalho por atenção e contexto.

## Decisão
1. **`CLAUDE.md` ≤ 150 linhas (~2.000 tokens)**; alerta a partir de 120 linhas.
   Contém apenas: o que é o projeto, rituais de início/fim, princípios, stack, estrutura,
   convenções e um índice de onde achar o resto.
2. **`docs/plan/STATUS.md`** é o estado vivo (≤ 120 linhas); atualizado ao fim de toda etapa.
3. Detalhes vivem em `docs/` (product, plan, architecture, agents, decisions, research,
   operations). Conteúdo obsoleto vai para `docs/history/` — **nunca é apagado**.
4. Processo de manutenção descrito em `docs/operations/claude-md-maintenance.md`.

## Por que 150 linhas / ~2.000 tokens
- Instruções curtas são seguidas com mais consistência; arquivos longos diluem regras
  importantes entre detalhes (a própria orientação da Anthropic é manter o CLAUDE.md
  conciso e específico).
- 150 linhas cabem numa leitura rápida humana (~2 telas) e custam ~1% de uma janela de
  200k tokens — margem segura mesmo em modelos menores.
- O limite força a pergunta "isso é necessário para o trabalho **atual**?".

## Alternativas consideradas
| Alternativa | Por que não |
|---|---|
| CLAUDE.md longo com tudo | Diluição de instruções; custo de contexto em toda sessão |
| Sem CLAUDE.md, só docs/ | Nova sessão não saberia por onde começar |
| Limite em tokens exatos | Difícil medir sem ferramenta; linhas são verificáveis com `wc -l` |

## Quando revisitar
Se sessões novas repetidamente não encontrarem informação essencial (aumentar índice),
ou se o limite forçar remover regras ainda ativas (dividir em `CLAUDE.md` de subdiretório).
