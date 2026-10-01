# ADR-025 — Descoberta de site oficial: busca com cache + validação determinística

- **Status:** aceito
- **Data:** 2026-10-01
- **Etapa:** E18

## Contexto
Organizações vindas do INEP não têm site, e a E19 (contatos) precisa dele. A decisão de ferramentas já estava em
`docs/research/ai-models-and-costs.md` (API de busca com cache) e `llm-strategy.md` (sem IA nesta tarefa). O
ambiente do Claude não tem chave de busca nem acesso aos provedores: **nada foi testado contra API real**.

## Decisão
1. **`SearchProvider`** (`collection/search/`) com Serper e Brave, escolhidos por `SEARCH_PROVIDER`. Cache
   permanente em `SearchQuery` (chave = consulta normalizada: sem acento, caixa ou pontuação): consulta repetida
   nunca vai à rede. Falha do provedor não entra no cache. `SEARCH_MAX_CALLS_PER_RUN` (padrão 100) limita as
   buscas **pagas** por execução; estourar o teto interrompe com mensagem, e o resto fica para a próxima.
2. **Consulta** = `nome + município + UF`, uma por organização sem site e com município.
3. **Validação determinística** (`extraction/website.py`), sobre até 3 domínios candidatos por organização:
   - domínio em lista de bloqueio (redes sociais, diretórios, buscadores, CNPJ) → descartado sem baixar;
   - a página é baixada pelo `PoliteFetcher` (robots, rate limit); os tokens distintivos do nome (sem
     «escola», «municipal»…) devem aparecer no título/começo da página (todos se ≤ 2; ≥ 75% se mais) **e** o
     município deve aparecer na página → `match`;
   - só nome, só no resultado da busca, ou página que não baixou → `weak`.
4. **Decisão** (`decide`): `found` só com **exatamente um** domínio em `match` e nenhum outro plausível;
   qualquer dúvida (vários domínios, `weak`, domínio já usado por outra organização) → `ambiguous`; nada → `not_found`.
   **Erra para `ambiguous`, nunca para `found`.**
5. **Gravação:** `website` (raiz do site se o resultado era a página inicial) + `website_status`. A evidência é
   **inferida por regra** (`rule:website_match`), com URL da página e trecho literal verificado contra o texto
   (ADR-004). Ambíguos guardam cada candidato como evidência `website_candidate`, para o humano escolher no admin.
6. **Por padrão só organizações `unknown`**; `--retry` reavalia `not_found`/`ambiguous` (buscas em cache: grátis).
   `--dry-run` não grava site nem evidência. A saída traz só contagens (logs públicos, ADR-014).
7. **Grounding do Gemini** (experimento opcional do plano): **não feito**; depende de E10 e de ler os termos de
   armazenamento. Registrado como pendência.

## Consequências
+ Custo ≈ 1 busca por organização, uma vez; sem IA; reexecutável sem custo.
+ Site errado dificilmente vira `found`; o humano resolve os ambíguos.
− **Formatos de Serper/Brave seguem a documentação pública e não foram testados** (P13).
− Critério «≥ 85% corretos em 20» **não medido**; precisa de chave e de conferência manual.
− Site só em JavaScript (sem texto no HTML) cai em `ambiguous`/`not_found` (sem navegador headless no MVP).
− Domínio de rede/prefeitura que hospeda várias unidades pode virar `ambiguous` (um domínio por organização).
