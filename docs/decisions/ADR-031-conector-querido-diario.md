# ADR-031 — Conector Querido Diário: consultas por termos, janela incremental e cobertura

- **Status:** aceito
- **Data:** 2026-10-01
- **Etapa:** E08

## Contexto
Editais, chamamentos e credenciamentos municipais aparecem primeiro no diário oficial, muitas vezes sem página própria
na prefeitura. A API pública do Querido Diário (Open Knowledge Brasil) faz busca textual por município, período e
termos. O ambiente do Claude não alcança a API (E01 pendente): o formato do JSON (`gazettes`, `excerpts`, `url`,
`territory_id`, `date`…) vem da documentação e de memória, **não** foi conferido.

## Decisão
1. **Conector `querido-diario`** (`collection/connectors/querido_diario.py`, tipo `api`, sem IA). Uma requisição por
   consulta e página para **todos** os municípios (`territory_ids` repetido), em vez de uma por município × consulta.
   Municípios (códigos IBGE, conferidos contra a tabela `Municipality`) e consultas ficam em `Source.config`, com
   padrão no código: Araraquara, São Carlos, Ribeirão Preto, Bauru, Matão e Américo Brasiliense; 8 consultas de termos
   combinados (as de `opportunity-sources.md`).
2. **Um trecho = uma candidata.** `Opportunity(status=unknown)` sem `extraction_version` (a E11 lê o PDF), com
   `official_url` = PDF do diário, abrangência municipal, **sem datas** de inscrição (a data do diário é a de
   publicação, não prazo; fica só como `Evidence` `published_at`, ADR-004). Tipo por regra no trecho:
   chamamento/credenciamento/oficineiro → `call_for_partners`; licitação/pregão → `procurement`; senão `edital`.
   O trecho citado vai literal na evidência (`observed`), com a consulta que o achou.
3. **Dedupe:** chave `qd:<ibge>|<data>|<hash do trecho>` (município, data, trecho normalizado). O mesmo trecho achado
   por duas consultas, ou numa segunda execução, não duplica.
4. **Janela incremental:** `published_since` = dia da última execução **concluída (`ok`) e não simulada** menos 1 dia
   de sobreposição; sem execução anterior, 60 dias. Execução parcial/com erro não avança a janela (o que faltou é
   tentado de novo) e `--dry-run` nunca "gasta" a novidade. Estado = o próprio `CollectionRun` (sem migration).
5. **Falsos positivos:** consultas combinadas (`oficina + (jogos | games)`) **e** lista de exclusão por regex no trecho
   (`Jogos Abertos/Regionais/Escolares`, azar, campeonato, futebol), editável em `exclude_patterns`.
6. **Cobertura:** ao fim, sondagem de 1 requisição por município (`size=1`, últimos 30 dias). Município sem nenhum
   diário vira erro **explícito** na execução («use `html_watch`»; status `partial`), sem derrubar os demais.
7. **Fonte nasce desabilitada e sem `robots_ok`** (termos de uso da API não conferidos, P19), com teto de 120
   requisições e intervalo de 2 s.
8. Resposta sem `gazettes` = erro «Resposta inesperada», nunca coleta vazia silenciosa.

## Consequências
+ Custo zero; 29 testes com fixture **sintética** (`tests/fixtures/querido_diario/`).
− Formato real da API, sintaxe dos operadores de `querystring` (`+`, `|`, aspas) e o fato de `excerpts` virem com
  `<em>` são suposições: o primeiro `make collect` real diz, e a resposta real vira fixture (P19).
− Taxa de relevância e lista de exclusão são hipóteses até a revisão de 10 ocorrências (P19).
− A sondagem de cobertura pode acusar município que só ficou sem publicar nos últimos 30 dias; o texto do erro diz isso.
