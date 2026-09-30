# Relevância geográfica contextual

## Problema

Distância importa muito para um curso presencial em escola e nada para um hackathon
online. Uma regra fixa ("priorize até 50 km") estaria errada para metade dos casos.

## Solução: perfis geográficos

A relevância geográfica `G ∈ [0,1]` é calculada por um **perfil** escolhido de acordo com
o tipo de item (e, para leads, o serviço do match). O perfil combina:

1. **Elegibilidade territorial (gate)** — se a oportunidade restringe participantes a uma
   região e Araraquara/SP não está nela → item é *gated* ("inelegível: só RJ").
2. **Decaimento por distância** — só para modalidades presenciais.
3. **Bônus de abrangência** — para editais: municipal de Araraquara > regional > estadual SP > federal.

## Base de localização

- Base configurável em settings: `HOME_MUNICIPALITY_IBGE = 3503208` (Araraquara/SP —
  código a confirmar na carga IBGE da E12).
- Distância: haversine entre centróides municipais (IBGE). Precisão de município basta.
- **Localização é fator de priorização, nunca filtro absoluto.** Única exceção: gate de
  elegibilidade territorial explícita de uma oportunidade. Leads de software, sites, jogos e
  aplicações são avaliados em qualquer lugar do Brasil. (O que é limitado por região é o
  **escopo de coleta** de bases grandes — ex. escolas do INEP —, por volume, e é configurável.)
- **Polos prioritários** (configuráveis, com relevância comercial já comprovada — propostas
  SESC enviadas): **Araraquara, São Carlos, Ribeirão Preto, Bauru**. Um polo conta como R1
  mesmo estando a ~100 km (Bauru).
- Anéis de referência (usados em explicações e filtros):
  - **R0** Araraquara
  - **R1** Polos prioritários + vizinhas de Araraquara (≈ até 40 km: Américo Brasiliense,
    Matão, Gavião Peixoto, Santa Lúcia, Boa Esperança do Sul…)
  - **R2** Interior próximo (≈ até 150 km: Jaú, Bebedouro, Rio Claro, Limeira, Franca…)
  - **R3** Estado de SP (inclui capital)
  - **R4** Brasil
  - **R5** Internacional
- Distâncias aproximadas em linha reta de Araraquara: São Carlos ~40 km, Ribeirão Preto
  ~80 km, Bauru ~100 km (confirmar na E12 com centróides do IBGE).

## Perfis iniciais (valores calibráveis — guardados como dados/config, não código fixo)

| Perfil | Aplica a | Função de G |
|---|---|---|
| `onsite_recurring` | Cursos/oficinas presenciais recorrentes (escolas, SESC) | R0/R1 1,0; R2 linear de 0,8 (40 km) a 0,3 (150 km); R3 0,15; além 0,05 (cursos intensivos pontuais ainda possíveis) |
| `onsite_event` | Game jam/hackathon/evento presencial | R0/R1 1,0; R2 0,7; SP capital 0,5; resto de SP 0,3; resto do Brasil 0,1 |
| `online` | Hackathon/jam online, chamadas remotas | 1,0 sempre |
| `edital_scope` | Editais/programas | gate por elegibilidade; depois: municipal Araraquara ou polo 1,0 · regional 0,9 · estadual SP 0,8 · federal 0,7 · internacional 0,4 |
| `remote_service` | Software, web, jogos sob encomenda, aplicações | 0,85 base em qualquer lugar do Brasil + 0,15 se R0–R2 (proximidade ajuda confiança e reunião presencial); internacional 0,6 |

## Explicação gerada

Cada cálculo devolve texto para o breakdown, ex.:
- "Presencial em Bauru (polo prioritário, R1) — perfil `onsite_recurring`: 1,0"
- "Presencial em Jaú (≈ 70 km, R2) — perfil `onsite_recurring`: 0,66"
- "Site institucional para empresa em Recife — perfil `remote_service`: 0,85"
- "Edital estadual SP, aceita proponentes de Araraquara — 0,8"
- "Online — distância irrelevante: 1,0"
- "GATE: edital restrito a proponentes do Rio de Janeiro"

## Dados ausentes

Localização desconhecida → `G = 0,5` e fator de confiança reduzido (ver `scoring.md`),
com explicação "localização não identificada". Nunca chutar localização.
