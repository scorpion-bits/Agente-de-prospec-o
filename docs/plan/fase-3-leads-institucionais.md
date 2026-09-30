# Fase 3 — Leads institucionais (MVP-C)

Foco: **escolas privadas da região** e **unidades SESC-SP** — maior chance de receita no
curto prazo (cursos/oficinas, case Game Lab). Ver ADR-009.

## E17 — Importação de escolas privadas (INEP) + lista semente SESC-SP

**Objetivo:** base de organizações-alvo com dados oficiais.
**Resultado esperado:** `Organization(kind=school)` para escolas **privadas ativas** nos
anéis R0–R2 (padrão: até 120 km de Araraquara), com código INEP, endereço, telefone,
etapas de ensino (infantil/fundamental I/II/médio/técnico) como `Evidence(observed)`;
`Organization(kind=sesc)` para as unidades SESC-SP a partir de `data/seeds/sesc_sp.csv`.
**Ler antes:** `organization-sources.md` (INEP, SESC — resultado E01), `connectors.md` (dataset, seed_csv).
**Alterações:** `collection/connectors/inep_schools.py` (dataset: download/arquivo local →
filtro por municípios da região e dependência privada); `data/seeds/sesc_sp.csv` (curado:
nome, município, URL da unidade, contato institucional publicado); `Source`s; testes com amostra.
**Dependências:** E04, E12 (municípios/distância para o filtro por raio).
**Modelo (desenvolvimento):** Claude Sonnet 5.5. **IA em runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** média.
**Riscos:** arquivo INEP grande/mudança de layout anual → mapear colunas por nome com
validação; telefone desatualizado → `last_verified_at` e confiança média; lista SESC manual
desatualiza → data de curadoria no CSV.
**Testes:** filtro (só privadas, só ativas, só região); idempotência por `inep_code`; seed carrega.
**Critério de conclusão:**
- [ ] Contagem de escolas por município registrada em STATUS e conferida por amostragem (5 escolas).
- [ ] Unidades SESC-SP carregadas com evidência (URL da unidade).

---

## E18 — Descoberta de site oficial

**Objetivo:** encontrar o site oficial de organizações sem `website`.
**Resultado esperado:** `manage.py find_websites --kind school --limit N` preenche
`website` + `website_status` (`found`/`not_found`/`ambiguous`) com evidência.
**Ler antes:** `ai-models-and-costs.md` (APIs de busca), `llm-strategy.md` (tarefa "encontrar site").
**Alterações:** `collection/search/{base,brave,serper}.py` (`SearchProvider` + cache em
`SearchQuery` + orçamento); `extraction/website.py` (validação determinística: domínio não é
agregador/rede social/diretório; título/página contém tokens do nome e o município; `.br`
favorece; lista de domínios bloqueados: guias, listas de escolas, redes sociais).
**Dependências:** E17, E04.
**Modelo (desenvolvimento):** Claude Sonnet 5.5.
**IA em runtime:** nenhuma no padrão; opcional desempate `ambiguous` via Flash-Lite
(desligado por padrão; só ativar se > 20% ambíguos).
**Custo:** dentro das cotas grátis (≈ 1 busca por organização, uma única vez).
**Complexidade:** média.
**Riscos:** escolhe site errado (rede de franquia, página de diretório) → validação +
`ambiguous` para revisão humana; cota estourada → teto de buscas por execução.
**Testes:** casos com resultados gravados (site certo, diretório, rede social, homônimo em outra cidade).
**Critério de conclusão:**
- [ ] Amostra de 20: ≥ 85% corretos entre `found`; erros viram `ambiguous`, não `found`.
- [ ] Nenhuma query repetida (cache verificado).

---

## E19 — Extração de contatos públicos institucionais

**Objetivo:** encontrar formas públicas de contato no próprio site da organização.
**Resultado esperado:** `manage.py extract_contacts` cria `ContactPoint`s (e-mail, telefone,
WhatsApp publicado, formulário, redes sociais da organização, LinkedIn da empresa se
linkado no site), cada um com evidência (URL + trecho).
**Ler antes:** `docs/agents/README.md` (ficha 3), `legal-and-compliance.md`.
**Alterações:** `extraction/contacts.py` (regex/`mailto:`/`tel:`/`wa.me`/`api.whatsapp.com`,
schema.org `ContactPoint`, links sociais; descoberta de páginas de contato por âncoras
"contato", "fale conosco", "atendimento"; máx. 5 páginas/site); classificação
institucional × pessoal; normalização de telefone (E.164 BR); consulta a `Suppression`.
**Dependências:** E18.
**Modelo (desenvolvimento):** Claude Sonnet 5.5. **IA em runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** média.
**Riscos:** e-mails ofuscados → aceitar perda (não "desofuscar" agressivamente);
e-mails de terceiros (desenvolvedor do site) → ignorar domínios diferentes da org salvo
provedores genéricos (gmail etc.) exibidos como contato oficial.
**Testes:** fixtures HTML variadas; nunca cria contato sem evidência; suppression respeitada.
**Critério de conclusão:**
- [ ] Amostra de 20 organizações: contatos extraídos conferem com o site.
- [ ] % de organizações com ≥ 1 contato institucional registrada em STATUS.

