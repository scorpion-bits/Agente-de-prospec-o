# Estratégia de IA (LLM)

> Regra de ouro: **se código, SQL, regex ou heurística resolvem, não use IA.**
> Preços e cotas mudam rápido: fonte e data em `docs/research/ai-models-and-costs.md`
> (levantamento de 30/09/2026). Revalidar antes de ativar provedor pago.

## Escada de modelos (usar o degrau mais baixo que funciona)

| Degrau | Opção | Custo | Uso |
|---|---|---|---|
| 0 | **Sem IA** (código/regex/regras) | 0 | Padrão para tudo |
| 1 | **Gratuito em nuvem**: Gemini Flash-Lite (free tier), Groq free, OpenRouter `:free` | 0 (cotas/dia; dados podem ser usados pelo provedor) | Extração de campos de documentos **públicos** |
| 2 | **Local**: Ollama + modelo 7–14B (ex. Qwen3, Gemma) | 0 (hardware/tempo) | Fallback offline; depende do hardware (pergunta aberta) |
| 3 | **Barato pago**: Claude Haiku 4.5 (US$1/US$5 por 1M tokens in/out; Batch −50%) | centavos | Quando o gratuito falha na validação ou estoura cota |
| 4 | **Forte**: Claude Sonnet 5.5 (US$2/US$10) | baixo volume | Texto que um humano vai ler/enviar (rascunho de abordagem), documentos longos de alto valor |
| 5 | **Topo**: Claude Opus 5.5 (US$4/US$20) | — | **Não usar em produção.** Só desenvolvimento/planejamento via Claude Code |

Claude Code (assinatura) é usado para **desenvolver** o sistema. Pesquisa manual
assistida em sessões interativas do Claude Code é aceitável (humano no comando);
automação de produção **não** deve depender da assinatura.

## Tarefa por tarefa

| Tarefa | IA? | Modelo recomendado | Alternativa gratuita | Alternativa local | Volume estimado | Custo/mês estimado | Risco de custo | Quando subir de modelo |
|---|---|---|---|---|---|---|---|---|
| Coleta via API/feed, normalização | **Não** | — | — | — | — | 0 | — | — |
| Detectar novidade em página monitorada | **Não** (diff de links/hash) | — | — | — | — | 0 | — | — |
| Classificar relevância (é sobre jogos/educação/tecnologia?) | Regras primeiro; LLM só para ambíguos | Gemini Flash-Lite | Groq | Ollama 7B | ~20–60 ambíguos/sem | 0 (free) / < US$0,50 (Haiku) | Baixo | Nunca (se regras + barato não bastam, revisar regras) |
| **Extrair campos de edital/chamada** (prazo, elegibilidade, exige CNPJ, prêmio, benefícios, esforço) | **Sim** (texto livre, PDFs) — datas/valores por regex primeiro | Gemini Flash-Lite (free) → fallback Claude Haiku 4.5 (Batch) | Groq / OpenRouter free | Ollama 8–14B | 50–150 docs/sem × ~6k tokens in / ~0,8k out | 0 (free) / ~US$3–6 (Haiku, ~US$1,5–3 com Batch) | Médio (PDFs longos) → truncar por seções relevantes + teto | Doc de alto valor (>R$100 mil) com validação falhando 2× → Sonnet 5.5 |
| Encontrar site da organização | **Não** (API de busca + validação por regras) | — (desempate por LLM opcional) | — | — | ~200–500 buscas no total (uma vez por org) | Dentro de cotas grátis (Brave US$5 crédito/mês; Serper 2.500 grátis) | Baixo (cache permanente) | — |
| Extrair contatos do site | **Não** (regex, `mailto:`, `tel:`, `wa.me`, schema.org, links sociais) | — | — | — | — | 0 | — | — |
| Matching organização ↔ serviço | **Não** no MVP (regras: tipo, CNAE, palavras-chave, etapas de ensino) | Opcional: 2 frases de justificativa para top-20/sem | Gemini Flash-Lite | Ollama | ≤ 20/sem × 2k in/0,3k out | ~0 / < US$1 | Baixo | — |
| Pontuação | **Não** (determinística — ver `scoring.md`) | — | — | — | — | 0 | — | — |
| Digest semanal | **Não** (template) | — | — | — | 1/sem | 0 | — | — |
| Rascunho de abordagem (Fase 4) | **Sim** (texto persuasivo, personalizado) | Claude Sonnet 5.5 | Gemini Flash | Ollama 14B (qualidade inferior) | 10–40/mês × 3k in/0,5k out | ~US$0,15–0,50 | Baixo | Já está no degrau 4; humano sempre revisa |
| Pesquisa profunda sob demanda (Fase 4, opcional) | **Sim** (agente com ferramentas) | Claude Sonnet 5.5 com teto por execução | Sessão manual no Claude Code | — | ≤ 10/mês | ~US$1–10 (teto) | **Alto** se sem teto → teto rígido por execução e por mês | Nunca Opus em produção |

