# Fase 1 — Radar de oportunidades (MVP-A)

Padrão para todos os conectores (E05–E09): seguir o checklist de
`docs/architecture/connectors.md`; usar amostras salvas na E01 como fixtures; revisar
10 itens reais ao final.

---

## E05 — Conector Devpost (hackathons)

**Objetivo:** coletar hackathons abertos/futuros como `Opportunity(kind=hackathon)`.
**Resultado esperado:** `collect devpost` traz hackathons com título, organizador, datas,
modalidade (online/presencial), local, prêmio (texto), temas e URL oficial.
**Ler antes:** `connectors.md`; linha Devpost em `opportunity-sources.md` (resultado E01).
**Alterações:** `collection/connectors/devpost.py`; fixture `collection/tests/fixtures/devpost/`;
testes; `Source` `devpost` (data migration/fixture).
**Dependências:** E04, E01 (fonte ✅).
**Modelo (desenvolvimento):** Claude Sonnet 5.5. **IA em runtime:** nenhuma.
**Justificativa:** JSON estruturado → mapeamento direto.
**Custo:** US$ 0. **Complexidade:** baixa.
**Riscos:** endpoint não documentado pode mudar → testes com fixture detectam; volume
alto de hackathons irrelevantes → filtro por temas/palavras-chave (games, education,
social good, open) + modalidade online ou Brasil.
**Testes:** `normalize` com fixture; datas em timezone correto; dedupe por URL.
**Critério de conclusão:**
- [ ] Coleta real traz ≥ 10 hackathons; 10 revisados manualmente estão corretos. *(pendente do humano: P16)*
- [x] Evidências `observed` com URL e data. *(fixture sintética)*
- [x] Segunda execução não duplica.

**Feito (2026-10-01, ADR-028):** `collection/connectors/devpost.py`, `Source` `devpost` em `load_sources`
(desabilitada), fixture sintética em `tests/fixtures/devpost/` (o ambiente não alcança devpost.com).

---

## E06 — Conector itch.io (game jams)

**Objetivo:** coletar game jams futuras/em andamento como `Opportunity(kind=game_jam)`.
**Resultado esperado:** jams com título, datas (início/fim/votação), hospedagem (online),
link, número de participantes (se disponível), tema quando publicado.
**Ler antes:** `connectors.md`; linha itch.io em `opportunity-sources.md` (resultado E01).
**Alterações:** `collection/connectors/itch_jams.py` (feed `.xml` ou página de listagem
conforme E01), fixtures, testes, `Source`.
**Dependências:** E04, E01.
**Modelo (desenvolvimento):** Claude Sonnet 5.5. **IA em runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** baixa.
**Riscos:** muitas jams pequenas/irrelevantes → filtro mínimo (duração ≥ 48 h, participantes
≥ N ou palavras-chave "brasil", "educação", "godot"); sem API oficial de jams → preferir
feed; se só HTML, respeitar rate limit.
**Testes:** normalização com fixture; filtro; dedupe.
**Critério de conclusão:**
- [ ] Coleta real traz jams futuras; 10 revisadas (P17, depende do humano).
- [x] Filtro documentado e configurável em `Source.config`.

> Feita (ADR-029): listagem HTML `/jams/upcoming` e `/jams/in-progress`; sem feed `.xml` confirmado.

---

## E07 — Conector genérico `html_watch` + primeiras páginas

**Objetivo:** monitorar páginas de listagem de editais/programas sem API e detectar
novidades (novos links/itens), criando oportunidades "candidatas" para extração (E11).
**Resultado esperado:** configurar uma página = uma entrada de `Source` com `url`,
seletor CSS opcional da área de listagem e padrões de link; a execução reporta itens novos.
**Páginas iniciais (validadas na E01):** FAPESP PIPE chamadas, Secretaria de Cultura SP
(ProAC/PNAB — arquivo de editais, inclui a linha de jogos eletrônicos), Oficinas Culturais
(Poiesis), Sebrae-SP, InovAtiva, páginas de editais das prefeituras dos polos (Araraquara,
São Carlos, Ribeirão Preto, Bauru), páginas de chamamento/credenciamento do SESC-SP (se existirem).
**Ler antes:** `connectors.md`; resultados E01.
**Alterações:** `collection/connectors/html_watch.py`; fixtures HTML por página;
`Source` configs; `Opportunity.status=unknown` + flag `needs_extraction`.
**Dependências:** E04, E01.
**Modelo (desenvolvimento):** Claude Sonnet 5.5. **IA em runtime:** nenhuma (diff de links/hash).
**Custo:** US$ 0. **Complexidade:** média.
**Riscos:** páginas mudam layout → fallback "todos os links do conteúdo principal que
casam padrão"; ruído (notícias, não editais) → padrões de URL/palavras-chave por página;
páginas via JS → marcar e deixar fora.
**Testes:** fixture "antes/depois" detecta exatamente os links novos; página inalterada = 0 novos.
**Critério de conclusão:**
- [x] ≥ 5 páginas configuradas sem código específico por página (9, desabilitadas até conferir URL/termos: P18).
- [x] Execução repetida sem mudança = 0 itens novos (testado com fixture antes/depois).
- [x] Itens novos aparecem no admin como candidatos com link e trecho (coleta real pendente: P18).

