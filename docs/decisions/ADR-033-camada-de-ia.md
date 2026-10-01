# ADR-033 — Camada de IA (`llm/`): tarefas × estratégias, HTTP sem SDK, classe do dado, teto

- **Status:** aceito
- **Data:** 2026-10-01

## Contexto
A E10 implementa o que ADR-003 e ADR-011 decidiram: nenhum módulo conhece fornecedor, só **tarefas**; custo
previsível (US$ 0–5/mês); documentos públicos podem ir a free tier, dados internos não (LGPD, ADR-014). Nenhuma chave
real existe neste ambiente, então nada foi chamado de verdade: formatos de requisição/resposta vêm da documentação
dos fornecedores e estão cobertos só por respostas simuladas (`httpx.MockTransport`).

## Decisão
1. **`AIService.run(tarefa, entrada, schema)`** percorre as estratégias da tarefa em ordem (`provedor:modelo` ou
   `rules`). Rate limit, erro, schema inválido (após 1 retry), teto estourado, falta de chave, ou dado não permitido
   passam à seguinte; se nenhuma serve, `NoStrategyAvailable` lista as razões, **sem conteúdo**. A lista de cada tarefa
   é trocável por configuração (`LLM_TASK_STRATEGIES`, JSON no `.env`).
2. **Sem SDK: HTTP direto com `httpx`** (já dependência) em `llm/providers/{gemini,anthropic,ollama}.py`. Contrato
   pequeno, testável sem rede, nenhuma dependência nova, e o isolamento «nenhum outro módulo importa SDK» vira um teste.
   Custo: se um fornecedor mudar o formato, o adapter quebra até ser ajustado (por isso a fumaça, P21).
3. **Classe do dado obrigatória** em `LLMInput` (`public` | `internal`). `gemini-free` só aceita `public`;
   `gemini-paid` e `anthropic` aceitam `internal`; Ollama aceita `internal` só se `OLLAMA_BASE_URL` for localhost.
4. **Ollama Cloud não adotado agora.** O adapter `ollama` só lê `OLLAMA_BASE_URL` (+ `OLLAMA_API_KEY` opcional):
   apontá-lo para um servidor remoto não exige código, mas o trata como terceiro → **só dados públicos**.
   Nenhum ADR anterior mudou; ADR-003/011 seguem valendo.
5. **Cache** por `sha256(estratégia + versão do prompt + instruções + entrada + PDF)` guardando só a **resposta**
   em `LLMCall.response_text`; hit gera linha `cached` com custo 0. Mudar `prompt_version` invalida.
6. **Orçamento:** `money` (Anthropic) vigia `LLM_MONTHLY_BUDGET_USD` (5); `credits` (Gemini pago, créditos do AI
   Pro) vigia `LLM_CREDITS_MONTHLY_USD` (10, valor aproximado a confirmar); `LLM_RUN_BUDGET_USD` (1) soma os dois por
   `AIService`. A checagem usa **estimativa pessimista** (caracteres/3 + saída máxima); free tier nunca é bloqueado.
   Modelo pago sem preço em `llm/pricing.py` **não é chamado**.
7. **Citações:** `llm.quotes.Quoted {value, quote, verified}` e `verify_quotes` (sem acento/caixa/espaços extras); o
   resultado traz `unverified` e quem grava a evidência (E11) rebaixa para `inferred` (ADR-004).
8. **Log (`LLMCall`)** guarda tarefa, estratégia, tokens, custo, duração e erro curto, nunca a entrada; `llm_usage`
   mostra o mês e `llm_smoke` faz a chamada real de fumaça. Tarefas reais (extração) chegam na E11; só `smoke_ping` existe.
9. PDF: só Gemini (entrada nativa); outros provedores são pulados quando só há PDF.

## Consequências
+ Custo previsível, tudo testado sem rede (32 testes), trocar de provedor é editar uma lista.
− Formatos HTTP não verificados contra os serviços reais até o P21; preços do Gemini pago são de referência (conferir).
− `response_text` fica no banco (dado possivelmente interno): fora do git e dos logs; política de retenção pode vir
  quando houver tarefas com dado interno.
