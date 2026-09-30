# Modelo de dados

> Modelo **alvo**. Cada etapa cria só o que precisa. Nomes de código em inglês.
> Status: proposto (nenhuma migration criada ainda).

## Visão geral

```text
Source ──< CollectionRun ──< RawDocument
   │                              │
   └──────────────┬───────────────┘
                  ▼
        Evidence (observed | inferred)  ── aponta para qualquer entidade + campo
                  │
   ┌──────────────┼───────────────────────────┐
   ▼              ▼                           ▼
Organization ──< ContactPoint           Opportunity
   │                                          │
   ├──< Match >── ServiceOffering ──< ─ ─ ─ ─ ┘ (opportunity também pode casar com serviço)
   │
   └── Municipality (IBGE) ◄── Opportunity.location
Score (genérico: entity_type, entity_id, profile, total, breakdown JSON, version)
Triage (status humano: new/interesting/discarded/acting + motivo + nota)
LLMCall (log de custo/cache)   SearchQuery (cache de busca)   Suppression (opt-out)
```

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
- `content_type`, `storage_path` (arquivo em `data/raw/<hash[:2]>/<hash>`), `text_path`
- `source`, `run`
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
- `created_at`, `updated_at`, `first_seen_source`
- Dedupe: `cnpj` > `inep_code` > domínio do site > (nome normalizado + município)

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
  `eligible_regions` (lista de UF/municípios, vazio = sem restrição conhecida)
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
Novos serviços = novas linhas, sem código.

### `Match`
Hipótese "organização X provavelmente compraria serviço Y".
- `organization`, `service`, `reasons` (lista de `{text, evidence_id, kind}`),
  `strength` (0–1), `method` (`rules_v1`, `llm_v1`), `created_at`
- Uma organização pode ter vários matches.

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
`PipelineStage` / `Deal` (organização + serviço + estágio + valor estimado + próxima ação),
`Interaction` (data, canal, resumo, resultado). Detalhar na E23.
