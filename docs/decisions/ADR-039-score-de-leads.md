# ADR-039 — Score de leads (E21)

**Status:** aceito · **Data:** 2026-10-03 · Estende ADR-006 e ADR-035; usa ADR-012.

## Contexto
A E13 pontua oportunidades. A prospecção ativa precisa priorizar **organizações** (SESC, parecidas e escolas) com o mesmo critério
explicável, sem redescobrir quem já foi contatado (propostas a SESC Bauru, Ribeirão Preto e São Carlos).

## Decisão
1. **Mesmo motor, outros fatores.** `scoring/leads.py` reaproveita `combine` (soma ponderada e confiança K) e grava no mesmo `Score`
   (entidade = `Organization`). Perfis `lead.sesc` (SESC, parecidas e rede SESC) e `lead.school_course` (escolas) com os pesos do
   `scoring.md`, em `scoring/profiles.py`. Outros tipos de organização não são pontuados como lead (`lead.company_service` fica para depois).
2. **Fatores** (`scoring/factors/lead.py`), a partir do **match mais forte** da organização: V = ticket do serviço no catálogo (faixas
   do fator V das oportunidades); F = força do match (já reduzida sem prova de portfólio pela E20); C = base 0,5 ± relacionamento,
   rede SESC com cliente, parecida com o SESC (+0,05), resposta positiva (+0,1) ou sem resposta (−0,05), cobertura MEI do serviço;
   T = sazonalidade escolar (out–dez alto; SESC sem sazonalidade até a E01b) ou follow-up vencido/próximo (vale o maior); A = geo
   do perfil do serviço × contatabilidade (só contatos `usable()`); L neutro (o catálogo não tem esforço).
3. **Gates de memória comercial.** Opt-out (`Suppression` ou `do_not_contact`) → `gated` (novo `GateKind.DO_NOT_CONTACT`). Quem já foi
   contatado (status contatada, em conversa, proposta, cliente) ou teve interação há menos de 21 dias sem ação vencida recebe nota,
   mas o rótulo é **«em andamento»** (novo `Label.ONGOING`): nunca entra em «Leads da semana». Duplicata não é gate de lead
   (a organização já é deduplicada na E03b).
4. **Suporte da confiança.** Dado digitado por pessoas (catálogo, interações) conta como suporte 1; o match é hipótese (0,5, ou 1
   se alguma razão cita evidência); sazonalidade conta 0,5. Leads tendem a ter K menor que oportunidades: é esperado.
5. **Uso.** `make rescore` pontua oportunidades e leads (`--target leads`, `--profile lead.sesc`). Admin de organizações ordena por nota
   e mostra o breakdown. O digest ganha «Leads da semana» (top-10, contato sugerido só `usable()`, serviço e portfólio) e «Em andamento».

## Consequências
- Migration `scoring.0002` (só `choices` de `label` e `gate_kind`, sem alterar dados).
- Pesos, faixas e sazonalidade são **hipótese**: calibrar na E30 com a triagem humana (P27).
- A nota de lead depende de `make match` (E20), `make contacts` (E19) e das interações (`make memory`); sem match, F = 0 e o alerta diz isso.
- O digest com contato sugerido segue só local (ADR-037); nada disso vai para logs públicos (ADR-014).
