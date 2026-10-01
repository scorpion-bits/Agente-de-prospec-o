# Fase 3 — Leads institucionais

Foco: **rede SESC-SP** (hipótese validada — Game Lab realizado, propostas a Bauru, Ribeirão
Preto e São Carlos), **organizações parecidas com o SESC** e **escolas privadas** dos polos e
interior próximo. Executada **antes** da Fase 1 na ordem recomendada (`PLAN.md`). ADR-009, ADR-012.

## E17 — Rede SESC-SP + escolas privadas (INEP)

**Objetivo:** base de organizações-alvo com dados oficiais, integrada à memória comercial.
**Resultado esperado:**
- `Organization(kind=sesc, network="SESC-SP", parent=SESC-SP)` para **todas** as unidades do
  estado (lista semente `data/seeds/sesc_sp.csv`: nome, município, URL oficial da unidade,
  contato institucional publicado, data de curadoria). Unidades já contatadas (E03b) são
  reconhecidas, não duplicadas.
- `Organization(kind=school)` para escolas **privadas ativas** dos polos e municípios até
  ~150 km (escopo de coleta configurável), com código INEP, endereço, telefone e etapas de
  ensino como `Evidence(observed)`.
**Ler antes:** `organization-sources.md` (resultado E01), `connectors.md` (dataset, seed_csv), ADR-012.
**Alterações:** `data/seeds/sesc_sp.csv`; `collection/connectors/inep_schools.py`; `Source`s; testes com amostra.
**Dependências:** E04, E12, E03b.
**Modelo (desenvolvimento):** Claude Sonnet 5.5. **IA em runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** média.
**Riscos:** layout do INEP muda por ano → mapear colunas por nome; telefones desatualizados →
confiança média; lista SESC desatualiza → data de curadoria.
**Testes:** filtro (privadas, ativas, escopo); idempotência por `inep_code`; unidades SESC já
existentes (E03b) não duplicam.
**Critério de conclusão:**
- [x] Todas as unidades SESC-SP no admin, com status de relacionamento correto nas já contatadas
  (lista curada de memória: **conferir contra sescsp.org.br**, P11).
- [ ] Contagem de escolas por município registrada em STATUS; 5 conferidas por amostragem
  (`make collect` com o CSV do INEP baixado + `count_organizations school`; depende de rede, P11).

---

## E17b — Organizações parecidas com o SESC

**Objetivo:** encontrar instituições com o mesmo perfil de compra do SESC (educação não
formal/cultural, contratam oficineiros, unidades na região).
**Resultado esperado:** `data/seeds/similar_orgs.csv` (curado: SENAC-SP, SESI/SENAI-SP,
Oficinas Culturais, Fábricas de Cultura, ETECs/FATECs e IFSP dos polos, secretarias de
cultura/educação, bibliotecas, centros de ciência) com `similarity_tags`; páginas de
chamamento/credenciamento dessas redes adicionadas como `html_watch` (reusa E07 quando existir;
senão, só a seed).
**Ler antes:** `organization-sources.md` (seção "parecidas com o SESC"), `business-analysis.md`.
**Alterações:** seed CSV; `Source`s; regras de tags.
**Dependências:** E17.
**Modelo (desenvolvimento):** Claude Sonnet 5.5. **IA em runtime:** nenhuma (curadoria humana
apoiada por pesquisa manual — Gemini Deep Research/Claude Code interativo, custo marginal zero).
**Custo:** US$ 0. **Complexidade:** baixa.
**Riscos:** lista crescer sem foco → começar pelos polos; organizações sem contratação externa → tag de baixa prioridade.
**Critério de conclusão:**
- [x] ≥ 20 organizações similares nos polos, cada uma com URL oficial (própria ou da rede-mãe) e evidência
  manual (lista de memória: **conferir na fonte**, P12).
- [x] Tags permitem filtrar "parecidas com o SESC" no admin (filtro e vocabulário fechado, ADR-024).

---

## E18 — Descoberta de site oficial

**Objetivo:** encontrar o site oficial de organizações sem `website`.
**Resultado esperado:** `manage.py find_websites --kind school --limit N` preenche
`website` + `website_status` (`found`/`not_found`/`ambiguous`) com evidência.
**Ler antes:** `ai-models-and-costs.md` (APIs de busca, grounding), `llm-strategy.md` (tarefa "achar site").
**Alterações:** `collection/search/{base,brave,serper}.py` (`SearchProvider` + cache em
`SearchQuery` + orçamento); `extraction/website.py` (validação determinística: não é
agregador/rede social/diretório; página contém tokens do nome e o município; lista de
domínios bloqueados).
**Experimento opcional (desligado por padrão):** provedor de busca via Gemini com Search
grounding (5 mil/mês grátis nos modelos 3.x) — ativar só após ler os termos sobre
armazenamento de resultados; comparar acurácia com a API de busca em 20 casos.
**Dependências:** E17, E04 (E10 só para o experimento).
**Modelo (desenvolvimento):** Claude Sonnet 5.5.
**IA em runtime:** nenhuma no padrão.
**Custo:** dentro das cotas grátis (≈ 1 busca por organização, uma vez).
**Complexidade:** média.
**Riscos:** site errado (franquia, diretório) → validação + `ambiguous`; cota estourada → teto por execução.
**Testes:** resultados gravados (site certo, diretório, rede social, homônimo em outra cidade).
**Critério de conclusão:**
- [ ] Amostra de 20: ≥ 85% corretos entre `found`; erros viram `ambiguous`, não `found`.
- [ ] Nenhuma query repetida.

