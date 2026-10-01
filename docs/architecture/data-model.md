# Modelo de dados

> Modelo **alvo**. Cada etapa cria só o que precisa. Nomes de código em inglês.
> Status: núcleo implementado na E03 (ver "Estado de implementação"); o resto entra nas etapas indicadas.

## Visão geral

```text
Source ──< CollectionRun ──< RawDocument
   │                              │
   └──────────────┬───────────────┘
                  ▼
        Evidence (observed | inferred | manual) ── aponta para qualquer entidade + campo
                  │
   ┌──────────────┼───────────────────────────┐
   ▼              ▼                           ▼
Organization ──< ContactPoint           Opportunity
   │  (parent/network: SESC-SP → unidades)    │
   ├──< Interaction (memória comercial)       │
   ├──< Match >── ServiceOffering ──< PortfolioItem (prova de capacidade)
   │      └── portfolio_refs ─────────────────┘
   └── Municipality (IBGE) ◄── Opportunity.location
CompanyProfile (única linha: MEI, abertura, CNAEs, sede) → usada na elegibilidade
Score (genérico: entity_type, entity_id, profile, total, breakdown JSON, version)
Triage (status humano: new/interesting/discarded/acting + motivo + nota)
LLMCall (log de custo/cache)   SearchQuery (cache de busca)   Suppression (opt-out)
```

Banco: PostgreSQL (Supabase) — ADR-010. Limite do Free: 500 MB → nada de binários no banco.

## Estado de implementação

| Etapa | Entidades |
|---|---|
| **E03 (feita)** | `Source`, `Organization`, `ContactPoint`, `Opportunity`, `Evidence`, `ServiceOffering`, `Match`, `Triage`, `Suppression` |
| **E03b (feita)** | `Interaction`, `PortfolioItem`, `CompanyProfile`, `Match.portfolio_refs`; `relationship_status`, `last_interaction_at`, `next_action_at` derivados (ADR-020); visão `FollowUp` (proxy de `Organization`) |
| **E04 (feita)** | `CollectionRun`, `RawDocument`, `Evidence.raw_document` (app `collection`) |
| E10 · E12 · E13 · E18 | `LLMCall` · `Municipality` · `Score` · `SearchQuery` |

**Desvios do modelo alvo feitos na E03/E03b** (as seções abaixo continuam descrevendo o alvo):
- E03b: `Interaction.occurred_at`/`next_action_at` e os derivados da organização são **datas** (`DateField`); `occurred_at` pode ser nulo com `data_status=pending` (sem data inventada). `Interaction.data_status` e `PortfolioItem.status` registram o que ainda falta confirmar. `CompanyProfile` é linha única (`pk=1`, constraint) e guarda `cnpj`/`legal_name`/`contact_email` só no banco (vêm do `.env`). `PortfolioItem.slug` é a chave estável da importação. `Interaction.created_by` é preenchido pelo admin.
- E04: `RawDocument` é único por URL (re-coleta atualiza a linha; o histórico fica nas `Evidence`) e guarda só texto comprimido; a retenção apaga o texto, não a linha. `CollectionRun` tem `dry_run` e `error_log` sem conteúdo dos itens.
- Município provisório: `municipality_name` + `uf` em `Organization` e `Opportunity` (a FK vem na E12).
- `ServiceOffering.typical_ticket_brl` (faixa) virou `typical_ticket_min_brl` e `typical_ticket_max_brl`,
  nulos: valores comerciais ficam no banco, não no repositório público (ADR-014).
- `Evidence`/`Triage` apontam para a entidade por `GenericForeignKey` (ADR-017), validando que o ID existe.
- Listas de strings são `ArrayField` (ADR-018). CNAE é sempre comparado **só pelos dígitos**.
- Identificadores externos únicos (`cnpj`, `inep_code`, `osm_id`) ficam **NULL** quando ausentes. O
  `cnpj` é guardado sem máscara, aceita o formato alfanumérico (vigente desde jul/2026) e tem os
  dígitos verificadores validados.
- `Opportunity.canonical_key`: gerada quando em branco (URL canônica; senão organizador + título + prazo,
  conforme `connectors.md`) e **somente leitura** no admin depois de criada.
