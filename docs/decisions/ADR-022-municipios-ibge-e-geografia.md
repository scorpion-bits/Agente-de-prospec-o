# ADR-022 — Municípios do IBGE, texto × FK e perfis geográficos

- **Status:** aceito
- **Data:** 2026-10-01
- **Etapa:** E12

## Contexto
A E12 pede uma tabela de municípios com coordenadas, polos configuráveis e a função de relevância
geográfica. O ambiente de desenvolvimento **não alcança** `servicodados.ibge.gov.br` nem
`geoftp.ibge.gov.br` (só o GitHub raw), e `Organization`/`Opportunity` já guardam o município como
texto (`municipality_name` + `uf`) desde a E03, usado por seeds, importações e conectores.

## Decisão
1. **Fonte dos dados:** `data/seeds/municipios.csv` (5.571 linhas: os 5.570 municípios + o Distrito
   Federal), derivado do conjunto público `kelvins/municipios-brasileiros` (códigos IBGE de 7 dígitos;
   coordenada = **sede** do município, não o centróide da área; precisão de município basta, ver
   `geo-relevance.md`). Não deu para baixar do IBGE daqui: **conferir contra o IBGE** quando houver acesso
   (E01) é uma pendência. `load_municipalities <arquivo>` aceita qualquer CSV no mesmo formato, então
   trocar a fonte é só trocar o arquivo.
2. **Texto + FK, não troca:** `municipality_name`/`uf` continuam guardando o que a fonte disse;
   `municipality` (FK nova, nula) é a versão resolvida. Resolve-se ao salvar (nome normalizado + UF;
   sem UF só nomes únicos no país; homônimo ambíguo fica sem município, **nunca chuta**) e em lote por
   `resolve_municipalities`. Uma escolha manual da FK vale enquanto combinar com o texto.
3. **Perfis como dados:** `scoring/geo.py::PROFILES` guarda os valores; base, polos e raios vêm de
   settings (`HOME_MUNICIPALITY_IBGE`, `PRIORITY_HUBS_IBGE`, `GEO_NEAR_KM`, `GEO_REGIONAL_KM`).
4. **Anéis por distância, não por UF:** R0 base; R1 polo ou ≤ 40 km; R2 ≤ 150 km (inclusive em outro
   estado); R3 resto do estado da base; R4 resto do Brasil; R5 exterior.
5. **Gate só explícito:** `edital_scope` retorna `gated` apenas se `eligible_regions` não cobre a base
   (UF, município, `Nome/UF`, região do IBGE ou "Brasil"). Edital municipal fora dos polos pesa a
   distância como evento presencial (decisão minha; o doc só definia o caso do polo).
6. **Dado ausente:** localização desconhecida → `G = 0,5`, `location_known=False` (o E13 reduz a
   confiança); `online` ignora localização.

## Consequências
+ Distâncias medidas, não estimadas: **Bauru fica a ≈ 111 km** de Araraquara (o doc estimava ~100;
  `geo-relevance.md` foi corrigido). São Carlos ≈ 40 km e Ribeirão Preto ≈ 80 km confirmados.
+ Nenhuma coluna ou seed existente quebrou.
− Coordenadas de sede podem diferir alguns km do centróide oficial; irrelevante nos anéis usados.
− Dois campos de município (texto e FK) a manter; o texto é a prova, a FK é para cálculo.
