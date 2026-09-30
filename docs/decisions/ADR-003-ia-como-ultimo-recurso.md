# ADR-003 — IA como último recurso: pipeline determinístico + camada LLM multi-provedor

- **Status:** aceito
- **Data:** 2026-09-30

## Contexto
A proposta inicial previa 8 agentes (Discovery, Research, Qualification, Contact
Discovery, Opportunity Analysis, Matching, Prioritization, Outreach). Orçamento ~zero;
free tiers mudam com frequência (Gemini Pro saiu do free tier em abr/2026; Brave encerrou
o plano grátis em fev/2026).

## Decisão
1. Construir um **pipeline determinístico**; LLM só onde há texto livre sem estrutura
   (extração de editais) e, na Fase 4, redação (rascunho de abordagem).
2. Nenhum agente autônomo no MVP. Um único agente sob demanda pode existir na Fase 4
   (E28) se a avaliação do MVP mostrar lacuna.
3. Toda chamada LLM passa pela camada `llm/` com: roteamento por tarefa, múltiplos
   provedores (Gemini free, Groq free, OpenRouter free, Ollama local, Claude Haiku/Sonnet),
   cache por hash, validação de schema, verificação de citação, log de custo e teto mensal.
4. Claude Opus não é usado em produção; Claude Code (assinatura) é usado para desenvolver.

## Alternativas consideradas
| Alternativa | Por que não |
|---|---|
| Multi-agentes (LangGraph/CrewAI) desde o início | Custo imprevisível, difícil de testar e auditar; frameworks pesados para o problema |
| Um único provedor (só Claude ou só Gemini) | Dependência de preço/cota de um fornecedor |
| Claude web search/fetch para pesquisar tudo | Custo por busca + tokens de páginas inteiras; cache difícil |

## Consequências
+ Custo previsível (US$ 0–5/mês no MVP). + Testável com fixtures e FakeProvider.
− Menos "mágico": regras precisam ser escritas e mantidas.
− Extração por modelos gratuitos pode ter qualidade menor → mitigado por validação + fallback.

## Quando revisitar
Se a avaliação do MVP (E22) mostrar que regras perdem muitos leads/oportunidades
relevantes que um LLM teria capturado (medir com amostra).