- `ContactPoint`: `(organization, kind, value)` único, com o valor normalizado (e-mail em minúsculas,
  telefone em E.164). `evidence` obrigatória (`RESTRICT`) e **sobre a mesma organização**.
  `ContactPoint.objects.usable()` é a **única** porta para exibir ou usar contatos: exclui opt-out,
  organizações `do_not_contact` e contatos inativos.
- `Suppression`: valor normalizado por tipo; domínio vale para subdomínios; `organization` vale por CNPJ ou nome.
- `Match`: um por `(organization, service, method)`. `Triage`: uma por entidade; descartar exige motivo.
- `Source` nasce desabilitada e sem `robots_ok`: só liga depois de conferir termos e robots.txt.
- Catálogo de serviços: `core/fixtures/services.json`. `make seed` (`load_services`) só cria o que falta e
  **não sobrescreve** edições do admin (ex.: cobertura do MEI ajustada pelo contador); `loaddata` sobrescreve.

## Entidades

### `Source`
Registro de uma fonte/conector.
- `slug` (único, ex. `devpost`, `itch_jams`, `querido_diario`, `inep_schools`)
- `name`, `kind` (`api` | `html_watch` | `dataset` | `seed_csv` | `search`)
- `base_url`, `terms_url`, `robots_ok` (bool), `license` (ex. ODbL, CC-BY)
- `reliability` (1–5, julgamento humano documentado em research)
- `enabled`, `schedule` (texto: `daily`, `weekly`), `config` (JSON)

### `CollectionRun`
Uma execução de um conector: `source`, `started_at`, `finished_at`, `status`
(`ok`/`partial`/`error`), `items_seen`, `items_new`, `items_updated`, `error_log`.

### `RawDocument`
Conteúdo bruto baixado (cache e prova).
- `url`, `canonical_url`, `fetched_at`, `http_status`, `etag`, `content_hash` (sha256)
- `content_type`, `text_gz` (texto extraído comprimido, ou referência no Supabase Storage),
  `size_bytes`, `retain_until`
- `source`, `run`
Binários (PDFs) **não** são guardados: só URL + hash + texto extraído (os workers rodam em
máquinas efêmeras do GitHub Actions; o ETag no banco permite requisições condicionais).
Regra: nunca baixar de novo se `etag`/`last-modified` indicarem igual; nunca reprocessar
com LLM se `content_hash` já foi processado com a mesma versão de prompt.

### `Municipality`
Tabela IBGE (≈5.570 linhas): `ibge_code`, `name`, `uf`, `lat`, `lon`,
`immediate_region`, `intermediate_region`. Carregada uma vez (fixture).

### `Organization`
Escola, SESC, empresa, instituição, órgão público, organizador de evento.
- `name`, `legal_name`, `kind` (`school`, `sesc`, `company`, `university`,
  `public_body`, `ngo`, `event_organizer`, `other`)
- Identificadores externos opcionais e únicos: `cnpj`, `inep_code`, `osm_id`
- `segment` (texto livre curto), `cnae_main`, `size_hint` (`micro`/`small`/`medium`/`large`/`unknown`)
- `municipality` (FK), `address`, `lat`, `lon`
- `website`, `website_status` (`unknown`/`found`/`not_found`/`ambiguous`)
- `network` (ex. `SESC-SP`, `SENAC-SP`, `Centro Paula Souza`) e `parent` (FK para a
  organização-mãe), para tratar redes com várias unidades
- `similarity_tags` (ex. `sistema_s`, `cultural_publico`, `educacao_nao_formal`) — usado para
  achar "organizações parecidas com o SESC"
- `relationship_status` (derivado de `Interaction`, recalculado ao salvar): `never_contacted`,
  `contacted`, `in_conversation`, `proposal_sent`, `client`, `lost`, `do_not_contact`
- `last_interaction_at`, `next_action_at` (derivados)
- `created_at`, `updated_at`, `first_seen_source`
- Dedupe: `cnpj` > `inep_code` > domínio do site > (nome normalizado + município).
  Toda descoberta consulta primeiro a base existente: organização conhecida **nunca** vira
  "nova"; o digest mostra o histórico ("proposta enviada em DD/MM").

