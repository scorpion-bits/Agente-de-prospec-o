# ADR-029 — Conector itch.io (listagem HTML) e medição de tempo no fetcher

- **Status:** aceito
- **Data:** 2026-10-01
- **Etapa:** E06

## Contexto
O itch.io não tem API de jams e o ambiente do Claude não o alcança (E01 pendente): o HTML da listagem vem de memória.
Separadamente, a primeira coleta real do Devpost (E05) funcionou (45 hackathons vistos, 21 novos), mas cada página
levou 2–3 min e o processo não terminou sozinho depois de «concluída».

## Decisão
1. **Conector `itch-jams`** (`collection/connectors/itch_jams.py`, sem IA): lê `/jams/upcoming` e `/jams/in-progress`
   (até `max_listing_pages`, `?page=N`) pelo `PoliteFetcher`; uma célula `jam_cell` = uma jam. Página sem nenhuma célula
   na primeira página = erro «Resposta inesperada» (layout mudou), nunca coleta vazia silenciosa.
2. **Datas:** `YYYY-MM-DD HH:MM:SS` do atributo `title` (supomos UTC). Duas datas = início e fim; uma data = início em
   «em breve» e fim em «em andamento»; qualquer outra forma deixa em branco (ADR-004). Jam já encerrada é ignorada.
3. **Filtro** (plano E06, em `Source.config`): descarta jam com início e fim lidos e menos de `min_duration_hours` (48);
   exige `min_joined` (20) inscritos **ou** palavra-chave no título (Brasil, educação, escola, Godot…).
4. **Fonte nasce desabilitada e sem `robots_ok`** (como o Devpost): termos de uso não confirmados (P17).
5. **Demora do Devpost — causa não reproduzida** (devpost.com é inalcançável daqui). Hipóteses: (a) `Retry-After`/backoff
   somando minutos; (b) o runner é preguiçoso: o tempo de **gravar** cada item num Supabase remoto cai entre uma página e
   a próxima, parecendo demora da busca; (c) conexão com o banco aberta ao sair. Em vez de chutar a causa:
   - `PoliteFetcher` ganhou **prazo total por requisição** (`max_seconds`, 90 s; estoura → `FetchError`) e `stats`
     (páginas, requisições HTTP, retries, segundos de rede × espera); timeout de conexão de 10 s.
   - `run_source` mede o tempo dentro do conector (busca) × o resto (gravação); o `collect` imprime a linha
     `tempo — … busca X s, gravação Y s; … rede …, espera …` (só números: log do Actions é público).
   - `collect` fecha as conexões com o banco antes de sair.
   O humano roda de novo e a linha diz se o gargalo é rede, espera ou banco (P16).

## Consequências
+ Custo zero; 28 testes do conector com fixture **sintética** (`tests/fixtures/itch_jams/`) e 2 do fetcher.
− Seletores do HTML (`jam_cell`, `date_countdown`, «N joined») são suposições: se o layout real diferir, o erro aparece
  na primeira coleta e a fixture real vira teste (P17).
− O prazo de 90 s pode cortar uma fonte realmente lenta; ajustar `max_seconds` se a medição mostrar que é legítimo.
