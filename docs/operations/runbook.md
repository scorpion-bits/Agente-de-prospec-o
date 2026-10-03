# Runbook — operar o radar (E16)

> Para quem nunca viu o projeto. Decisões: ADR-038 (agendamento/backup), ADR-010 (hospedagem), ADR-014 (repositório público: nada de dado pessoal em log).
> Os comandos `make` rodam **na sua máquina** (o Supabase não é acessível do ambiente do Claude).

## 1. O que roda sozinho

| Workflow | Quando | O que faz |
|---|---|---|
| `Pipeline` (`pipeline.yml`) | todo dia 09:00 UTC (06:00 BRT) | `migrate` → collect → extract → match → rescore; às **segundas**, digest por e-mail (se `DIGEST_EMAIL_TO` existir) |
| `Backup` (`backup.yml`) | domingo 08:00 UTC | `pg_dump` do schema `radar` criptografado com age → artefato `radar-backup-*` (30 dias) |
| `CI` | cada push/PR | `make check` |

Mesma cadeia à mão: `make pipeline` (`DRY=1` simula, `DIGEST=1` inclui digest).

## 2. Configurar uma vez (GitHub → Settings → Secrets and variables → Actions)

**Secrets obrigatórios:** `DATABASE_URL` (Session pooler do Supabase, porta 5432, com `?sslmode=require`; ver `supabase-setup.md`),
`DJANGO_SECRET_KEY` (qualquer string longa e aleatória). **Backup:** `BACKUP_AGE_PUBLIC_KEY` (chave pública `age1…`).
**Opcionais:** `GEMINI_API_KEY_FREE`, `GEMINI_API_KEY_PAID`, `ANTHROPIC_API_KEY`, `SERPER_API_KEY`/`BRAVE_API_KEY`, `COMPANY_CNPJ`, `CONTACT_EMAIL`,
`DIGEST_EMAIL_TO`, `DIGEST_EMAIL_FROM`, `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`. **Variables** (não secretas): `DIGEST_BASE_URL`, `SEARCH_PROVIDER`, `PG_CLIENT_VERSION`.
Sem IA/busca configuradas, a etapa correspondente falha ou não faz nada, e as outras seguem. **Nunca** cole segredos no chat ou no git.

Gerar o par de chaves do backup (na sua máquina; `age` instalado):

```bash
age-keygen -o ~/radar-backup.key      # a linha "Public key: age1…" vai no Secret BACKUP_AGE_PUBLIC_KEY
```

Guarde `~/radar-backup.key` em **dois** lugares seguros fora do repositório (gerenciador de senhas + pendrive). Sem ela o backup não abre.

## 3. Conferir que está rodando

1. Aba **Actions** → `Pipeline`: última execução verde? Rodar à mão: *Run workflow* (marque `dry_run` para só testar).
2. O digest tem a seção de fontes («última coleta há X dias»); se a coleta parou, aparece lá.
3. Execução vermelha: abra o log. Ele mostra a etapa e contagens (sem dados pessoais); o detalhe de erros de coleta está em Admin → Execuções de coleta.
4. O Actions manda e-mail de falha para quem fez o último commit no workflow; confirme as notificações do GitHub.

## 4. Problemas comuns

- **Agendamento parou** (`schedule` desliga após 60 dias sem atividade): Actions → `Pipeline` → *Enable workflow*. O próprio pipeline tenta renová-lo a cada execução agendada.
  Fallback: cron externo chamando `workflow_dispatch` (API do GitHub com token) ou `make pipeline` num cron local.
- **Supabase pausado** (Free pausa por inatividade): painel do Supabase → projeto → *Restore project*; depois rode o `Pipeline` à mão. O pipeline diário evita a pausa.
- **`DATABASE_URL` errada/expirada:** o passo de migrate falha; corrija o Secret. Senha trocada no Supabase → atualize o Secret e o `.env` local.
- **Cota da IA acabou:** a etapa `extract` falha ou pula; veja `make llm-usage`. As demais etapas seguem.
- **Trocar uma chave:** gere a nova no provedor, atualize o Secret (e o `.env` local), apague a antiga. Chave vazada: revogue primeiro.
- **Desabilitar uma fonte ruidosa:** Admin → Fontes → desmarque *Habilitada* (vale já na próxima rodada). Para pausar tudo: Actions → `Pipeline` → *Disable workflow*.

## 5. Backup e restauração

**Baixar e guardar uma cópia local** (o artefato some em 30 dias): Actions → `Backup` → execução → *Artifacts* → baixe `radar-backup-*` e guarde o `.dump.age` fora do GitHub.
Backup manual: `make backup` (precisa de `pg_dump` ≥ versão do servidor e `age`; lê `DATABASE_URL` e `BACKUP_AGE_PUBLIC_KEY` do `.env`; grava em `data/backups/`, ignorado pelo git).

**Restaurar** (teste primeiro no `radar-dev`, nunca direto no prod às cegas):

```bash
RESTORE_CONFIRM=sim bash scripts/restore_backup.sh ARQUIVO.dump.age ~/radar-backup.key "postgresql://…radar-dev…"
DATABASE_URL="postgresql://…radar-dev…" make migrate   # nada deve estar pendente
```

O script **apaga o schema `radar`** do banco alvo antes de restaurar. Depois confira no admin (organizações, oportunidades, interações) e rode `make rescore`.
Teste de restauração: repita a cada trimestre e anote a data em `docs/plan/STATUS.md`.

## 6. Verificar sem dados pessoais nos logs

Logs do Actions são públicos. Os comandos imprimem só contagens; se achar um nome, e-mail ou telefone num log, apague a execução (Actions → `…` → *Delete workflow run*) e abra um ajuste.
