# ADR-002 — SQLite no MVP, PostgreSQL no deploy compartilhado

- **Status:** substituído por ADR-010 (2026-09-30)
- **Data:** 2026-09-30

## Contexto
Volume esperado no MVP: milhares de registros; 1 processo escrevendo por vez (cron) e
1–3 pessoas usando o admin. Custo de infraestrutura deve ser zero.

## Decisão
SQLite em modo WAL no MVP (arquivo em `data/`), backup por cópia diária do arquivo.
Migrar para PostgreSQL quando houver deploy compartilhado (E29) ou importação de CNPJ
de muitas regiões. Evitar recursos específicos de SQLite/Postgres no código (usar ORM;
`JSONField` é suportado por ambos).

## Alternativas consideradas
| Alternativa | Por que não agora |
|---|---|
| PostgreSQL desde o início | Exige servidor/instância; sem ganho para o volume do MVP |
| DuckDB | Excelente para análise (pode ser usado pontualmente no filtro do CNPJ), mas não para app transacional com admin |
| Supabase/Neon free tier | Dependência externa, latência, limites de free tier; desnecessário local |

## Consequências
+ Zero custo e zero operação. + Testes rápidos.
− Concorrência de escrita limitada (aceitável). − Migração futura exige `dumpdata/loaddata` ou script.

## Quando revisitar
Deploy em servidor com acesso de várias pessoas, base > 1 GB, ou jobs concorrentes.