---

## E19 — Extração de contatos públicos institucionais

**Objetivo:** encontrar formas públicas de contato no próprio site da organização.
**Resultado esperado:** `manage.py extract_contacts` cria `ContactPoint`s (e-mail, telefone,
WhatsApp publicado, formulário, redes da organização, LinkedIn da empresa se linkado no site),
cada um com evidência (URL + trecho).
**Ler antes:** `docs/agents/README.md` (ficha 3), `legal-and-compliance.md`.
**Alterações:** `extraction/contacts.py` (regex/`mailto:`/`tel:`/`wa.me`, schema.org, links
sociais; páginas "contato"/"fale conosco"; máx. 5 páginas/site); institucional × pessoal;
telefone E.164; `Suppression`.
**Dependências:** E18.
**Modelo (desenvolvimento):** Claude Sonnet 5.5. **IA em runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** média.
**Riscos:** e-mails ofuscados → aceitar perda; e-mails de terceiros → ignorar domínios alheios.
**Testes:** fixtures HTML variadas; nunca cria contato sem evidência; suppression respeitada.
**Critério de conclusão:**
- [ ] Amostra de 20: contatos conferem com o site.
- [ ] % de organizações com ≥ 1 contato institucional registrada em STATUS.

---

## E20 — Matching serviço ↔ organização ↔ portfólio

**Objetivo:** gerar hipóteses "organização X → serviço Y, porque…, **prova: trabalho Z**".
**Resultado esperado:** `manage.py match_services` cria `Match` com razões ligadas a evidências
e `portfolio_refs`. Regras v1 (como dados):
- SESC / parecidas com o SESC → `course_gamedev`, `workshop_gamedev`, `game_jam_org`; prova: Game Lab SESC;
- escola privada com fundamental II ou médio → `extracurricular_school`, `course_gamedev`; prova: Game Lab SESC;
- escola técnica/informática → `course_gamedev`, `workshop_gamedev`;
- organização que menciona gamificação/jogos educativos → `educational_game`, `gamification`; prova: AstroDash/Tirania;
- sem site (`website_status=not_found`) → `institutional_site` (fraco; prova: quando houver item web no portfólio).
**Ler antes:** `docs/agents/README.md` (ficha 4), `data-model.md` (ServiceOffering, PortfolioItem, Match).
**Alterações:** `scoring/matching.py` (regras: condição → serviço → força → razão → itens de portfólio); testes.
**Dependências:** E17, E03b (E19 opcional).
**Modelo (desenvolvimento):** Claude Sonnet 5.5.
**IA em runtime:** nenhuma no padrão; opcional justificativa em 2 frases para o top-20 (Gemini Flash-Lite), desligada por padrão.
**Custo:** US$ 0 (≈ US$ 0 com free tier se ligada). **Complexidade:** média.
**Riscos:** regras genéricas demais → força diferenciada e máximo de 3 matches por organização.
**Testes:** cada regra com caso positivo/negativo; razões e portfólio apontam para registros existentes.
**Critério de conclusão:**
- [ ] Toda unidade SESC/escola tem ≥ 1 match com razão legível, evidência e (quando existir) item de portfólio.
- [ ] Novo serviço ou item de portfólio no admin + regra em dados não exige mudar o motor.

---

## E21 — Score de leads

**Objetivo:** priorizar leads com os perfis `lead.sesc` (inclui parecidas) e `lead.school_course`.
As seções de leads do digest são montadas na E15 (executada depois desta).
**Ler antes:** `scoring.md` (fatores, memória comercial), `geo-relevance.md`.
**Alterações:** fatores de lead — Valor (ticket do serviço), Fit (força do match + prova de
portfólio), Chance (rede SESC com case ↑, relacionamento, resposta anterior), Timing
(sazonalidade escolar; follow-up vencendo), Acesso (geo com polos × contatabilidade); gates de
memória (recontato < 21 dias, `do_not_contact`); admin ordena leads por score com breakdown.
**Dependências:** E13, E20 (E19 para contatabilidade).
**Modelo (desenvolvimento):** Claude Sonnet 5.5. **IA em runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** baixa.
**Riscos:** leads sem contato dominarem → contatabilidade no Acesso; unidades com proposta em
aberto reaparecerem como "novas" → gate de memória testado.
**Testes:** fatores; gates de memória; sazonalidade.
**Critério de conclusão:**
- [ ] SESC Bauru/Ribeirão Preto/São Carlos classificados "em andamento", nunca como novos leads.
- [ ] Breakdown de 5 leads compreensível sem ler código.

---

## E22 — Avaliação do MVP (checkpoint go/no-go)

**Objetivo:** decidir com dados se o sistema vale o investimento contínuo.
**Pré-condição:** ≥ 4 semanas de uso real com triagem semanal.
**Resultado esperado:** `docs/history/mvp-evaluation.md` com M1–M9, comparação com o
baseline manual (E01), custos (dinheiro novo e créditos), tempo de triagem, casos de
sucesso/fracasso e decisão: **continuar (quais etapas da Fase 4)**, **ajustar** ou **parar**. ADR.
**Ler antes:** `docs/product/mvp.md`, `metrics.md`, `baseline-manual.md`.
**Dependências:** E14–E21 em uso.
**Modelo (desenvolvimento):** Claude Opus 5.5. **IA em runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** baixa.
**Riscos:** pouco uso → estender o período em vez de decidir no escuro.
**Critério de conclusão:**
- [ ] Relatório com números, não impressões.
- [ ] Decisão em ADR e próxima etapa definida em STATUS.
