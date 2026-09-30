# Estratégia de IA (multimodelo)

> Regra de ouro: **"isso realmente precisa de inteligência generativa?"** Se código, SQL,
> regex ou heurística resolvem, não use IA. Preços/cotas: `docs/research/ai-models-and-costs.md`
> (levantamento de 30/09/2026 — revalidar antes de ativar provedor pago).
> Decisões: ADR-003 (IA como último recurso) e ADR-011 (seleção por tarefa, Gemini).

## Não precisam de IA (nunca)

Calcular/ordenar por distância · deduplicar · verificar se URL/documento já foi processado ·
armazenar leads · filtrar categorias · scores · detectar duplicatas · controlar status e
follow-ups · agendar coletas · regras determinísticas · extrair e-mails/telefones · achar
datas e valores em R$ (regex) · montar o digest.

## Camada de IA: tarefas com estratégias intercambiáveis

A aplicação **não conhece fornecedores**; conhece **tarefas**. Cada tarefa tem estratégias
configuráveis — inclusive uma sem LLM:

```text
                    AI SERVICE (llm/)
   tarefa: "extract_opportunity_fields" | "classify_relevance" | "draft_outreach" | ...
                          │  (config: lista ordenada de estratégias + teto de custo)
      ┌──────────┬────────┼──────────┬──────────────┐
      ▼          ▼        ▼          ▼              ▼
   rules      gemini   claude    local (Ollama)   fake (testes)
 (sem LLM)  (free/pago) (pago)   (grátis, lento)
```

```python
result = ai.run(
    task="extract_opportunity_fields",   # roteamento, cache, log e orçamento por tarefa
    input=DocumentInput(text=..., pdf_bytes=None, url=...),
    schema=OpportunityFields,            # Pydantic; cada campo {value|"unknown", quote}
)
# result.data, result.strategy ("rules"/"gemini:flash-lite"/...), result.cost_usd, result.cached
```

Trocar `Claude → Gemini`, `API → local` ou `LLM → regras` = mudar a configuração da tarefa.
Adapters de provedor ficam isolados em `llm/providers/`; nenhum outro módulo importa SDK.

Responsabilidades da camada (implementada na E10):
1. **Roteamento por tarefa**: estratégias em ordem; passa à seguinte em rate limit, erro ou validação falha.
2. **Cache** por `sha256(estratégia + modelo + prompt_version + entrada)` — conteúdo igual ⇒ nunca paga duas vezes.
3. **Validação de schema** (Pydantic) com 1 retry.
4. **Verificação de evidência**: cada campo traz `quote`; a citação precisa existir no texto-fonte;
   senão `verified=false` → vira inferência.
5. **Log de custo** (`LLMCall`) com tokens e US$ (tabela de preços em config).
6. **Orçamento**: teto mensal (padrão US$ 5 de dinheiro novo; créditos Gemini contabilizados
   à parte) e por execução. Atingiu → só estratégias gratuitas/regras.
7. **Classe de dados**: `public` (documentos públicos) pode ir a free tiers; `internal`
   (contatos, interações, rascunhos com nomes) **só** a provedores pagos (Gemini com
   faturamento/créditos, Claude API) ou local.
8. `FakeProvider` para testes (nenhum teste chama rede).

## Seleção de modelos por tarefa

Legenda: ✅ escolhido · ↪ fallback · ◯ viável, não escolhido · ✗ inadequado

| Tarefa | Sem IA | Gemini | Claude | Local | Escolha e motivo |
|---|---|---|---|---|---|
| Coleta, dedupe, status, distância, score, digest | ✅ | ✗ | ✗ | ✗ | Determinístico por definição |
| Detectar novidades em páginas | ✅ diff | ✗ | ✗ | ✗ | Hash/diff de links basta |
| **Classificar relevância** (é sobre jogos/educação/tecnologia?) | ✅ palavras-chave primeiro | ✅ Flash-Lite (free) só p/ ambíguos | ↪ Haiku 4.5 | ◯ | Classificação curta; free tier suficiente |
| **Extrair campos de edital** (prazo, elegibilidade/MEI, prêmio, benefícios, esforço, resumo 2–4 linhas) | Regex p/ datas/valores | ✅ Flash-Lite (free) → Flash (créditos AI Pro) | ↪ Haiku 4.5 (Batch) | ◯ 8–14B | Texto livre; Gemini: free tier, contexto longo, barato. O resumo sai na **mesma** chamada |
| **PDF escaneado** (sem texto) | ✗ | ✅ Flash com PDF nativo | ◯ Haiku/Sonnet (visão, mais caro) | ✗ | Elimina OCR próprio |
| **Identificar necessidade comercial** a partir do site de uma organização | ✅ regras (termos: robótica, maker, programação, extracurricular, tecnologia, curso livre) | ✅ Flash-Lite só p/ top-N sem sinal claro | ↪ Haiku | ◯ | Regras cobrem a maioria; LLM só onde há dúvida |
| **Justificativa do match** ("por que esta escola → curso de jogos") | ✅ template com evidências | ◯ Flash-Lite p/ top-20 (opcional) | ◯ | ◯ | Template já é explicável; LLM só se melhorar a leitura |
| **Achar site oficial** | ✅ API de busca + validação | ◯ Search grounding (5 mil/mês grátis nos 3.x) — experimento na E18, conferir termos sobre armazenamento | ✗ | ✗ | Busca simples com cache é mais barata e previsível |
| **Rascunho de abordagem** (Fase 4) | ✗ | ✅ 3.1 Pro (créditos AI Pro) — A/B | ✅ Sonnet 5.5 — A/B | ◯ (qualidade menor) | Texto lido por clientes: testar os dois com 10 casos; empate → Gemini (já pago) |
| **Pesquisa profunda sob demanda** (Fase 4) | ✗ | ✅ Flash/Pro + Search grounding (cota grátis) | ↪ Sonnet 5.5 + API de busca | ✗ | Busca embutida e cota grátis; teto rígido por execução |
| **Pesquisa manual pelo humano** | — | ✅ Gemini app: Deep Research, NotebookLM (assinatura) | ✅ Claude Code (assinatura) | — | Custo marginal zero; humano no comando; **não** automatizar via assinatura |
| Desenvolvimento do sistema | — | ◯ | ✅ Claude Code | — | Já disponível |

Quando subir de modelo: somente se a amostra revisada (E11, E24) mostrar que o degrau
inferior erra em campos que importam (prazo, elegibilidade) — nunca por "parecer melhor".

## Redução de tokens (antes de qualquer LLM)

- Texto principal (trafilatura) sem menus/rodapés.
- PDFs longos: janelas ao redor de `inscrição`, `prazo`, `elegibilidade`, `proponente`,
  `MEI`, `pessoa jurídica`, `CNAE`, `valor`, `prêmio`, `cronograma`, `sede`.
- Limite duro por documento (ex. 12k tokens de texto); PDF nativo só quando não há texto.
- Nunca reprocessar documento com mesmo `content_hash` + `prompt_version`.
- Processamento em lote/assíncrono quando pago (Claude Batch −50%).

## Tratamento de alucinação

- Schema com `unknown` permitido em todo campo; instrução "se não está no texto, `unknown`".
- Citação verificada (item 4); datas conferidas por regex.
- Inferências sempre `Evidence(kind=inferred, method=llm:<modelo>@<versão>)`.
- Amostra humana de 20 extrações por versão de prompt (E11), acurácia por campo registrada.
