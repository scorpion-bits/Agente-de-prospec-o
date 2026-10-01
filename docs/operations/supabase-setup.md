# Aplicar o banco no Supabase (passo a passo para o titular)

> Por quê: a rede do ambiente do Claude bloqueia `*.supabase.co`, então quem cria as tabelas no
> Supabase é **você**, na sua máquina. O Claude só gera os arquivos (migrations). Decisão e
> contexto: ADR-010, ADR-016. **Nunca cole a senha nem a `DATABASE_URL` no chat ou no git.**

## 1. Pegar a string de conexão

No painel do Supabase, no projeto: botão **Connect** → **Session pooler** (porta **5432**).
Use essa, e **não** a "Direct connection" (é IPv6) nem o "Transaction pooler" (porta 6543).
Ela tem esta forma (troque `SENHA` pela senha do banco):

```text
postgresql://postgres.<ref-do-projeto>:SENHA@aws-0-<regiao>.pooler.supabase.com:5432/postgres?sslmode=require
```

## 2. Configurar e aplicar (na pasta do projeto)

Com `make` (Linux, macOS ou Windows com WSL):

```bash
make setup          # instala dependências e cria o .env a partir do .env.example
# edite o .env: DATABASE_URL=<a string do passo 1>   (e deixe DB_SCHEMA=radar)
make migrate        # cria o schema "radar" e as tabelas
make seed           # catálogo de 12 serviços (não sobrescreve edições)
make superuser      # cria o seu usuário do admin
make run            # http://127.0.0.1:8000/admin/
```

Windows sem `make`: os mesmos passos, direto (PowerShell, com o [uv](https://docs.astral.sh/uv/) instalado):

```powershell
uv sync
Copy-Item .env.example .env       # depois edite o .env como acima
uv run python manage.py migrate
uv run python manage.py load_services
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

O `.env` é ignorado pelo git. Em produção/CI a `DATABASE_URL` vai em **secrets**, nunca no código.

## 3. Conferir (SQL Editor do Supabase)

```sql
-- 1) Tabelas por schema. Esperado: "radar" com 19 tabelas (9 do núcleo + Django); "public" sem as do app.
select table_schema, count(*) from information_schema.tables
where table_schema in ('radar', 'public') group by 1 order by 1;

-- 2) Nada do app em public. Esperado: 0 linhas.
select table_name from information_schema.tables
where table_schema = 'public'
  and (table_name like 'core\_%' or table_name like 'django\_%' or table_name like 'auth\_%');

-- 3) Papéis da Data API sem acesso ao schema. Esperado: false | false.
select has_schema_privilege('anon', 'radar', 'USAGE') as anon,
       has_schema_privilege('authenticated', 'radar', 'USAGE') as authenticated;
```

E no painel: configurações do projeto → **API / Data API** → o schema `radar` **não** pode estar
na lista de schemas expostos. (Pode ficar desativada de vez, se você não usa.)

## Se der erro

| Sintoma | Causa provável |
|---|---|
| `could not translate host name` / `Network is unreachable` | usou a conexão **direta** (IPv6); use a do **Session pooler** |
| `unsupported startup parameter: options` | usou a porta 6543 (modo transação); use a **5432** |
| `password authentication failed` | senha errada (no painel: Database → Reset password) |
| `permission denied for database` | usuário diferente de `postgres.<ref>` |
| `Defina DJANGO_SECRET_KEY…` | falta `DJANGO_DEBUG=true` no `.env` local (ou uma chave, fora do local) |

Se falhar, mande ao Claude **só a mensagem de erro, sem a senha**.
Depois de aplicar, avise para o Claude registrar o P4 como concluído no `STATUS.md`.
