# ADR-011 — Seleção de modelos por tarefa, com Gemini como provedor principal de extração

- **Status:** aceito (complementa ADR-003)
- **Data:** 2026-09-30

## Contexto
A Scorpion Bits tem acesso ao **Gemini Pro** (assinatura Google AI Pro) e ao Claude Code.
Assinaturas de produto **não** equivalem a API: a assinatura dá uso nos apps (Gemini,
Deep Research, NotebookLM) e, desde 2026, **US$ 10/mês em créditos de Google Cloud**
(benefício de desenvolvedor, precisa ser ativado) utilizáveis na API Gemini. O free tier da
API Gemini cobre Flash/Flash-Lite (Pro saiu do free tier em abr/2026). Grounding com Google
Search nos modelos 3.x: ~5.000 requisições grátis/mês, depois ~US$ 14/1.000.

## Decisão
1. **Escolha por tarefa**, sempre começando por "sem IA" (ver tabela em
   `docs/architecture/llm-strategy.md`).
2. **Gemini é o provedor principal para extração** (editais, páginas, PDFs, inclusive
   escaneados via entrada nativa de PDF): Flash-Lite (free tier) → Flash no projeto com
   faturamento (pago pelos créditos do AI Pro).
3. **Dados não públicos** (contatos, interações, rascunhos com nomes) só vão para provedores
   em **plano pago** (projeto Gemini com faturamento/créditos ou Claude API), nunca para free tiers
   que podem usar dados para treino.
4. **Texto que o cliente vai ler** (rascunho de abordagem, E24): teste A/B entre Claude
   Sonnet 5.5 e Gemini 3.1 Pro; empate → Gemini (créditos já pagos pela assinatura).
5. **Pesquisa profunda manual** (humano no comando) usa o que já é pago: Gemini Deep
   Research / NotebookLM (assinatura) e Claude Code. Automação de produção nunca depende de
   assinatura de app.
6. **Claude Haiku 4.5** permanece como fallback pago barato; Claude Opus só no desenvolvimento.
7. Toda troca de provedor é configuração da camada `llm/` (ADR-003); cada tarefa de IA tem
   também uma estratégia **sem LLM** (regras) selecionável.

## Alternativas consideradas
| Alternativa | Por que não |
|---|---|
| Claude para tudo | Custo maior sem ganho em extração simples; ignora créditos/free tier já disponíveis |
| Gemini para tudo | Dependência de um fornecedor que mudou cotas várias vezes em 2026 |
| Usar a assinatura (app) para automação | Não é API; termos não permitem; frágil |

## Consequências
+ Custo de IA do MVP ≈ US$ 0 em dinheiro novo. + Leitura de PDF escaneado sem OCR próprio.
− Mais de um SDK para manter (isolados em adapters). − Créditos precisam ser ativados e monitorados.

## Quando revisitar
Mudança de preço/cota de Gemini ou Claude; A/B da E24; avaliação E22.
