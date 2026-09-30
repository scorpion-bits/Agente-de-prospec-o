# ADR-012 — Memória comercial (interações) e portfólio entram no MVP

- **Status:** aceito (antecipa parte da E23 original)
- **Data:** 2026-09-30

## Contexto
A Scorpion Bits já realizou o Game Lab com o SESC e **já enviou propostas** a unidades
(Bauru, Ribeirão Preto, São Carlos). Tem portfólio público (AstroDash, Tirania, protótipo,
jogos no itch.io). O plano anterior deixava interações para a Fase 4 e não modelava portfólio.
Sem memória, o sistema "redescobriria" organizações já prospectadas e poderia sugerir
contato duplicado — contrário ao princípio anti-spam.

## Decisão
1. `Interaction` (histórico por organização: data, canal, tipo — proposta enviada, reunião,
   curso realizado…, serviço, contato, resumo, resultado, próxima ação e data) entra no
   **núcleo do MVP (E03b)**, com importação das interações já existentes.
2. `Organization` ganha rede/unidade (`network`, `parent`) e **status de relacionamento
   derivado** das interações (nunca contatado, em conversa, cliente, perdido, não contatar).
3. `PortfolioItem` (jogos, cursos, sites, sistemas) ligado a `ServiceOffering`; o `Match`
   referencia itens de portfólio como **prova de capacidade**.
4. Descoberta consulta a memória: organização já conhecida nunca é "nova"; aparece como
   "já falamos em DD/MM — próxima ação: …".
5. Pipeline completo (estágios de negócio, valores, funil) continua na Fase 4 (E23).

## Consequências
+ Utilidade imediata (registrar e consultar propostas SESC) antes mesmo dos conectores.
+ Score pode usar relacionamento e portfólio (Chance/Fit) e gerar lembretes de follow-up.
− Mais 3 entidades no MVP (pequenas). − Interações contêm dados pessoais (nomes de contatos)
  → não versionar em git; ficam só no banco (LGPD, `legal-and-compliance.md`).

## Quando revisitar
Na E23 (pipeline) ou se o registro manual de interações não for mantido (sinal de UX ruim).
