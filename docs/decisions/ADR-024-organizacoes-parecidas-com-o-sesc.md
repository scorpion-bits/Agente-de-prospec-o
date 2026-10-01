# ADR-024 — Organizações parecidas com o SESC (CSV curado + vocabulário de tags)

- **Status:** aceito
- **Data:** 2026-10-01
- **Etapa:** E17b

## Contexto
O SESC é hipótese validada (ADR-012). A E17b amplia a base com instituições de perfil de compra parecido
(educação não formal/cultural, oficineiros externos, unidades na região). Como na E17, o ambiente não
alcança nenhum site oficial: nada foi conferido na fonte.

## Decisão
1. **Seed curada** `data/seeds/similar_orgs.csv` + conector `orgs-parecidas-sesc`
   (`collection/connectors/similar_orgs.py`, estende `seed_csv`), fonte habilitada por `make seed`.
   Cobre os 4 polos: SENAC, SESI, SENAI, Fatec, IFSP, prefeituras (Cultura e Educação), UNESP/UFSCar/USP e o
   CDCC-USP; mais as Oficinas Culturais como rede. Só instituições, nunca pessoas (ADR-014).
2. **Vocabulário fechado de tags** (`core/services/similarity.py`): tag desconhecida reprova a linha. Elas
   alimentam o filtro «parecida com o SESC» do admin e o perfil `lead.sesc`. `baixa_prioridade` marca quem
   não tem contratação externa conhecida (hipótese de curadoria, editável no admin).
3. **Tags somam, nunca removem**: numa organização já conhecida (inclusive contatada, ADR-012) o upsert só
   acrescenta tags; as postas à mão ficam.
4. **URL oficial por rede**: o dedupe por domínio (ADR-020) fundiria unidades com o mesmo `website`; por
   isso o site fica na organização-mãe (rede, prefeitura, universidade) e as unidades herdam via `parent`.
   Sem `source_url` a evidência é **manual** (`human`), nunca observada (ADR-004).
5. **Sem `html_watch`**: o conector de páginas monitoradas é a E07; as páginas de chamamento entram lá.

## Consequências
+ Zero custo, sem IA e sem rede; idempotente; filtro no admin.
− **Lista e URLs escritas de memória, não conferidas** (pode haver unidade faltando/sobrando ou URL mudada):
  conferir na E01. Municípios fora dos 4 polos (Matão, IFSP) vieram só por proximidade.
− Mães sem município (rede/prefeitura/universidade) aparecem junto das unidades: filtre por `parent`.
