# Modelos de IA, APIs de busca e custos

> Levantamento: **30/09/2026**. Preços/cotas mudam com frequência (o Gemini mudou o free
> tier várias vezes em 2026; o Brave eliminou o plano grátis em fev/2026).
> **Revalidar antes de ativar qualquer provedor pago** e atualizar este arquivo.

## LLMs

### Anthropic (Claude) — preços por 1M tokens (API primária)

| Modelo | ID | Entrada | Saída | Observação |
|---|---|---|---|---|
| Claude Haiku 4.5 | `claude-haiku-4-5` | US$ 1,00 | US$ 5,00 | Degrau "barato pago" para extração |
| Claude Sonnet 5.5 | `claude-sonnet-5-5` | US$ 2,00 | US$ 10,00 | Texto de qualidade, agente sob demanda |
| Claude Opus 5.5 | `claude-opus-5-5` | US$ 4,00 | US$ 20,00 | Só desenvolvimento (Claude Code) |

Descontos: **Batch API −50%** (assíncrono, até 24h — adequado ao radar);
**prompt caching** (leitura de cache ≈ 10% do preço de entrada; exige prefixo mínimo — o
system prompt de extração pode não atingir o mínimo; medir). Ferramenta de web search
server-side da Anthropic é cobrada à parte por busca (≈ US$10/1.000 — conferir) — **não
usar** no pipeline; buscar via API de busca própria com cache.

### Google Gemini (free tier)

- Desde 01/04/2026, modelos Pro saíram do free tier; **Flash e Flash-Lite continuam grátis**.
- Gemini 2.5 Flash-Lite: ~15 RPM, ~1.000 req/dia, 250k TPM (fontes variam).
- Gemini 3.1 Flash-Lite: ~500 req/dia (set/2026).
- ⚠ No free tier, o Google pode usar entradas para melhorar produtos → **só documentos públicos**.

### Groq (free tier)
- ~30 RPM, ~6k TPM, até ~14.400 req/dia (varia por modelo; modelos maiores ~1.000/dia).
- Cartão (sem gasto mínimo) aumenta limites. Bom como segundo provedor gratuito.

### OpenRouter (modelos `:free`)
- Sem pagamento: ~50 req/dia, 20 RPM. Com compra única de US$10 em créditos: ~1.000 req/dia.
- Útil como terceiro fallback; qualidade/disponibilidade dos modelos free varia.

### Local (Ollama)
- Modelos 7–14B (famílias Qwen, Gemma, Llama) rodam em CPU com 16 GB RAM (lento) ou GPU
  8–12 GB (aceitável). Qualidade de extração estruturada: razoável com schema + validação.
- Custo: zero em dinheiro; custo em tempo/energia. **Pergunta aberta**: hardware disponível.

## APIs de busca web

| Provedor | Gratuito | Pago | Observação |
|---|---|---|---|
| Brave Search API | US$5 de crédito/mês (~1.000 buscas) desde fev/2026 | ~US$5/1.000 | Índice próprio; bom para achar sites |
| Serper.dev (Google SERP) | 2.500 buscas (uma vez) | US$50/50k (≈US$1/1k) → US$0,30/1k em escala | Mais barato para volume |
| Tavily | 1.000/mês | US$8/1.000 (PAYG) | Otimizado p/ agentes; caro para nosso uso |
| Google Custom Search JSON API | — | — | **Fechado a novos clientes; encerra em 01/01/2027** |
| SearXNG auto-hospedado | Grátis | — | Motores bloqueiam uso contínuo; instável |

Decisão: interface `SearchProvider` com Brave e Serper; cache permanente por query
(tabela `SearchQuery`). Buscas são raras (1 por organização sem site).

## Estimativas de custo mensal

Premissas MVP: 50–150 documentos de oportunidade novos/semana; ~6k tokens de entrada e
~0,8k de saída por documento após pré-filtro; ~300 escolas + ~40 SESCs na base; busca de
site uma vez por organização.

| Cenário | Infra | LLM | Busca | Total/mês |
|---|---|---|---|---|
| **MVP** (roda em máquina própria; Gemini/Groq free; Haiku só fallback) | US$ 0 | US$ 0–3 | US$ 0 (cotas grátis) | **US$ 0–5** (teto configurado US$ 5–10) |
| MVP todo em Haiku (sem free tier) | US$ 0 | ~US$ 3–6 (≈ metade com Batch) | US$ 0 | ~US$ 3–6 |
| **Operação pequena** (VPS 2–4 GB; + rascunhos Sonnet; + CNPJ região) | US$ 5–10 (VPS) + domínio ~US$1 | US$ 5–15 | US$ 0–10 | **US$ 15–35** |
| **Operação maior** (Postgres gerenciado ou VPS maior, várias regiões/segmentos, agente de pesquisa sob demanda, mais buscas) | US$ 20–40 | US$ 30–100 (teto) | US$ 20–50 | **US$ 80–200** |

Cálculo de referência (Haiku 4.5): 600 docs × (6.000 × US$1/1M + 800 × US$5/1M)
= 600 × (US$0,006 + US$0,004) = **US$ 6,00/mês** (US$ 3,00 com Batch).
Rascunhos (Sonnet 5.5): 40 × (3.000 × US$2/1M + 500 × US$10/1M) = 40 × US$0,011 ≈ **US$ 0,44/mês**.

## Riscos de custo e mitigação

| Risco | Mitigação |
|---|---|
| Free tier muda/acaba (já aconteceu com Gemini Pro e Brave) | Roteamento multi-provedor; fallback pago barato com teto |
| PDF enorme estoura tokens | Pré-filtro por janelas de palavras-chave; limite duro por documento |
| Loop de agente | Sem agentes no MVP; Fase 4 com teto por execução |
| Reprocessamento repetido | Cache por hash de conteúdo + versão de prompt |
| Buscas repetidas | Cache permanente por query |

## Fontes

- Anthropic: pricing de modelos (skill `claude-api`, cache de 25/09/2026) — docs.anthropic.com/pricing
- Gemini free tier 2026: https://www.aifreeapi.com/en/posts/gemini-api-free-tier-rate-limits ; https://tokenmix.ai/blog/gemini-api-free-tier-limits ; https://www.cloudzero.com/blog/gemini-pricing/
- Groq: https://tokenmix.ai/blog/groq-free-tier-limits-2026 ; https://www.cloudzero.com/blog/groq-pricing/
- OpenRouter: https://openrouter.zendesk.com/hc/en-us/articles/39501163636379-OpenRouter-Rate-Limits-What-You-Need-to-Know ; https://costgoat.com/pricing/openrouter-free-models
- Brave Search API: https://costbench.com/software/ai-search-apis/brave-search-api/ ; https://agentdeals.dev/vendor/brave-search-api
- Serper/Tavily: https://www.scrapingdog.com/blog/serper-alternatives/ ; https://keirolabs.cloud/blogs/comparisons/ai-search-api-pricing-compared
- Google CSE fim: https://dev.to/booyaka101/google-kills-the-custom-search-json-api-on-2027-01-01-here-is-a-self-hosted-drop-in-3nk0
