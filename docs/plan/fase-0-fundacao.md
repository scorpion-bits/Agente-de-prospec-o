# Fase 0 — Fundação

## E00 — Planejamento, pesquisa e documentação ✅
Concluída em 2026-09-30. Registro: `docs/history/sessions/2026-09-30-E00.md`.

---

## E01 — Validação de fontes + baseline manual (spike)

**Objetivo:** confirmar, a partir de uma máquina com acesso normal à internet, que as
fontes prioritárias do MVP são acessíveis, estáveis e permitidas; e registrar um
**baseline manual** para medir depois se o sistema acha o que não acharíamos.

**Por que é a primeira etapa:** toda a Fase 1 e a Fase 3 dependem dessas fontes, e o
ambiente de planejamento não conseguiu testá-las (egress bloqueado). Descobrir agora que
uma fonte não funciona custa minutos; descobrir na E08 custa uma etapa.
**Não é código de produto**: scripts descartáveis em `spikes/E01/` (podem ser apagados depois).

**Ler antes:** `docs/research/opportunity-sources.md`, `docs/research/organization-sources.md`,
`docs/research/legal-and-compliance.md` (seção checklist por fonte).

**Alterações:**
- `spikes/E01/*.py` ou `*.sh` — chamadas simples (`httpx`/`curl`) a cada fonte, salvando
  1 resposta de exemplo em `spikes/E01/samples/` (servirão de fixture na Fase 1).
- `docs/research/opportunity-sources.md` e `organization-sources.md` — preencher coluna
  "Validado" (✅/❌/⚠ + observação: formato, paginação, campos úteis, robots.txt, termos).
- `docs/research/baseline-manual.md` — **novo**: o humano (ou Claude com o humano) gasta
  até 1 h buscando manualmente oportunidades e escolas/SESCs relevantes, e registra o que
  encontrou (título, link, data) e o tempo gasto.
- `docs/plan/STATUS.md` — respostas às perguntas abertas que o humano fornecer.

**Fontes a validar (mínimo):** Devpost API; itch.io (`/jams`, `.xml`); Querido Diário
(cobertura de Araraquara, São Carlos, Matão, Américo Brasiliense; exemplo de busca);
Mapas Culturais (instâncias nacional e SP; `/api/opportunity/find`); páginas FAPESP PIPE,
ProAC/PNAB, Sebrae-SP, InovAtiva, Prefeitura de Araraquara (URL da página de editais);
SESC-SP (existe página de credenciamento/chamamento?); INEP Catálogo de Escolas (há
exportação por município? campos?); IBGE localidades.

**Dependências:** nenhuma.
**Modelo (desenvolvimento):** Claude Sonnet 5.5 (tarefa de investigação simples).
**IA em runtime:** nenhuma.
**Justificativa:** trabalho de leitura/verificação; não exige raciocínio pesado.
**Custo:** US$ 0 (runtime). ~1 sessão.
**Complexidade:** baixa.
**Riscos:** fonte exige JS/login (→ marcar ❌ e propor alternativa); termos proíbem uso
automatizado (→ remover do MVP); cobertura do Querido Diário não inclui a região
(→ `html_watch` do diário oficial municipal).
**Testes:** não há testes automatizados; evidência = amostras salvas + tabela preenchida.
**Critério de conclusão:**
- [ ] Todas as fontes prioritárias com status ✅/❌/⚠ e observação.
- [ ] Pelo menos 1 amostra real salva por fonte ✅.
- [ ] `baseline-manual.md` com ≥ 10 itens e tempo gasto.
- [ ] Lista de fontes do MVP confirmada (ou ajustada) em STATUS.
- [ ] Perguntas abertas respondidas ou marcadas como pendentes.

---

## E02 — Esqueleto do projeto

**Objetivo:** projeto Python/Django executável, com qualidade automatizada desde o início.

**Ler antes:** `CLAUDE.md` (stack/estrutura), `docs/architecture/overview.md` (módulos).

**Alterações:**
- `pyproject.toml` (uv; deps: django, httpx, python-dotenv/django-environ, pydantic;
  dev: pytest, pytest-django, ruff), `uv.lock`.
- `radar/` (settings com `.env`, SQLite WAL, `TIME_ZONE="America/Sao_Paulo"`,
  `LANGUAGE_CODE="pt-br"`), apps vazios `core`, `collection`, `extraction`, `llm`,
  `scoring`, `reports`.
- `Makefile` (ou `justfile`): `make setup`, `make run`, `make test`, `make lint`,
  `make check` (lint + test + docs-check), `make docs-check` (limites de linhas do
  CLAUDE.md/STATUS.md).
- `.env.example`, `.gitignore` (inclui `data/`, `.env`, `spikes/**/samples` se grandes).
- `.github/workflows/ci.yml` — `make check` em push/PR (GitHub Actions, gratuito).
- `README.md` — seção "Como rodar".

