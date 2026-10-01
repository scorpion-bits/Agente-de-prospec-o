# ADR-016 — Schema dedicado `radar` e conexão pelo pooler em modo sessão

- **Status:** aceito (detalha o item 4 do ADR-010)
- **Data:** 2026-10-01
- **Etapa:** E02

## Contexto
O Supabase expõe o schema `public` pela Data API (PostgREST) por padrão. O Radar guarda
contatos, interações e leads (LGPD) e só o Django deve acessar o banco. A conexão direta do
Supabase é IPv6; o GitHub Actions e muitas redes domésticas são só IPv4. O pooler em modo
transação não aceita prepared statements automáticos nem cursores do lado do servidor.

## Decisão
1. Todas as tabelas do Django ficam no schema **`radar`** (`DB_SCHEMA`, padrão `radar`), via
   `search_path=radar,public` nas opções da conexão. Como o schema não está na lista de
   schemas expostos do Supabase, a Data API não enxerga as tabelas.
2. O schema é criado por um handler de `pre_migrate` (`core.apps.ensure_schema`): vale para
   `migrate` normal e para o banco de testes, sem passo manual.
3. Conexão com o **pooler em modo sessão** (porta 5432 do host do pooler, IPv4). Configuração
   compatível com modo transação mesmo assim: `prepare_threshold=None` e
   `DISABLE_SERVER_SIDE_CURSORS=True`.
4. Sem `DATABASE_URL` ou (fora de DEBUG) sem `DJANGO_SECRET_KEY`, a aplicação **falha ao
   iniciar**, em vez de usar um padrão que aponte para o banco errado.

## Alternativas consideradas
| Alternativa | Por que não |
|---|---|
| Tabelas em `public` + `REVOKE` para `anon`/`authenticated` + RLS | Depende de lembrar de revogar a cada tabela nova; um deslize expõe dados |
| Desativar a Data API do projeto | Complementar, mas é configuração manual fora do código; o schema dedicado protege mesmo se alguém reativá-la |
| `search_path` por `ALTER ROLE` num papel dedicado | Funciona em qualquer modo do pooler; reavaliar se o modo transação for necessário |

## Consequências
+ Proteção por construção; testes cobrem que nada cai em `public`.
− `options=-c search_path=…` não é aceito em modo transação do pooler (usar sessão, ou `ALTER ROLE`).
− **Não foi possível testar contra o Supabase real** (projeto ainda não criado — P4); validado em PostgreSQL 16 local.

## Quando revisitar
Ao criar o `radar-dev` (conferir que a Data API não lista as tabelas e que o pooler aceita a conexão),
ou se precisarmos do modo transação.
