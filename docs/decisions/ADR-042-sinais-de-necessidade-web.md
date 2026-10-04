# ADR-042 — Sinais de necessidade web: só a página inicial, ausência é inferida, nada de IA

- **Status:** aceito
- **Data:** 2026-10-04
- **Etapa:** E26

## Contexto
A E22 (ADR-040) espera uso real; a Fase 4 só segue com «continuar». A E26 é determinística, depende só da E18 (site oficial) e
não precisa de dados reais para ser construída. O ambiente do Claude não alcança sites reais: nada foi testado fora de fixtures.
A ideia (sinais de HTML sem LLM) vem da análise do `agente-prospeccao` (MIT, só a ideia; nenhum código foi copiado).

## Decisão
1. **`extraction/web_signals.py` (puro)** analisa a página inicial já baixada: `no_https` (URL **final**, depois de redirecionamentos),
   `no_viewport`, `old_copyright` (maior ano ≥ 4 anos atrás; anos futuros ou < 1990 ignorados) e `obsolete_tech` (Flash, jQuery 1.x/2.x,
   `frameset`). `no_site` e `social_only` vêm de `Organization.website` (vazio + «não encontrado» na E18; ou só rede/agregador de links),
   sem baixar nada. `site_down` vem de falha de rede/HTTP.
2. **Só a página inicial**, pelo `PoliteFetcher` (robots, rate limit, cache): 1 requisição por organização. Robots/403/conteúdo não
   textual → nenhuma conclusão (`skipped`); opt-out (`Suppression`) → o site nem é visitado.
3. **Nada inventado (ADR-004):** o que a página mostra (© antigo, Flash, jQuery, HTTP) é `observed` com URL e trecho literal verificado;
   **ausência** (`no_viewport`, `no_site`) e `site_down` são `inferred` (confiança 0,5–0,7). Página com < 200 caracteres de texto
   (montada por JavaScript) não gera `no_viewport`: fica `unknown`, nunca «sem».
4. **Evidência por sinal** (`web.signal.<código>`) via `record_evidence`; a marca `web.signals_checked` (evidência inferida) dá o
   **frescor de 30 dias** sem migration: `make signals` só relê quem não tem marca fresca (`--refresh` ignora).
5. **Sinal é fator de Fit, não verdade** (site simples pode ser adequado). **Ainda não entra no score**: decidir depois do P30, com
   sites reais, qual peso dar e a quais serviços (`web`) ligar.
6. **Fora do `make pipeline`** por enquanto: lê sites de terceiros, então roda sob demanda até o P30 conferir falsos positivos.

## Consequências
+ Custo zero, sem IA, sem migration; 20 testes (fixtures sintéticas, sem rede), saída só com contagens (logs públicos).
− Regex de © e de jQuery são heurísticas de HTML real não visto; site só em JavaScript quase não gera sinal (de propósito).
− Fora de escopo: versões de CMS/EOL (endoflife.date), CVE, acessibilidade e velocidade.