**Dependências:** E01 (não bloqueante tecnicamente; pode rodar em paralelo).
**Modelo (desenvolvimento):** Claude Sonnet 5.5.
**IA em runtime:** nenhuma.
**Justificativa:** boilerplate bem conhecido.
**Custo:** US$ 0.
**Complexidade:** baixa.
**Riscos:** versão de Python ausente na máquina do usuário (documentar instalação via uv).
**Testes:** teste de fumaça (`/admin/` responde 302/200; `manage.py check` sem erros).
**Critério de conclusão:**
- [ ] `make setup && make check` passa numa máquina limpa.
- [ ] `make run` abre o admin; superusuário criado via comando documentado.
- [ ] CI verde no GitHub.
- [ ] CLAUDE.md "Estrutura" confere com o que existe.

---

## E03 — Modelo de dados núcleo + admin básico + catálogo de serviços

**Objetivo:** criar as entidades centrais com evidência e o catálogo de serviços como dado.

**Ler antes:** `docs/architecture/data-model.md`, ADR-004.

**Alterações:**
- `core/models.py`: `Source`, `Organization`, `ContactPoint`, `Opportunity`, `Evidence`,
  `ServiceOffering`, `Match`, `Triage`, `Suppression` (Score fica para E13; Municipality para E12
  — usar `CharField` provisório `municipality_name`/`uf` ou FK nula adicionada na E12).
- `core/admin.py`: listas com filtros (tipo, status, UF), busca, inlines de `Evidence` e
  `ContactPoint`; inferências destacadas (ícone/cor).
- `core/fixtures/services.json` ou data migration: catálogo inicial de serviços —
  `course_gamedev` (curso de desenvolvimento de jogos), `workshop_gamedev` (oficina),
  `game_jam_org` (organização de game jam), `extracurricular_school` (atividade
  extracurricular), `educational_game`, `institutional_game`, `gamification`,
  `custom_software`, `web_app`, `landing_page`, `institutional_site`, com palavras-chave
  e perfis geográficos.
- `core/services/evidence.py`: helper `record_evidence(entity, field, value, kind, source, ...)`.
- Testes de modelo e do helper.

**Dependências:** E02.
**Modelo (desenvolvimento):** Claude Opus 5.5 (decisões de modelagem que afetam todo o resto).
**IA em runtime:** nenhuma.
**Custo:** US$ 0.
**Complexidade:** média.
**Riscos:** modelagem excessiva → criar só campos listados em `data-model.md`; `Evidence`
genérica (entity_type/id) pode complicar admin → usar `GenericForeignKey` ou par de campos simples
e documentar a escolha.
**Testes:** criação de entidades; dedupe por chaves únicas; helper de evidência; fixture de serviços carrega.
**Critério de conclusão:**
- [ ] Migrations aplicam do zero.
- [ ] Admin permite cadastrar manualmente uma oportunidade com 2 evidências (1 observed, 1 inferred) e elas aparecem distintas.
- [ ] Catálogo de serviços carregado e editável no admin.
- [ ] `data-model.md` atualizado com qualquer desvio.

---

## E04 — Infra de coleta

**Objetivo:** base comum para todos os conectores: fetch educado, cache, registro de
execuções e runner.

**Ler antes:** `docs/architecture/connectors.md`, `docs/research/legal-and-compliance.md` (scraping).

**Alterações:**
- `collection/fetcher.py`: `PoliteFetcher` (User-Agent do settings, robots.txt com cache,
  rate limit por domínio, ETag/If-Modified-Since, retries com backoff, limite de tamanho).
- `collection/models.py`: `CollectionRun`, `RawDocument` (+ armazenamento em `data/raw/`).
- `collection/base.py`: `Connector` (Protocol), `RunContext`, `RawItem`, `CandidateRecord`.
- `collection/registry.py` + `collection/management/commands/collect.py`
  (`collect <slug>`, `collect --all`, `--dry-run`, `--limit`).
- `collection/upsert.py`: dedupe por `canonical_key`, upsert + evidências.
- Conector de exemplo `seed_csv` genérico (lê CSV de `data/seeds/`) — útil já na E17.
- Testes com `respx`/transport mock do httpx (sem rede).

**Dependências:** E03.
**Modelo (desenvolvimento):** Claude Sonnet 5.5.
**IA em runtime:** nenhuma.
**Custo:** US$ 0.
**Complexidade:** média.
**Riscos:** robots.txt com sintaxe estranha (usar `urllib.robotparser` + fallback conservador);
cache crescer (limite e limpeza documentados).
**Testes:** robots bloqueia; rate limit respeitado (tempo simulado); 304 reutiliza cache;
retry em 503; upsert idempotente (rodar 2× não duplica).
**Critério de conclusão:**
- [ ] `manage.py collect seed_csv --dry-run` funciona com CSV de exemplo.
- [ ] Execução registrada em `CollectionRun` com contagens.
- [ ] Rodar duas vezes não cria duplicatas.
- [ ] Nenhum teste faz acesso de rede.
