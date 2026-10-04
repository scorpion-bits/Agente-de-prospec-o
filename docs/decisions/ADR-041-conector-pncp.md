# ADR-041 — Conector PNCP: contratações com propostas abertas, filtro por objeto, nada inventado

- **Status:** aceito
- **Data:** 2026-10-04
- **Etapa:** E27

## Contexto
A E22 (ADR-040) ainda espera 4 semanas de uso real; a Fase 4 só segue se a avaliação for «continuar». O PNCP é a 1ª
candidata do plano (ADR-013: contratações até R$ 80 mil têm cota exclusiva ME/EPP/MEI) e **não depende** de dados reais para
ser construído: reusa a camada de coleta (E04) e a extração (E11). O ambiente do Claude não alcança o PNCP (E01 pendente):
parâmetros, códigos de modalidade e formato do JSON vêm do manual das APIs de consulta e de memória, **não** foram conferidos.

## Decisão
1. **Conector `pncp`** (`collection/connectors/pncp.py`, tipo `api`, sem IA): `GET /api/consulta/v1/contratacoes/proposta`
   com `dataFinal` (hoje + `horizon_days`), `codigoModalidadeContratacao`, `uf`, `pagina` e `tamanhoPagina`. Uma consulta por
   UF × modalidade (padrão: SP; concorrência eletrônica, pregão eletrônico, dispensa e credenciamento), editável em `Source.config`.
2. **Uma contratação = uma `Opportunity`** (`kind=procurement`; credenciamento → `call_for_partners`), `official_url` montada do
   `numeroControlePNCP` (página do edital no PNCP; senão o link do sistema de origem), chave `pncp:<numeroControlePNCP>`.
   Sem `extraction_version`: a E11 pode ler o edital para habilitação, atestados e CNAEs.
3. **Relevância pelo objeto** (prefixos no início de palavra, sem acento: curso, oficina, jogo, software, aplicativo, robótica…) e
   `exclude_patterns` (ar condicionado, veículos, obras, jogos esportivos…). Volume alto → filtro de UF e de termos, não IA.
4. **Nada inventado (ADR-004):** datas só se informadas (ISO sem fuso = Brasília); valor estimado zero/ausente fica em branco
   (sigiloso ≠ R$ 0); `cota exclusiva ME/EPP/MEI` só vira `True` quando o **texto** diz isso, nunca `False` por ausência.
5. **Falha por consulta é isolada** (status `partial`); resposta sem `data` é erro explícito; HTTP 204 (resposta do PNCP sem
   resultado) é lista vazia.
6. **Fonte nasce desabilitada e sem `robots_ok`** (termos da API não conferidos), intervalo de 3 s.

## Consequências
+ Custo zero; 28 testes com fixture **sintética**; entra no `make pipeline` assim que o humano habilitar a fonte (P29).
− Códigos de modalidade, `dataFinal` e campos (`valorTotalEstimado`, `orgaoEntidade`, `unidadeOrgao`) são suposições: o primeiro
  `make collect` real diz, e a resposta real vira fixture. Palavras-chave e exclusões são hipótese até revisar 10 itens.
− Contratação cujo objeto não cita as palavras-chave (ex.: «serviço de TI» genérico) é descartada de propósito.
