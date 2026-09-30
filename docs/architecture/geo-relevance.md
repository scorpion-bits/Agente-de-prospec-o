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
- Anéis de referência (usados em explicações e filtros):
  - **R0** Araraquara
  - **R1** Região imediata/vizinhas (≈ até 40 km: Américo Brasiliense, Matão, Gavião
    Peixoto, Santa Lúcia, Boa Esperança do Sul…)
  - **R2** Região intermediária (≈ até 120 km: São Carlos, Ribeirão Preto, Jaú,
    Bebedouro, Rio Claro…)
  - **R3** Estado de SP
  - **R4** Brasil
  - **R5** Internacional

## Perfis iniciais (valores calibráveis — guardados como dados/config, não código fixo)

| Perfil | Aplica a | Função de G |
|---|---|---|
| `onsite_recurring` | Cursos/oficinas presenciais recorrentes (escolas, SESC) | 1,0 até 30 km; linear até 0,3 em 120 km; 0,05 além (cursos intensivos pontuais ainda possíveis) |
| `onsite_event` | Game jam/hackathon/evento presencial | 1,0 até 50 km; 0,6 até 150 km; 0,3 em SP capital/estado; 0,1 resto do Brasil |
| `online` | Hackathon/jam online, chamadas remotas | 1,0 sempre |
| `edital_scope` | Editais/programas | gate por elegibilidade; depois: municipal Araraquara 1,0 · regional 0,9 · estadual SP 0,8 · federal 0,7 · internacional 0,4 |
| `remote_service` | Software, web, jogos sob encomenda | 0,8 base + 0,2 se R0–R2 (proximidade ajuda confiança e reunião presencial) |

## Explicação gerada

Cada cálculo devolve texto para o breakdown, ex.:
- "Presencial em São Carlos (38 km, R2) — perfil `onsite_recurring`: 0,93"
- "Edital estadual SP, aceita proponentes de Araraquara — 0,8"
- "Online — distância irrelevante: 1,0"
- "GATE: edital restrito a proponentes do Rio de Janeiro"

## Dados ausentes

Localização desconhecida → `G = 0,5` e fator de confiança reduzido (ver `scoring.md`),
com explicação "localização não identificada". Nunca chutar localização.
