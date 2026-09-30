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
- [ ] Coleta real traz ≥ 10 hackathons; 10 revisados manualmente estão corretos.
- [ ] Evidências `observed` com URL e data.
- [ ] Segunda execução não duplica.

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
- [ ] Coleta real traz jams futuras; 10 revisadas.
- [ ] Filtro documentado e configurável em `Source.config`.

---

## E07 — Conector genérico `html_watch` + primeiras páginas

**Objetivo:** monitorar páginas de listagem de editais/programas sem API e detectar
novidades (novos links/itens), criando oportunidades "candidatas" para extração (E11).
**Resultado esperado:** configurar uma página = uma entrada de `Source` com `url`,
seletor CSS opcional da área de listagem e padrões de link; a execução reporta itens novos.
**Páginas iniciais (validadas na E01):** FAPESP PIPE chamadas, Secretaria de Cultura SP
(ProAC/PNAB), Sebrae-SP editais/programas, InovAtiva, Prefeitura de Araraquara (editais).
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
- [ ] 5 páginas configuradas sem código específico por página.
- [ ] Execução repetida sem mudança = 0 itens novos.
- [ ] Itens novos aparecem no admin como candidatos com link e trecho.

---

## E08 — Conector Querido Diário (diários oficiais municipais)

**Objetivo:** buscar em diários oficiais de Araraquara e região termos que indiquem
editais, chamamentos, credenciamentos e demandas relacionadas a jogos/cursos/tecnologia.
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
- [ ] Consultas configuradas para ≥ 4 municípios cobertos.
- [ ] Coleta incremental funciona.
- [ ] Revisão de 10 ocorrências: taxa de relevância anotada em STATUS (para ajustar termos).

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
- [ ] ≥ 2 instâncias configuradas; oportunidades com prazo de inscrição corretamente mapeado.
- [ ] 10 revisadas.

---

## E10 — Camada `llm/`

**Objetivo:** infraestrutura única para qualquer uso de LLM, com custo controlado.
**Resultado esperado:** `llm.complete_json(...)` funcional com FakeProvider (testes),
Gemini (free) e Anthropic (Haiku), cache, log de custo e teto mensal.
**Ler antes:** `docs/architecture/llm-strategy.md`, `docs/research/ai-models-and-costs.md`.
**Alterações:** `llm/providers/{base,fake,gemini,anthropic,groq,ollama}.py` (groq/ollama
podem ser stubs documentados se não houver chave/hardware); `llm/router.py` (roteamento por
tarefa via settings); `llm/cache.py`; `llm/models.py` (`LLMCall`); `llm/budget.py`;
`llm/pricing.py` (tabela de preços em config); `.env.example` com chaves;
`manage.py llm_usage` (custo do mês).
**Dependências:** E03.
**Modelo (desenvolvimento):** Claude Sonnet 5.5 (consultar a documentação oficial dos SDKs;
para o SDK Anthropic, carregar a skill `claude-api`).
**IA em runtime:** infraestrutura (sem uso real ainda).
**Custo:** US$ 0 (testes usam FakeProvider; 1–2 chamadas reais de fumaça < US$ 0,01).
**Complexidade:** média.
**Riscos:** SDKs mudam → isolar em adapters; free tier com limites diferentes do documentado
→ tratar 429 como "próximo provedor".
**Testes:** cache acerta na 2ª chamada; teto bloqueia provedor pago e permite gratuito;
falha de schema → retry → fallback; custo calculado corretamente.
**Critério de conclusão:**
- [ ] Todos os testes sem rede.
- [ ] Chamada real de fumaça registrada em `LLMCall` com custo.
- [ ] Nenhum outro módulo importa SDK de provedor diretamente.

---

## E11 — Extração estruturada de oportunidades

**Objetivo:** transformar páginas/PDFs de oportunidades "candidatas" em campos
estruturados confiáveis (prazo, elegibilidade, exige CNPJ, abrangência, prêmio,
benefícios, custo de participação, esforço estimado, resumo curto).
**Resultado esperado:** `manage.py extract_opportunities` processa itens com
`needs_extraction`, grava campos + `Evidence` com citação verificada, e um relatório de
acurácia em amostra revisada por humano.
**Ler antes:** `llm-strategy.md` (redução de tokens, alucinação), ADR-004, `data-model.md` (Opportunity).
**Alterações:** `extraction/text.py` (HTML → texto com trafilatura; PDF → texto com
pypdf/pdfplumber; seleção de janelas por palavras-chave); `extraction/rules.py` (regex de
datas, valores R$, CNPJ/MEI/pessoa física); `extraction/opportunity.py` (schema Pydantic
com `{value|unknown, quote}` por campo, prompt versionado em arquivo, verificação de
citação normalizada); comando de gestão; `docs/research/extraction-eval.md` (amostra de 20).
**Dependências:** E10, e ao menos um conector com candidatos (E07 ou E08).
**Modelo (desenvolvimento):** Claude Opus 5.5 (desenho de prompt/schema e avaliação).
**IA em runtime:** Gemini Flash-Lite (free) → fallback Claude Haiku 4.5 (Batch quando pago).
Local (Ollama) opcional se hardware permitir.
**Justificativa:** texto livre e PDFs variados; tarefa de extração, não de raciocínio longo —
modelos pequenos bastam com schema + citação.
**Custo:** US$ 0 no free tier; ~US$ 0,01/documento em Haiku sem Batch.
**Complexidade:** alta.
**Riscos:** PDFs escaneados (sem texto) → marcar `needs_ocr` e deixar para humano;
datas ambíguas → regex confere; free tier sai do ar → fallback; custo de PDF enorme → janelas + limite duro.
**Testes:** FakeProvider com respostas gravadas; verificação de citação rejeita citação
inexistente; regex de datas/valores; documento idêntico não chama LLM 2×.
**Critério de conclusão:**
- [ ] 20 extrações revisadas: acurácia por campo registrada em `extraction-eval.md`;
      prazo e "exige CNPJ" ≥ 90% corretos ou marcados `unknown` (nunca errados com confiança).
- [ ] Custo total da etapa registrado em `LLMCall`.
- [ ] Campos sem citação verificada aparecem como inferência no admin.
