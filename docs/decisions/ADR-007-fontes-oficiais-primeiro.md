# ADR-007 — Fontes oficiais/abertas primeiro; sem scraping de LinkedIn/Google

- **Status:** aceito
- **Data:** 2026-09-30

## Contexto
Fontes variam em confiabilidade, custo e risco jurídico. Google Maps/LinkedIn têm os
dados "mais ricos", mas termos de uso proíbem raspagem e a Places API é cara acima da
cota gratuita e restringe armazenamento.

## Decisão
Ordem de preferência: (1) dados abertos oficiais e APIs públicas (INEP, IBGE, Receita,
PNCP, Querido Diário, Mapas Culturais); (2) APIs públicas de plataformas (Devpost,
itch.io); (3) páginas oficiais monitoradas (FAPESP, Sebrae, secretarias, prefeituras);
(4) site da própria organização; (5) API de busca (cota grátis) só para achar sites.
Proibido: raspar LinkedIn, Google Search/Maps, redes sociais; comprar listas de contatos.

## Consequências
+ Baixo risco, custo zero, dados com licença clara.
− Menos contatos pessoais e menos cobertura de pequenos comércios (aceitável: foco MVP é
escolas/SESC/editais).

## Quando revisitar
Se uma fonte paga específica mostrar ROI claro (ex.: base comercial CNPJ enriquecida) —
decidir em novo ADR com custo explícito.