## Camada `llm/` (implementada na E10)

```python
result = llm.complete_json(
    task="extract_opportunity_fields",      # chave de roteamento e de log
    prompt_version="v1",
    system=SYSTEM_PROMPT,                   # estável → cacheável
    user=document_text,                     # já pré-filtrado
    schema=OpportunityFields,               # JSON Schema / Pydantic
    max_output_tokens=1200,
)
```

Responsabilidades:
1. **Roteamento por tarefa** (config): lista ordenada de provedores, ex.
   `extract_opportunity_fields: [gemini_flash_lite_free, groq_free, anthropic_haiku]`;
   passa ao próximo em rate limit/erro/validação falha.
2. **Cache** por `sha256(provider_family + model + prompt_version + system + user)`:
   resultado reaproveitado para sempre (conteúdo igual ⇒ resposta igual).
3. **Validação de schema** (Pydantic). Falhou → 1 retry com mensagem de erro → próximo provedor.
4. **Verificação de evidência**: cada campo extraído traz `quote`; o sistema confere se a
   citação existe no texto-fonte (normalizando espaços/acentos). Sem citação válida ⇒
   campo marcado `verified=false` e não entra no score como `observed`.
5. **Log de custo** (`LLMCall`) com tokens e US$ calculados por tabela de preços em config.
6. **Orçamento**: teto mensal (padrão **US$ 5**) e teto por execução. Ao atingir → para de
   chamar provedores pagos, registra e avisa no digest. Provedores gratuitos continuam.
7. **Provedor falso** (`FakeProvider`) para testes — nenhum teste chama rede.
8. **Privacidade**: provedores gratuitos só recebem **documentos públicos**. Nunca enviar
   listas de contatos ou dados pessoais para provedores cujo free tier usa dados para treino.

## Redução de tokens (antes de chamar qualquer LLM)

- Extrair texto principal (trafilatura) e remover menus/rodapés.
- Para PDFs longos: selecionar janelas ao redor de palavras-chave (`inscrição`, `prazo`,
  `elegibilidade`, `proponente`, `valor`, `prêmio`, `CNPJ`, `MEI`, `pessoa física`, `cronograma`).
- Limite duro de entrada por documento (ex. 12k tokens); acima disso, só janelas.
- Nunca reprocessar documento com mesmo `content_hash` + `prompt_version`.
- Usar Batch API (−50%) para extração paga — nada no radar é urgente ao minuto.

## Tratamento de alucinação

- Schema estrito com `unknown` permitido em todo campo (o modelo não é forçado a inventar).
- Instrução explícita: "Se não estiver no texto, responda `unknown`."
- Verificação de citação (item 4 acima).
- Datas extraídas por LLM conferidas contra regex de datas do próprio texto.
- Inferências (ex. "esforço alto") sempre gravadas como `Evidence(kind=inferred)`.
- Amostragem humana: na E11, revisar 20 extrações e medir acurácia por campo; registrar.
