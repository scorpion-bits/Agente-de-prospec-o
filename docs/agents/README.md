# Agentes — catálogo e decisão

## Conclusão (resumo)

Dos 8 "agentes" imaginados inicialmente, **só 1 é um agente de verdade** (loop de
ferramentas decidido pelo modelo) e ele fica **fora do MVP**. Os demais viram:

- **pipelines determinísticos** (código, regras, regex) — custo zero, previsíveis; ou
- **chamadas únicas de LLM com schema** (não agentes) — baratas, cacheáveis, validáveis.

Por quê: um agente autônomo gasta tokens de forma imprevisível, é difícil de testar e
de auditar. Para 1–3 usuários com orçamento ~zero, o ganho não compensa enquanto um
pipeline simples resolver. (ADR-003)

Terminologia neste repositório:
- **Worker**: etapa de pipeline determinística (sem LLM).
- **Extrator LLM**: uma chamada LLM com entrada fixa → JSON validado.
- **Agente**: LLM que escolhe ferramentas em loop até concluir.

## Tabela resumo

| "Agente" original | Vira | Função | Modelo | Custo/mês | Prioridade |
|---|---|---|---|---|---|
| Discovery Agent | **Workers de coleta** (conectores) | Encontra oportunidades/organizações em fontes | Nenhum | 0 | MVP (E05–E09, E17) |
| Research Agent | **Worker de enriquecimento** (fetch + texto) + Extrator LLM | Baixa e lê a página/PDF do item | Nenhum / ver abaixo | 0 | MVP |
| Opportunity Analysis Agent | **Extrator LLM** `extract_opportunity_fields` | Extrai prazo, elegibilidade, prêmio, exige CNPJ, benefícios, esforço | Gemini Flash-Lite free → Haiku 4.5 | US$0–6 | MVP (E11) |
| Qualification Agent | **Gates + fatores** do scoring | Descarta inviável, qualifica o resto | Nenhum | 0 | MVP (E13) |
| Contact Discovery Agent | **Worker** `extract_contacts` | Contatos públicos institucionais do próprio site | Nenhum | 0 (+ busca na cota grátis) | MVP (E18–E19) |
| Matching Agent | **Regras** `match_services_v1` (+ justificativa LLM opcional) | Necessidade provável ↔ serviço | Nenhum (opcional Flash-Lite) | 0–1 | MVP (E20) |
| Prioritization Agent | **Scoring determinístico** | Ordena por retorno esperado | Nenhum | 0 | MVP (E13, E21) |
| Outreach Preparation Agent | **Extrator LLM** `draft_outreach` (1 chamada) | Rascunho de mensagem com base só em evidências | Claude Sonnet 5.5 | < US$1 | Fase 4 (E24) |
| (novo) Deep Research Agent | **Agente de verdade**, sob demanda | Investiga 1 organização/edital a fundo quando o humano pede | Claude Sonnet 5.5 + ferramentas restritas | US$1–10 com teto | Fase 4 (E28), só se houver lacuna medida |

## Fichas

### 1. Workers de coleta (ex-Discovery Agent)
- **Problema**: saber que a oportunidade/organização existe.
- **Por que não é agente**: fontes são conhecidas e estruturadas; o que muda é o parser.
- **Input**: config da `Source`. **Output**: `Opportunity`/`Organization` + `Evidence(observed)`.
- **Ferramentas**: `PoliteFetcher`, parser do conector.
- **Quando**: cron (diário para oportunidades; semanal/mensal para datasets).
- **Duplicação**: `canonical_key` + `RawDocument.content_hash`.
- **Validação**: testes com fixtures; revisão humana de 10 itens por fonte nova.
- **Alucinação**: não se aplica (sem LLM). **Fonte**: URL e data em cada `Evidence`.

