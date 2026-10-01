# Radar Scorpion Bits

Plataforma interna da **Scorpion Bits** para descobrir, qualificar e priorizar
oportunidades comerciais (escolas, SESCs, empresas, instituições) e institucionais
(editais, hackathons, game jams, programas de aceleração).

> Estado: modelo de dados núcleo e admin prontos (E03); veja `docs/plan/STATUS.md` para a próxima etapa.

## Por onde começar

- **Humanos:** `docs/product/vision.md` → `docs/product/mvp.md` → `docs/plan/PLAN.md`
- **Claude Code:** `CLAUDE.md` (ritual de início de sessão)
- **Mapa da documentação:** `docs/README.md`

## Princípios

1. Encontrar oportunidades reais → economizar tempo → gerar receita.
2. IA só quando código simples não resolve. Custo mensal alvo do MVP: **US$ 0–10**.
3. Toda informação com fonte rastreável; fato ≠ inferência.
4. Humano decide e faz o contato. Nada de spam.

## Como rodar (desenvolvimento)

Requisitos: [uv](https://docs.astral.sh/uv/) (instala o Python 3.12 sozinho) e um PostgreSQL.

```bash
make setup            # instala dependências e cria o .env a partir do .env.example
docker compose up -d  # PostgreSQL local (ou use o projeto Supabase radar-dev: ver .env.example)
make migrate          # cria o schema "radar" e as tabelas
make seed             # catálogo inicial de serviços (não sobrescreve o que você editar no admin)
make memory           # perfil da empresa, portfólio e histórico comercial (CNPJ via COMPANY_CNPJ no .env)
make superuser        # usuário do admin
make run              # http://127.0.0.1:8000/admin/
make check            # lint + testes + verificações (o mesmo que o CI roda)
```

`make help` lista todos os comandos. Os testes precisam de `DATABASE_URL` apontando para um
PostgreSQL (nunca para o banco de produção: o pytest cria e apaga um banco `test_*`).

Aplicar no **Supabase** (e rodar no Windows sem `make`): `docs/operations/supabase-setup.md`.

## Regras do repositório público

Nunca commitar CNPJ, endereço, e-mails/telefones/nomes de contatos, interações, digests,
dumps ou chaves (ADR-014). `make docs-check` procura esses padrões. Dados privados ficam em
`.env`, no banco ou em `data/private/` (ignorado).
