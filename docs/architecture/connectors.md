# Conectores e coleta

## Objetivo

Adicionar uma nova fonte deve exigir **uma classe nova + uma linha de configuração**,
sem mexer no resto do sistema.

## Tipos de conector

| Tipo | Exemplo | Como funciona |
|---|---|---|
| `api` | Devpost, Querido Diário, Mapas Culturais, PNCP | Chama endpoint JSON público, pagina, normaliza |
| `feed` | itch.io (páginas de listagem com `.xml`) | Lê RSS/Atom |
| `html_watch` | FAPESP/PIPE, Sebrae-SP, InovAtiva, ProAC, prefeituras | Baixa página de listagem, extrai links/itens, detecta novidades por diff |
| `dataset` | INEP (Catálogo de Escolas / microdados), IBGE municípios, CNPJ aberto | Download de arquivo, filtro local, import |
| `seed_csv` | Unidades SESC-SP, fontes curadas à mão | CSV versionado em `data/seeds/` |
| `search` | Brave/Serper | Consulta de busca com cache (usado para achar sites, não como fonte primária) |

## Contrato (Python, alvo)

```python
class Connector(Protocol):
    slug: str                      # igual a Source.slug
    kind: str                      # api | feed | html_watch | dataset | seed_csv | search

    def fetch(self, ctx: RunContext) -> Iterable[RawItem]:
        """Busca itens brutos. Usa SEMPRE ctx.fetcher (educado + cache). Sem efeitos no banco."""

    def normalize(self, item: RawItem) -> CandidateRecord | None:
        """Converte para OpportunityCandidate/OrganizationCandidate com Evidence(observed).
        Função pura: testável com fixtures."""
```

O runner genérico (`manage.py collect <slug>` / `collect --all`) faz:
`fetch → normalize → dedupe (canonical_key) → upsert → Evidence → CollectionRun`.
Erro em um item não interrompe os demais; erro no conector não interrompe outros conectores.

## PoliteFetcher (regras de coleta responsável)

1. **User-Agent identificado**: `RadarScorpionBits/0.1 (+contato: <email da empresa>)`.
2. **robots.txt** respeitado (cache de 24h por domínio). Disallow → não baixa, registra.
3. **Rate limit por domínio**: padrão 1 requisição a cada 5 s; configurável por fonte.
4. **Cache condicional**: `ETag`/`If-Modified-Since`; conteúdo guardado por hash.
5. **Retries** com backoff exponencial só para 429/5xx/timeouts (máx. 3). 4xx = não insistir.
6. **Limites**: máx. páginas por execução por fonte; máx. tamanho de download (ex. 20 MB,
   exceto `dataset`).
7. **Sem** contornar login, captcha, paywall ou bloqueio. Bloqueou → fonte desabilitada e
   registrada para revisão humana.
8. **Sem navegador headless** no MVP.

## Deduplicação (`canonical_key`)

| Entidade | Chave |
|---|---|
| Opportunity com URL estável | URL canônica (sem querystring de tracking, sem `www`, sem barra final) |
| Opportunity sem URL estável | `slug(organizer) + slug(title) + deadline_date` |
| Organization | `cnpj` > `inep_code` > domínio do site > `slug(name)+ibge_code` |
| ContactPoint | `organization + kind + value normalizado` |

Revisita: item já existente atualiza `last_seen_at` e campos que mudaram (com nova
Evidence); o histórico não é apagado.

## Checklist para adicionar uma fonte

1. Documentar em `docs/research/opportunity-sources.md` ou `organization-sources.md`:
   URL, termos de uso, robots.txt, licença, formato, frequência de atualização, confiabilidade.
2. Criar `Source` (migration de dados ou fixture).
3. Implementar classe em `collection/connectors/<slug>.py`.
4. Gravar fixture real (resposta salva) em `collection/tests/fixtures/<slug>/`.
5. Teste de `normalize` com a fixture (sem rede).
6. Rodar uma coleta real e revisar 10 itens manualmente.
7. Atualizar `STATUS.md`.