---

## E20 — Matching serviço ↔ organização por regras

**Objetivo:** gerar hipóteses "organização X → serviço Y, porque…".
**Resultado esperado:** `manage.py match_services` cria `Match` com razões ligadas a
evidências. Exemplos de regras v1:
- escola privada com fundamental II ou médio → `extracurricular_school`, `course_gamedev`, `game_jam_org`;
- escola com ensino técnico/informática → `course_gamedev`, `workshop_gamedev`;
- SESC → `course_gamedev`, `workshop_gamedev`, `game_jam_org` (+ razão "case Game Lab");
- organização sem site (`website_status=not_found`) → `institutional_site` (fraco).
**Ler antes:** `docs/agents/README.md` (ficha 4), `data-model.md` (ServiceOffering, Match).
**Alterações:** `scoring/matching.py` (regras como dados: condição → serviço → força → texto
da razão); testes.
**Dependências:** E17 (E19 opcional).
**Modelo (desenvolvimento):** Claude Sonnet 5.5.
**IA em runtime:** nenhuma no padrão; opcional justificativa em 2 frases para o top-20 (Flash-Lite), desligada por padrão.
**Custo:** US$ 0 (≤ US$ 1/mês se a opção LLM for ligada). **Complexidade:** média.
**Riscos:** regras genéricas demais (tudo casa com tudo) → força diferenciada e limite de 3 matches por org.
**Testes:** cada regra com caso positivo/negativo; razões apontam para evidências existentes.
**Critério de conclusão:**
- [ ] Toda escola/SESC tem ≥ 1 match com razão legível e evidência.
- [ ] Adicionar um serviço novo no admin + regra em dados não exige mudar código do motor.

---

## E21 — Score de leads + digest integrado

**Objetivo:** priorizar leads com os perfis `lead.school_course` e `lead.sesc` e integrá-los ao digest.
**Ler antes:** `scoring.md`, `geo-relevance.md`.
**Alterações:** fatores para leads (Valor via ticket do serviço; Fit via força do match;
Chance: relacionamento prévio/SESC, porte; Timing: sazonalidade escolar out–dez; Acesso:
geo × contatabilidade); perfis; seção "Leads da semana" no digest (top-10 com contato
sugerido e razão).
**Dependências:** E13, E15, E20 (E19 para contatabilidade).
**Modelo (desenvolvimento):** Claude Sonnet 5.5. **IA em runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** baixa.
**Riscos:** leads sem contato dominarem o topo → contatabilidade pesa no Acesso.
**Testes:** fatores de lead; sazonalidade; digest com as duas seções.
**Critério de conclusão:**
- [ ] Digest mostra oportunidades e leads, cada um com "por quê" e próximo passo.

---

## E22 — Avaliação do MVP (checkpoint go/no-go)

**Objetivo:** decidir com dados se o sistema vale o investimento contínuo.
**Pré-condição:** ≥ 4 semanas de uso real com triagem semanal (a etapa pode ser iniciada
antes só para preparar o relatório).
**Resultado esperado:** `docs/history/mvp-evaluation.md` com M1–M8, comparação com o
baseline manual (E01), custos, tempo de triagem, casos de sucesso/fracasso, e decisão:
**continuar (Fase 4 — quais etapas)**, **ajustar (o quê)** ou **parar**. ADR registrando a decisão.
**Ler antes:** `docs/product/mvp.md` (critérios), `metrics.md`, `baseline-manual.md`.
**Alterações:** relatório; ADR-0XX; STATUS; possivelmente reordenar Fase 4.
**Dependências:** E14–E21 em uso.
**Modelo (desenvolvimento):** Claude Opus 5.5 (análise e recomendação).
**IA em runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** baixa.
**Riscos:** pouco uso = dados insuficientes → estender o período em vez de decidir no escuro.
**Critério de conclusão:**
- [ ] Relatório com números, não impressões.
- [ ] Decisão registrada em ADR e próxima etapa definida em STATUS.
