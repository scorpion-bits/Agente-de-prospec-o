# ADR-043 — Empresas do CNPJ aberto: arquivo local, filtro por CNAE e região, sem dado pessoal

- **Status:** aceito
- **Data:** 2026-10-04
- **Etapa:** E25

## Contexto
A E25 pede uma base de empresas ativas da região por CNAE mapeado a serviços. O sandbox do Claude não alcança a Receita:
o layout (30 colunas), o código de município e os CNAEs vêm do conhecimento do formato público e do estudo do
repositório de referência (`notes/analise-zenonpb-agente-prospeccao.md`, MIT; **nenhum código copiado**), não de um arquivo real.
O repositório é público (ADR-014) e os dados de MEI são de pessoa física (LGPD).

## Decisão
1. **Conector `cnpj-estabelecimentos`** (`collection/connectors/cnpj_estabelecimentos.py`, tipo `dataset`, sem IA e sem rede):
   lê `EstabelecimentosN.zip`/`.csv` **locais** (baixados à mão, ~1 GB cada) em streaming, sem cabeçalho, por posição de coluna
   (`COL`), Latin-1. Linha curta, CNPJ inválido (aceita o alfanumérico, `is_valid_cnpj`) ou baixada/inapta é descartada.
2. **Região:** o município da Receita é o código Tom/SRF; a tabela `Municipios` (`data/cnpj/Municipios.csv`) dá o nome, que casa com
   o escopo da E17 (`max_km` ou `municipalities`) por nome + UF. Sem a tabela, erro claro (nada importado).
3. **CNAE → serviço é dado:** `data/seeds/cnae_services.csv` (cnae, grupo, segmento, serviços). Padrão: marketing, cursos, editoras
   e eventos; o grupo `web` (varejo/serviços locais) fica fora por volume e é ligado em `config.groups`.
4. **Minimização (LGPD):** só entra quem tem **nome fantasia** (a razão social do MEI é nome de pessoa). Não guardamos e-mail,
   telefone, endereço de rua nem sócios; só CNPJ, nome, CNAE, município/UF e data de início. Sem `ContactPoint`.
5. **Evidência (ADR-004):** campos da Receita são `observed`; a sugestão de serviço pelo CNAE é `inferred`
   (`rule:cnae_services`, com o CNAE no trecho). Dedupe por CNPJ (E04); nunca recria quem já é conhecido.
6. **Fonte nasce desabilitada**; `make collect` a roda quando habilitada (P31). Sem migration.

## Consequências
+ Custo zero; 14 testes com fixture sintética (ZIP e CSV); organizações entram para E18/E26 acharem site e sinais.
− Layout, código Tom e CNAEs são suposições até o P31; mudou o layout → zero resultados ou erro, ajustar `COL`/CSV.
− Sem a razão social, empresas sem nome fantasia ficam de fora (perda aceita). Dados cadastrais podem estar desatualizados.
− Tempo sobre ~10 GB não medido (meta da E25: < 30 min).