### `ContactPoint`
- `organization`, `kind` (`email`, `phone`, `whatsapp`, `contact_form`, `website`,
  `instagram`, `facebook`, `linkedin_company`, `youtube`, `other`)
- `value`, `label` (ex. "Secretaria"), `is_personal` (bool — e-mail/telefone de pessoa
  identificada), `role_hint` (ex. "coordenação pedagógica", nunca inventado)
- `evidence` (FK obrigatória), `last_verified_at`, `status` (`active`/`bounced`/`invalid`)
- Regra: sem `evidence` não entra. Contatos em `Suppression` nunca aparecem.

### `Opportunity`
Edital, hackathon, game jam, evento, programa, concurso, chamada, licitação.
- `kind` (`edital`, `hackathon`, `game_jam`, `event`, `program`, `contest`,
  `procurement`, `call_for_partners`, `other`)
- `title`, `organizer` (FK Organization opcional), `organizer_name`
- `description` (resumo curto), `categories` (lista: `culture`, `innovation`,
  `education`, `games`, `technology`, `entrepreneurship`)
- `modality` (`online`/`in_person`/`hybrid`/`unknown`), `municipality`, `scope`
  (`municipal`/`regional`/`state`/`national`/`international`)
- Datas: `opens_at`, `deadline_at`, `starts_at`, `ends_at`
- `eligibility_text`, `requires_legal_entity` (`yes`/`no`/`unknown`),
  `eligible_legal_forms` (ex. `["MEI","ME","EPP"]`, vazio = sem restrição conhecida),
  `exclusive_small_business` (bool/unknown — cota exclusiva ME/EPP/MEI),
  `min_company_age_months`, `required_cnaes` (prefixos),
  `eligible_regions` (lista de UF/municípios, vazio = sem restrição conhecida)
  (comparados com `CompanyProfile` no scoring — ADR-013)
- `requirements_text`, `prize_text`, `prize_amount_brl` (quando numérico),
  `benefits` (lista: `money`, `contract`, `prize`, `visibility`, `networking`,
  `mentoring`, `infrastructure`, `acceleration`, `partnership`, `clients`,
  `portfolio`, `certification`, `investors`)
- `participation_cost_text`, `effort_estimate` (`low`/`medium`/`high`/`unknown`)
- `official_url`, `canonical_key` (dedupe), `status` (`open`/`upcoming`/`closed`/`unknown`)
- `extraction_version`, `first_seen_at`, `last_seen_at`

### `Evidence` (coração da rastreabilidade — ADR-004)
Uma afirmação sobre um campo de uma entidade.
- `entity_type` + `entity_id` (genérico) e `field` (ex. `deadline_at`, `offers_high_school`)
- `value` (JSON), `kind`: **`observed`** (lido na fonte) | **`inferred`** (deduzido por
  regra ou IA) | **`manual`** (informado por humano)
- `source_url`, `source_name`, `retrieved_at`, `excerpt` (trecho literal ≤ 500 chars)
- `raw_document` (FK opcional), `method` (`connector:devpost`, `regex:email`,
  `rule:cnae_map`, `llm:gemini-2.5-flash-lite@prompt_v3`, `human`)
- `confidence` (0–1), `verified` (bool: para LLM, a citação foi encontrada no texto?)
- Regra de UI: inferências aparecem visualmente distintas ("🔮 inferido") de fatos.

### `ServiceOffering` (catálogo como dado)
- `slug`, `name`, `category` (`games`, `education`, `software`, `web`, `other`)
- `description`, `keywords` (lista), `target_org_kinds`, `target_cnaes` (prefixos),
- `geo_profile` (ver `geo-relevance.md`), `typical_ticket_brl` (faixa), `active`
- `mei_coverage` (`covered`/`verify`/`not_covered`) e `required_cnae_prefixes` — se o enquadramento
  atual cobre vender este serviço (ADR-015); editável no admin
Novos serviços = novas linhas, sem código.