### 2. Extrator `extract_opportunity_fields` (ex-Opportunity Analysis/Research)
- **Problema**: editais são texto livre/PDF; prazos, elegibilidade e benefícios não vêm estruturados.
- **Por que LLM**: linguagem variável demais para regex; mas **uma chamada** basta.
- **Modelo**: Gemini Flash-Lite (free) → fallback Claude Haiku 4.5 (Batch). Local: Ollama.
- **Input**: texto pré-filtrado do documento (≤ 12k tokens) + metadados do conector.
- **Output**: JSON (schema Pydantic) com cada campo = `{value | "unknown", quote}`.
- **Quando**: após coleta, só para itens novos ou com `content_hash` alterado.
- **Duplicação**: cache por hash(conteúdo + prompt_version + modelo).
- **Validação**: schema; **citação precisa existir no texto**; datas conferidas por regex.
- **Alucinação**: `unknown` permitido; campos sem citação válida → `verified=false`.
- **Fonte**: `Evidence(kind=observed se citação verificada, senão inferred, method=llm:<modelo>@<versão>)`.
- **Custo**: US$0 no free tier; ~US$0,005–0,01/documento no Haiku (antes do desconto Batch).

### 3. Worker `extract_contacts` (ex-Contact Discovery)
- **Problema**: achar formas públicas de contato.
- **Por que não é agente**: contatos aparecem em padrões conhecidos (`mailto:`, `tel:`,
  `wa.me/`, páginas "contato"/"fale conosco", rodapé, schema.org, links de redes).
- **Input**: `Organization.website`. **Output**: `ContactPoint` + `Evidence(observed)` com trecho.
- **Limites**: máx. 5 páginas por site; só o domínio da organização; robots.txt.
- **Regras**: prioriza institucionais (`contato@`, `secretaria@`, telefone fixo); marca
  `is_personal=true` se o e-mail parecer nominal; nunca "adivinha" padrões de e-mail
  (ex. `nome.sobrenome@`); nunca busca pessoas no LinkedIn.

### 4. Regras `match_services_v1` (ex-Matching)
- **Problema**: "empresa X provavelmente compraria serviço Y".
- **Por que regras**: o catálogo é pequeno e as correlações são explícitas
  (escola privada com ensino fundamental II/médio → curso extracurricular de jogos;
  site ausente/sem HTTPS → site institucional; CNAE de agência → parceria/jogos para campanhas).
- **Output**: `Match` com `reasons` apontando para evidências; razões baseadas em regra
  são `inferred` (é uma hipótese), mas citam os fatos `observed` que a sustentam.
- **LLM opcional**: 2 frases de justificativa para o top-20 da semana (Flash-Lite).

### 5. Scoring (ex-Qualification + Prioritization)
Ver `docs/architecture/scoring.md`. Determinístico, explicável, versionado.

### 6. Extrator `draft_outreach` (Fase 4)
- **Problema**: escrever uma primeira mensagem boa leva tempo.
- **Modelo**: Claude Sonnet 5.5 (qualidade de texto importa; volume baixo).
- **Input**: só `Evidence` da organização + serviço do match + portfólio da Scorpion Bits
  (texto fixo, cacheável). **Proibido** inventar fatos: cada afirmação sobre o
  destinatário deve citar uma evidência.
- **Output**: rascunho + lista de afirmações com evidência. Humano edita e envia manualmente.

### 7. Deep Research Agent (Fase 4, condicional)
- **Problema**: às vezes um lead/edital de alto valor merece investigação que o pipeline
  não cobre (ex.: entender o programa pedagógico de uma rede de escolas).
- **Condição para existir**: E22 mostrar que leads de alto valor ficam sem dados suficientes.
- **Modelo**: Claude Sonnet 5.5, `effort` baixo/médio, teto rígido de tokens e US$ por execução.
- **Ferramentas (restritas, sem acesso livre ao sistema)**:
  `search_web(query)` (com cache e cota), `fetch_page(url)` (via PoliteFetcher, mesmo
  domínio da org + fontes oficiais), `get_known_facts(org_id)`, `propose_evidence(field, value, url, quote)`.
  O agente **não escreve no banco**: propõe evidências; o sistema verifica a citação e o
  humano aprova.
- **Quando**: só por clique humano. Nunca em lote/cron.
- **Duplicação**: não roda de novo para a mesma org em < 30 dias sem confirmação.

## Regras gerais para qualquer novo agente/extrator

1. Justificar por escrito por que regras não bastam (ADR se custar > US$ 5/mês).
2. Ferramentas explícitas e mínimas; nada de shell/SQL livre.
3. Toda saída vira `Evidence` com `method` e fonte; nada vai direto para campos "verdadeiros".
4. Teto de custo por execução e por mês na camada `llm/`.
5. Avaliação com amostra revisada por humano antes de ligar em produção.
