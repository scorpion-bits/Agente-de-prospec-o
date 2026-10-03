# ADR-038 — Agendamento no Actions e backups criptografados

- **Status:** aceito
- **Data:** 2026-10-03

## Contexto
O radar precisa rodar sozinho, sem servidor (ADR-010), e ser recuperável. O repositório é público (ADR-014): logs e artefatos do
Actions podem ser lidos por qualquer pessoa. O banco (Supabase Free) pausa por inatividade e o `schedule` do Actions desliga após 60 dias sem atividade.

## Decisão
1. **`manage.py run_pipeline`** (`make pipeline`) encadeia `collect --all → extract_opportunities → match_services → rescore`
   (+ `digest` com `--digest`). Cada etapa tem falha isolada: as seguintes ainda rodam e o comando termina com erro no fim (Actions vermelho).
   O log traz só contagens; erro inesperado mostra só o tipo da exceção (a conexão pode vazar host/usuário). `--dry-run` simula e **pula o digest** (imprimiria dados privados).
   O app `radar` entrou em `INSTALLED_APPS` só para hospedar o comando (sem modelos).
2. **`pipeline.yml`**: `schedule` diário (09:00 UTC) + `workflow_dispatch` (`dry_run`, `digest`). Roda `migrate` antes (o titular não precisa lembrar).
   Segredos só em Secrets (`DATABASE_URL`, `DJANGO_SECRET_KEY`, chaves de IA/busca, SMTP). O digest só vai por e-mail, às segundas, e só se `DIGEST_EMAIL_TO`
   existir: **nada de digest como artefato** (follow-ups são privados, e artefato de repositório público é baixável). Um passo final renova o agendamento
   (`gh api …/enable`), mitigando o desligamento de 60 dias; o pipeline diário também mantém o Supabase Free ativo.
3. **`backup.yml`** semanal (domingo): `scripts/backup.sh` faz `pg_dump --schema=radar -Fc` **direto para `age`** (nunca há dump em claro em disco) com a chave
   **pública** `BACKUP_AGE_PUBLIC_KEY`; só o `.dump.age` vira artefato (retenção 30 dias). A chave privada fica só com o titular (P6). O cliente `pg_dump` é instalado do
   PGDG na versão `PG_CLIENT_VERSION` (padrão 17; precisa ser ≥ a do servidor Supabase).
4. **Restauração**: `scripts/restore_backup.sh` (`DROP SCHEMA` + `pg_restore`), com confirmação `RESTORE_CONFIRM=sim`. Testada localmente (PostgreSQL 16: dump → age → restore →
   12 serviços iguais e `migrate --check` limpo); **ainda não testada no radar-dev do Supabase** (P26).
5. Fallback se o `schedule` falhar: cron externo chamando `workflow_dispatch` ou `make pipeline` num cron local (runbook).

## Consequências
- Sem digest no Actions sem e-mail configurado: sem destinatários o digest simplesmente não roda lá (continua `make digest` local).
- Backup de 30 dias no GitHub não substitui cópia local: o runbook manda baixar e guardar o `.dump.age` fora (P26).
- `extract` consome cota do Gemini free a cada rodada diária (limite `--extract-limit`, padrão 30, e o teto de orçamento da `llm/`).