### `PortfolioItem` (prova de capacidade — ADR-012)
- `slug`, `title` (ex. AstroDash, Tirania, Game Lab SESC), `kind` (`game`, `prototype`,
  `course`, `event`, `website`, `software`), `description`, `year`
- `public_url` (ex. página no itch.io — preenchida pelo humano, nunca inventada),
  `media_urls`, `public` (bool — só itens públicos aparecem em abordagens)
- `services` (M2M `ServiceOffering`), `capability_tags` (ex. `godot`, `2d`, `mobile`,
  `educacao`, `ensino_presencial`), `outcomes` (texto: nº de alunos, downloads… com fonte)
- Novos trabalhos = novas linhas; alimentam matching e, na Fase 4, rascunhos.

### `Match`
Hipótese "organização X provavelmente compraria serviço Y".
- `organization`, `service`, `reasons` (lista de `{text, evidence_id, kind}`),
  `strength` (0–1), `method` (`rules_v1`, `llm_v1`), `created_at`
- `portfolio_refs` (M2M `PortfolioItem`): trabalhos que demonstram a capacidade
  (cadeia **Lead → Necessidade → Serviço → Portfólio**)
- Uma organização pode ter vários matches.

### `Interaction` (memória comercial — ADR-012)
- `organization`, `occurred_at`, `channel` (`email`, `phone`, `whatsapp`, `in_person`,
  `form`, `other`), `kind` (`proposal_sent`, `meeting`, `message`, `call`, `visit`,
  `course_delivered`, `event_participation`, `response_received`, `other`)
- `service` (FK opcional), `contact_point` (FK opcional), `contact_name_role` (texto; dado
  pessoal — só o necessário), `summary`, `outcome` (`pending`, `positive`, `negative`,
  `no_response`, `won`, `lost`), `next_action`, `next_action_at`, `attachments_url` (link
  para proposta em drive próprio), `created_by`
- Responde: "Já falamos com eles? Quando? Sobre o quê? Resultado? Próximo passo?"
- Importação inicial a partir de CSV privado (fora do git) na E03b.

### `CompanyProfile` (linha única — ADR-013)
- `legal_form` (`MEI`), `opened_at`, `cnaes` (lista de {código, descrição, principal/secundário}), `hq_municipality`,
  `annual_revenue_cap_brl` (MEI 2026: 81.000), `website` (`scorpionbits.com`),
  `contact_email` (para User-Agent/digest)
- Seed não sensível versionado: `data/seeds/company_profile.json`. CNPJ, razão social do titular e
  endereço: só no banco/`.env`, nunca no git (repositório público — ADR-014).

### `Score`
- `entity_type`, `entity_id`, `profile` (ex. `opportunity.edital`, `lead.school_course`)
- `total` (0–100), `gated` (bool) + `gate_reason`
- `breakdown` (JSON: lista de `{factor, raw, weight, points, explanation, evidence_ids}`)
- `scoring_version`, `computed_at`

### `Triage`
- `entity_type`, `entity_id`, `status` (`new`/`interesting`/`discarded`/`acting`/`done`)
- `discard_reason` (`not_relevant`, `too_far`, `ineligible`, `too_much_effort`,
  `low_value`, `duplicate`, `bad_data`, `other`), `note`, `decided_by`, `decided_at`
- É a fonte das métricas M1–M4 e M8.

### `LLMCall`
`provider`, `model`, `purpose`, `prompt_version`, `input_hash`, `input_tokens`,
`output_tokens`, `cost_usd`, `cached` (bool), `latency_ms`, `ok`, `error`, `created_at`.

### `SearchQuery`
`provider`, `query`, `params`, `results` (JSON), `cost_usd`, `created_at`.
Mesma query + params nunca é refeita dentro do TTL (padrão: 90 dias).

### `Suppression` (opt-out)
`kind` (`email`/`phone`/`domain`/`organization`), `value`, `reason`, `created_at`.
Consultada antes de exibir qualquer contato e antes de qualquer abordagem.

### Fase 4
`Deal` (organização + serviço + estágio + valor estimado + próxima ação), agrupando
`Interaction`s já existentes. Detalhar na E23.
