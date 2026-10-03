# ADR-036 — Triagem em massa no admin e métricas M1–M9 calculadas do banco

- **Status:** aceito
- **Data:** 2026-10-03

## Contexto
A E14 precisa que o humano triar rápido (meta: 20 itens em < 5 min) e que se meça se o sistema entrega valor
(`docs/product/metrics.md`). `Triage` já existia desde a E03 (ADR-017); faltava a interface e a leitura.

## Decisão
1. **Sem migration.** `Triage` guarda uma linha por entidade; «não triada» = sem linha **ou** situação `new`. Voltar para `new`
   limpa autor e data.
2. **Serviço único** `core/services/triage.py::triage_entities`: grava situação, motivo, nota, autor e data; descartar exige
   motivo (já garantido também por constraint no banco); o motivo é limpo ao sair de «descartada».
3. **Admin de oportunidades**: ações em massa (interessante, em andamento, concluído, descartar, voltar para não triado), coluna
   «triagem» e filtro «Não triadas», por subconsulta (sem consulta extra por linha). **Descartar abre uma tela intermediária**
   pedindo o motivo (e nota opcional) uma vez para todos os selecionados. Organizações ficam para a E21 (leads).
4. **`reports/metrics.py` + `make metrics`**: M1–M9 só leitura, sem IA/rede. Escolhas: M1 conta decisões «interessante, em andamento
   ou concluída» (não descartadas) na janela de 28 dias; **M2 usa o ranking atual do `Score`** (top 10 não bloqueadas) porque o
   digest ainda não existe (E15), sobre os já triados; M5 soma só `LLMCall` com cobrança `money` (a busca web não registra custo);
   M3 e M6 não são calculáveis (baseline da E01; autodeclarado) e aparecem como «sem dados»; M7 ignora execuções simuladas e conta
   `error` e `partial`; M9 = organizações com `next_action_at` vencida há mais de 7 dias.
5. Métrica sem dado mostra «sem dados», nunca zero inventado (ADR-004). A saída só tem contagens (logs públicos, ADR-014).

## Consequências
- Se a triagem passar de 30 min/semana, avaliar a view HTMX dedicada prevista no plano (registrar em novo ADR).
- Quando o digest (E15) existir, M2 deve passar a usar o top-10 **entregue** em vez do ranking atual.