> Feita (ADR-030): conector por `kind`, seletor CSS simples, sem flag `needs_extraction` (candidata = `status=unknown`).

---

## E08 — Conector Querido Diário (diários oficiais municipais)

**Objetivo:** buscar em diários oficiais dos polos (Araraquara, São Carlos, Ribeirão Preto,
Bauru) e municípios próximos termos que indiquem editais, chamamentos, credenciamentos de
oficineiros e demandas relacionadas a jogos/cursos/tecnologia.
**Resultado esperado:** para cada ocorrência: município, data, trecho, link do PDF →
`Opportunity(kind=edital|procurement|call_for_partners, needs_extraction=true)`.
**Ler antes:** `opportunity-sources.md` (Querido Diário + estratégia de palavras-chave).
**Alterações:** `collection/connectors/querido_diario.py`; config com municípios (códigos
IBGE) e consultas; fixtures; testes.
**Dependências:** E04, E01 (cobertura confirmada). E12 não é necessária (usar códigos IBGE na config).
**Modelo (desenvolvimento):** Claude Sonnet 5.5. **IA em runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** média.
**Riscos:** muitos falsos positivos (ex. "jogos" em contexto esportivo) → consultas com
termos combinados + lista de exclusão; município sem cobertura → registrar e usar `html_watch`.
**Testes:** normalização; janela de datas incremental (só desde a última execução); dedupe por (município, data, trecho-hash).
**Critério de conclusão:**
- [x] Consultas configuradas para ≥ 4 municípios (6 configurados; cobertura real confirmada só na 1ª coleta: P19).
- [x] Coleta incremental funciona (janela = última execução `ok` − 1 dia; testado).
- [ ] Revisão de 10 ocorrências: taxa de relevância anotada em STATUS (para ajustar termos) — pendente: P19.

> Feita (ADR-031): consultas combinadas + exclusões, janela por `CollectionRun`, sondagem de cobertura; fonte desabilitada.

---

## E09 — Conector Mapas Culturais

**Objetivo:** coletar oportunidades (editais culturais, incluindo PNAB) das instâncias de
Mapas Culturais relevantes (nacional + SP/municípios, conforme E01).
**Ler antes:** `opportunity-sources.md` (Mapas Culturais).
**Alterações:** `collection/connectors/mapas_culturais.py` (uma classe, várias instâncias via config); fixtures; testes.
**Dependências:** E04, E01.
**Modelo (desenvolvimento):** Claude Sonnet 5.5. **IA em runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** baixa.
**Riscos:** campos variam por instância → normalização tolerante; oportunidades de artes
não relacionadas → filtro por palavras-chave (jogos, games, audiovisual, tecnologia,
cultura digital, educação, oficina).
**Testes:** fixture de 2 instâncias; filtro; datas de inscrição.
**Critério de conclusão:**
- [x] ≥ 2 instâncias configuradas; prazo de inscrição mapeado só quando informado. *(fixture sintética)*
- [ ] 10 revisadas. *(pendente do humano: P20)*

> Feita (ADR-032): uma `Source` com várias instâncias em `config`, datas e status só do que a instância informa, falha isolada por instância; fonte desabilitada.

---

## E10 — Camada de IA (`llm/`)

