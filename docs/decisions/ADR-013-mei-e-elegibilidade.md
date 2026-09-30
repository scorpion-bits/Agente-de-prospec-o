# ADR-013 — Empresa formalizada como MEI: elegibilidade pelo perfil da empresa

- **Status:** aceito (ajusta ADR-006 e a premissa "empresa não formalizada"; complementado por ADR-015: cobertura de atividades/CNAE)
- **Data:** 2026-09-30

## Contexto
A Scorpion Bits **tem CNPJ de MEI**. O plano anterior tratava "exige CNPJ" como alerta
principal. Com MEI, a pergunta muda para "o **nosso** CNPJ atende aos requisitos?". Exemplos:
- MEI pode participar de licitações (Lei 14.133/21); contratações até R$ 80 mil podem ser
  exclusivas para ME/EPP/MEI (vantagem).
- Limite de faturamento do MEI: R$ 81 mil/ano (2026) — um contrato grande exigiria migrar
  para ME (não impede participar).
- Editais podem exigir tempo mínimo de CNPJ/sede (ex.: ProAC 05/2026 de jogos eletrônicos:
  PJ com sede em SP há mais de 2 anos), CNAE compatível, ou natureza jurídica específica.

## Decisão
1. Criar `CompanyProfile` (configuração única): natureza jurídica (MEI), data de abertura,
   CNAEs, município/UF da sede, limite de faturamento vigente. CNPJ e dados do titular ficam
   no banco/`.env`, **não** no git.
2. Extração de oportunidades captura requisitos: `requires_legal_entity`,
   `eligible_legal_forms`, `min_company_age_months`, `required_cnaes`, `exclusive_small_business`.
3. Scoring: **gate** quando o requisito é explícito e não atendido (ex.: "não aceita MEI",
   idade mínima não atingida na data do prazo); **alerta + redução de Chance** quando
   ambíguo ou contornável (CNAE a incluir no MEI, valor acima do limite anual → "exigiria migrar
   para ME"); **bônus de Chance** para cotas exclusivas ME/EPP/MEI.
4. O digest mostra "oportunidades bloqueadas por requisito da empresa" (ex.: idade do CNPJ),
   para decisões de negócio (ex.: quando migrar para ME, que CNAE incluir).
5. PNCP (licitações) sobe de prioridade dentro da Fase 4 (E27 é a primeira candidata).

## Consequências
+ Elegibilidade real em vez de "exige CNPJ" genérico. + Inteligência de negócio sobre formalização.
− Mais campos na extração (mais tokens por documento; aceitável).

## Quando revisitar
Mudança de natureza jurídica (MEI → ME) ou do limite do MEI.
