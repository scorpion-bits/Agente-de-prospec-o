# ADR-032 — Conector Mapas Culturais: uma `Source`, várias instâncias

- **Status:** aceito
- **Data:** 2026-10-01
- **Etapa:** E09

## Contexto
O Mapas Culturais é software livre usado pelo MinC (mapa nacional), por estados e por municípios; cada instância expõe
a mesma API pública (`/api/opportunity/find`) com editais e chamadas culturais, inclusive PNAB. O ambiente do Claude
não alcança nenhuma instância (E01 pendente): endereços das instâncias, formato do JSON e operadores de filtro
(`GTE(...)`) vêm da documentação e de memória, **não** foram conferidos.

## Decisão
1. **Conector `mapas-culturais`** (`collection/connectors/mapas_culturais.py`, tipo `api`, sem IA). Uma classe, **uma
   `Source`** e as instâncias em `Source.config["instances"]` (`slug`, `name`, `base_url`, `scope`, `uf`,
   `municipality_name`); acrescentar uma prefeitura é editar o JSON no admin, sem código. Padrão no código: mapa
   nacional (`mapa.cultura.gov.br`) e Estado de SP (`mapacultural.sp.gov.br`), endereços de memória (P20).
2. **Uma oportunidade = uma `Opportunity`** com `official_url` = página da própria instância, chave de dedupe
   `mc:<host>|<id>` (estável entre execuções e entre títulos editados). Sem `extraction_version` fixada: a E11 pode
   ler a página para requisitos (MEI, CNPJ).
3. **Datas só se a instância informa** (ADR-004). `registrationFrom`/`registrationTo` aceitam texto, ISO ou objeto
   `{date, timezone}`; sem fuso vale Brasília; valor ilegível vira vazio, nunca chute. `status` é derivado delas
   (futura → `upcoming`, vencida → `closed`, sem datas → `unknown`).
4. **Filtro de relevância** por prefixos sem acento em título, resumo e áreas (jogo, game, audiovisual, tecnologia,
   cultura digital, educa, oficina, software, program…), editável em `keywords`; `exclude_patterns` opcional.
   A requisição já pede só `registrationTo >= hoje`; o que vencer mesmo assim é descartado (`include_closed` muda isso).
5. **Falha por instância é isolada:** bloqueio, HTTP ou formato inesperado numa instância não derruba as outras; os
   erros saem juntos no fim (status `partial`). Resposta que não é lista é erro explícito, nunca coleta vazia.
6. **Fonte nasce desabilitada e sem `robots_ok`** (termos de cada instância não conferidos), intervalo de 3 s.

## Consequências
+ Custo zero; 24 testes com fixtures **sintéticas** de 2 instâncias (uma com campos ricos, outra pobre).
− Instâncias, campos (`type`, `terms`, `ownerEntity`) e o filtro `GTE()` são suposições: o primeiro `make collect`
  real diz, e a resposta real vira fixture (P20). Instâncias municipais de Araraquara/São Carlos não foram achadas.
− Oportunidades de editais culturais "puros" (sem palavra-chave) são descartadas de propósito; a lista de
  palavras-chave é hipótese até a revisão de 10 itens.