**Objetivo:** serviço único de IA orientado a **tarefas**, com estratégias intercambiáveis
(regras, Gemini, Claude, local) e custo controlado (ADR-003, ADR-011).
**Resultado esperado:** `ai.run(task, input, schema)` funcional com FakeProvider (testes),
estratégia `rules`, Gemini (free tier e projeto pago com créditos do AI Pro) e Anthropic
(Haiku); cache, log de custo, teto mensal e classe de dados (`public`/`internal`).
**Ler antes:** `docs/architecture/llm-strategy.md`, `docs/research/ai-models-and-costs.md`.
**Alterações:** `llm/tasks.py` (registro de tarefas → lista de estratégias em settings);
`llm/providers/{base,fake,rules,gemini,anthropic,ollama}.py` (ollama pode ser stub documentado
se não houver hardware; Gemini com suporte a entrada de PDF); `llm/router.py`; `llm/cache.py`; `llm/models.py` (`LLMCall`); `llm/budget.py`;
`llm/pricing.py` (tabela de preços em config); `.env.example` com chaves;
`manage.py llm_usage` (custo do mês).
**Dependências:** E03.
**Modelo (desenvolvimento):** Claude Sonnet 5.5 (consultar a documentação oficial dos SDKs:
`google-genai` para Gemini; para o SDK Anthropic, carregar a skill `claude-api`).
**IA em runtime:** infraestrutura (sem uso real ainda).
**Custo:** US$ 0 (testes usam FakeProvider; 1–2 chamadas reais de fumaça < US$ 0,01).
**Complexidade:** média.
**Riscos:** SDKs mudam → isolar em adapters; free tier com limites diferentes do documentado
→ tratar 429 como "próximo provedor".
**Testes:** cache acerta na 2ª chamada; teto bloqueia provedor pago e permite gratuito;
falha de schema → retry → fallback; custo calculado corretamente; entrada `internal` nunca
roteada a free tier; trocar a estratégia de uma tarefa só por configuração.
**Critério de conclusão:**
- [x] Todos os testes sem rede.
- [ ] Chamada real de fumaça registrada em `LLMCall` com custo. *(pendente do humano: P21, `make llm-smoke`)*
- [x] Nenhum outro módulo importa SDK de provedor diretamente (teste `test_only_llm_providers_talk_to_model_apis_or_import_sdks`).

> Feita (ADR-033): HTTP direto com `httpx` em vez de SDKs; Ollama como adapter genérico (`OLLAMA_BASE_URL`); tarefas reais chegam na E11.

---

## E11 — Extração estruturada de oportunidades

**Objetivo:** transformar páginas/PDFs de oportunidades "candidatas" em campos
estruturados confiáveis (prazo, elegibilidade, **requisitos de empresa** — aceita MEI?
natureza jurídica, tempo mínimo de CNPJ/sede, CNAE, cota ME/EPP —, abrangência, prêmio,
benefícios, custo de participação, esforço estimado, resumo curto).
**Resultado esperado:** `manage.py extract_opportunities` processa itens com
`needs_extraction`, grava campos + `Evidence` com citação verificada, e um relatório de
acurácia em amostra revisada por humano.
**Ler antes:** `llm-strategy.md` (redução de tokens, alucinação), ADR-004, `data-model.md` (Opportunity).
**Alterações:** `extraction/text.py` (HTML → texto com trafilatura; PDF → texto com
pypdf/pdfplumber; seleção de janelas por palavras-chave); `extraction/rules.py` (regex de
datas, valores R$, "MEI", "ME/EPP", "pessoa jurídica", "há mais de N anos", CNAE); `extraction/opportunity.py` (schema Pydantic
com `{value|unknown, quote}` por campo, prompt versionado em arquivo, verificação de
citação normalizada); comando de gestão; `docs/research/extraction-eval.md` (amostra de 20).
**Dependências:** E10, e ao menos um conector com candidatos (E07 ou E08).
**Modelo (desenvolvimento):** Claude Opus 5.5 (desenho de prompt/schema e avaliação).
**IA em runtime:** Gemini Flash-Lite (free) → Gemini Flash (projeto pago com créditos; também
para PDF escaneado via entrada nativa de PDF) → Claude Haiku 4.5. Local (Ollama) opcional.
**Justificativa:** texto livre e PDFs variados; tarefa de extração, não de raciocínio longo —
modelos pequenos bastam com schema + citação.
**Custo:** US$ 0 no free tier; ~US$ 0,01/documento em Haiku sem Batch.
**Complexidade:** alta.
**Riscos:** PDFs escaneados (sem texto) → Gemini com PDF nativo; se falhar, revisão humana;
datas ambíguas → regex confere; free tier sai do ar → fallback; custo de PDF enorme → janelas + limite duro.
**Testes:** FakeProvider com respostas gravadas; verificação de citação rejeita citação
inexistente; regex de datas/valores; documento idêntico não chama LLM 2×.
**Critério de conclusão:**
- [ ] 20 extrações revisadas: acurácia por campo registrada em `extraction-eval.md`;
      prazo e requisitos de empresa ≥ 90% corretos ou `unknown` (nunca errados com confiança).
- [ ] Pelo menos 1 edital real com requisito de empresa (ex. idade mínima de CNPJ) extraído com citação.
- [ ] Custo total da etapa registrado em `LLMCall`.
- [ ] Campos sem citação verificada aparecem como inferência no admin.
