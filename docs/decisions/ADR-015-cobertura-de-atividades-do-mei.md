# ADR-015 — Cobertura de atividades do MEI (CNAE) como fator de elegibilidade

- **Status:** aceito (complementa ADR-013)
- **Data:** 2026-09-30
- **Etapa:** E01b

## Contexto
O CNPJ foi aberto em **10/04/2025** como MEI, com atividade principal de **ensino de arte e
cultura (85.92-9/99)** e secundárias que incluem **treinamento em informática (85.99-6/03)**
e fabricação de jogos recreativos (32.40-0/99, jogos físicos). **Não constam** desenvolvimento
de software sob encomenda (62.01-5), edição de jogos eletrônicos (58.21-2) nem
desenvolvimento web. Fontes secundárias (contabilidade) indicam que desenvolvimento de
software sob encomenda **não é permitido ao MEI** (exige ME/EPP). Isto não é parecer jurídico:
**confirmar com contador**.

Datas relevantes (hoje: 30/09/2026): CNPJ com ~17 meses; completa **2 anos em 10/04/2027**
(ex.: ProAC de jogos eletrônicos 05/2026 exige sede em SP há mais de 2 anos).

## Decisão
1. `CompanyProfile` guarda a lista de CNAEs ({código, descrição, principal/secundário}) —
   seed em `data/seeds/company_profile.json`.
2. `ServiceOffering.mei_coverage` ∈ {`covered`, `verify`, `not_covered`}, com valor inicial:
   - `covered`: `course_gamedev`, `workshop_gamedev`, `extracurricular_school`
     (ensino/treinamento em informática);
   - `verify`: `game_jam_org`, `gamification`, `educational_game`, `institutional_game`, `indie_game`;
   - `not_covered`: `custom_software`, `web_app`, `landing_page`, `institutional_site`.
   O contador ajusta esses valores (editáveis no admin, sem mudar código).
3. No scoring, `not_covered` **não é gate**: gera alerta "exigiria ME" e reduz Chance; `verify`
   gera alerta leve. O digest soma o valor potencial de oportunidades/leads que dependem de
   serviços `not_covered`/`verify` ("receita que exigiria ME") — insumo para decidir quando migrar.
4. A priorização natural do MVP (cursos e oficinas em SESC, organizações parecidas e escolas)
   coincide com o que o MEI cobre hoje; software/web/jogos sob encomenda ficam visíveis, mas com alerta.
5. A regra de idade do CNPJ usa `opened_at` e a data-limite da oportunidade (ADR-013).

## Consequências
+ Decisão de formalização orientada por dados. + Evita prometer serviço que o enquadramento não cobre.
− Classificação inicial é hipótese até a validação do contador.

## Quando revisitar
Mudança de enquadramento (MEI → ME), inclusão de CNAEs, parecer do contador.
