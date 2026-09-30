# Manutenção do CLAUDE.md e do STATUS.md

## Limites

| Arquivo | Alvo | Alerta | Limite rígido | Verificação |
|---|---|---|---|---|
| `CLAUDE.md` | ≤ 130 linhas | 120 linhas | **150 linhas (~2.000 tokens)** | `wc -l CLAUDE.md` |
| `docs/plan/STATUS.md` | ≤ 100 linhas | 100 linhas | **120 linhas** | `wc -l docs/plan/STATUS.md` |

(A partir da E02, `make docs-check` automatiza essa verificação.)

Racional do limite: ver ADR-008.

## O que pode ficar no CLAUDE.md

Só o que é necessário para **qualquer** sessão de trabalho atual:
- identidade do projeto (2–4 linhas) e links para visão/MVP;
- rituais de início e fim;
- princípios inegociáveis;
- stack e estrutura de diretórios **atuais**;
- convenções de código que valem hoje;
- índice "onde encontrar o quê".

## O que NÃO pode ficar

- Histórico ("na etapa E05 decidimos…") → `docs/history/`
- Detalhes de arquitetura/implementação → `docs/architecture/`
- Justificativas longas → ADR
- Resultados de pesquisa, preços, listas de fontes → `docs/research/`
- Estado do trabalho → `docs/plan/STATUS.md`
- Instruções de etapas específicas → arquivo de fase

## Procedimento quando passar do limite

1. **Analisar** cada seção: "uma sessão executando a próxima etapa precisa disto?"
2. **Classificar** o que sai:
   - *obsoleto* (não é mais verdade) → mover para `docs/history/claude-md-archive/AAAA-MM-DD.md`
     com nota "substituído por …";
   - *histórico/decisão* → ADR (se ainda não existir) ou `docs/history/`;
   - *detalhe ainda válido* → documento temático apropriado em `docs/`.
3. **Mover** o texto (copiar integralmente para o destino **antes** de remover).
4. **Deixar link** no CLAUDE.md quando o conteúdo ainda for útil sob demanda
   (ex.: "Convenções de conectores: `docs/architecture/connectors.md`").
5. **Registrar** no arquivo de arquivo: data, motivo, seções movidas e destino.
6. **Verificar** `wc -l` e commit `docs: manutenção do CLAUDE.md`.

**Nunca apagar informação histórica sem registrá-la em `docs/history/`.**

## Procedimento para o STATUS.md

Quando passar de 100 linhas: mover itens "Concluído" antigos (mantendo só as últimas
3 etapas) para `docs/history/status-archive.md`, preservando datas e links.
