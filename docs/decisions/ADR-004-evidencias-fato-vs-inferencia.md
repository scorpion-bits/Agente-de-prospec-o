# ADR-004 — Evidência obrigatória e separação fato observado × inferência

- **Status:** aceito
- **Data:** 2026-09-30

## Contexto
Prospecção com informação inventada destrói credibilidade (ex.: mencionar um curso que a
escola não oferece). LLMs alucinam. Precisamos responder "de onde veio isso?" para
qualquer dado.

## Decisão
- Toda afirmação relevante sobre uma entidade é uma linha em `Evidence` com: campo, valor,
  `kind` (`observed` | `inferred` | `manual`), URL da fonte, nome da fonte, data de coleta,
  trecho literal, método (`connector:x`, `regex:y`, `rule:z`, `llm:modelo@versão`,
  `human`), confiança e `verified`.
- Saídas de LLM só contam como `observed` se a citação for encontrada no texto-fonte.
- A UI mostra inferências de forma visualmente distinta.
- O score usa a proporção de evidências observadas no fator de confiança.
- Mensagens de abordagem (Fase 4) só podem afirmar fatos com evidência.

## Alternativas consideradas
| Alternativa | Por que não |
|---|---|
| Só guardar o valor final nos campos | Perde a origem; impossível auditar |
| Guardar fonte só no nível do registro | Um registro mistura fontes e inferências |

## Consequências
+ Auditável; protege reputação; permite recalcular quando fonte muda.
− Mais linhas no banco e um pouco mais de código em cada conector (aceitável).

## Quando revisitar
Nunca no princípio; apenas na forma de armazenamento se o volume crescer muito.
