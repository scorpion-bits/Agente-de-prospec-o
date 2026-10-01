# ADR-034 — Extração de oportunidades: citação obrigatória, conferência por regras, campo crítico só verificado

- **Status:** aceito
- **Data:** 2026-10-01

## Contexto
Os conectores (E05–E09) criam `Opportunity` «candidatas» só com título e URL. A E11 precisa transformar a página em
campos úteis ao scoring (E13): prazo, requisitos de empresa (MEI, natureza jurídica, idade do CNPJ, CNAE, cota ME/EPP),
prêmio, benefícios e resumo. Um prazo ou requisito errado com ar de certeza é pior que um campo vazio (ADR-004).

## Decisão
1. **Candidata** = `Opportunity` com `official_url` e `extraction_version` vazia (sem migration). Depois de extraída,
   `extraction_version = extract_opportunity@v1`; página sem texto (PDF, só JS) fica `sem-texto` e só volta com `--force`.
2. **Uma tarefa** `extract_opportunity` na camada `llm/` (ADR-033): `gemini-free:gemini-3.1-flash-lite` → `anthropic:claude-haiku-4-5`
   → `rules`. Os dois primeiros só recebem **texto público** (`DataClass.PUBLIC`); Haiku só roda com chave e preço. As `rules`
   (regex) fecham a lista: sem modelo disponível, ainda saem prazo único, MEI, ME/EPP, idade do CNPJ, CNAE e prêmio.
3. **Schema** `OpportunityFields`: cada campo é `{value | "unknown", quote}`. O prompt está em arquivo versionado
   (`extraction/prompts/extract_opportunity_v1.txt`); mudar o prompt = mudar `PROMPT_VERSION` (invalida o cache).
4. **Conferência por regras depois do modelo.** Para campos críticos (datas, MEI/natureza jurídica, `requires_legal_entity`,
   cota ME/EPP, idade mínima, CNAE, valor), além da citação existir no texto (`quote_in_text`, ≥ 8 caracteres), o **valor**
   precisa bater com o que a regex acha (data escrita na página, mesmo número de anos, CNAE presente, valor em R$ presente).
5. **Campo crítico só vai para a coluna se confiável.** Não confiável: fica só como `Evidence(kind=inferred)`, visível no admin.
   Campos não críticos (resumo, esforço, benefícios…) entram na coluna, com evidência `observed` ou `inferred` conforme a citação.
6. **Nunca sobrescreve** coluna já preenchida (conector ou humano). «Não aceita MEI» sem lista de naturezas vira «todas menos MEI».
7. **Redução de tokens:** texto visível do HTML + janelas ao redor de palavras-chave (≤ 12 mil caracteres); documento idêntico
   não chama o modelo duas vezes (cache da E10). Teto de custo é o da E10.
8. **PDF fica de fora desta etapa:** o fetcher só baixa texto. Página PDF vira `sem-texto` (revisão humana). Entrada nativa de
   PDF no Gemini já existe na `llm/`; falta só baixar o binário com o fetcher educado (próxima iteração, junto do P22).

## Consequências
+ Zero custo no free tier; resultado sempre auditável (citação + método em cada evidência); funciona sem modelo, só com regras.
− Conferência estrita deixa campos `unknown`/inferidos em editais bem escritos de outro jeito (preferimos errar para o lado de não saber).
− Acurácia **não medida**: a amostra de 20 revisada por humano é o P22 (`docs/research/extraction-eval.md`).
