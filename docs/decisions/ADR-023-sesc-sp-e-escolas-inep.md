# ADR-023 — Rede SESC-SP (CSV curado) e escolas do INEP (dataset local)

- **Status:** aceito
- **Data:** 2026-10-01
- **Etapa:** E17

## Contexto
A E17 cria a base de organizações-alvo: unidades do SESC-SP e escolas privadas da região. O ambiente de
desenvolvimento não alcança o gov.br/INEP nem o sescsp.org.br (E01 pendente), então nenhum dado real foi
conferido na fonte durante a etapa. As unidades SESC já contatadas (E03b) não podem ser duplicadas.

## Decisão
1. **SESC-SP = CSV curado** (`data/seeds/sesc_sp.csv`, conector `sesc-sp-unidades`): só nome, município,
   UF e `curated_at`; sem contatos de pessoas (ADR-014). Sem `source_url` a evidência é **manual**
   (`human`), nunca "observada" (ADR-004). A lista foi escrita de memória, **não conferida** contra
   sescsp.org.br: conferir e completar na E01 (colunas `website`/`source_url` existem para isso).
2. **Hierarquia:** cada unidade é filha de uma organização "SESC-SP" (`parent`), criada pelo upsert quando
   falta. `fields["parent_name"]` do candidato é genérico e serve a qualquer rede (E17b). Uma mãe já
   definida nunca é trocada.
3. **Memória comercial:** o dedupe existente (nome + município + rede) reconhece as unidades de E03b; nada
   é sobrescrito, só completado. `inep_code` entrou em `FILLABLE_FIELDS`: escola cadastrada à mão recebe o
   código INEP em vez de ser duplicada.
4. **INEP = dataset de arquivo local** (`inep-escolas`): o humano baixa o CSV do Catálogo de Escolas para
   `data/inep/` (ignorado pelo git) e roda `collect`. `dataset` com `config.path` e sem `config.url` não usa
   rede (não exige `robots_ok`). Com `url` segue pelo `PoliteFetcher`. Nasce **desabilitada**.
5. **Colunas por nome**, com aliases do catálogo e dos microdados; coluna obrigatória ausente = erro e nada
   importado. Os nomes de coluna vêm de conhecimento do layout, **não de um arquivo real**: ajustar
   `COLUMNS` na primeira execução.
6. **Escopo:** privadas (`Privada`/`4`) e ativas (sem coluna de situação não dá para filtrar: aceita);
   municípios até `max_km` (padrão `GEO_REGIONAL_KM` = 150) **mais** os polos prioritários, ou lista
   explícita `municipalities`. O filtro roda no `fetch`, para `items_seen` contar só o que interessa.
7. **Telefone e endereço** do INEP são telefone/endereço institucional da escola: ficam como `Evidence`
   (e `address` na organização), no banco, nunca no repositório.

## Consequências
+ Zero custo, sem IA, sem rede no caso padrão; idempotente por `inep_code`.
+ Trocar de ano do Censo = baixar outro arquivo.
− Lista SESC e layout do INEP precisam de conferência humana (pendência P11).
− `Organization` SESC-SP "mãe" aparece junto das unidades em listas por `kind=sesc`; filtre por `parent`.
