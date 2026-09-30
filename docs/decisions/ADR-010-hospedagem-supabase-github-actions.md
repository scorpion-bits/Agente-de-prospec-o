# ADR-010 — Hospedagem: Supabase (PostgreSQL) + workers no GitHub Actions + admin local

- **Status:** aceito (substitui ADR-002)
- **Data:** 2026-09-30
- **Etapa:** E00 (complemento)

## Contexto
A empresa pode hospedar na internet e considerou Vercel + Supabase. Restrições: quase zero
de custo, sem servidor próprio no início, sem lock-in, uso comercial (a ferramenta serve à
Scorpion Bits, agora um MEI). Análise completa em `docs/research/hosting.md`.

## Decisão
1. **Banco: PostgreSQL no Supabase (Free) desde o início**, acessado só pelo Django
   (`DATABASE_URL` via pooler Supavisor para compatibilidade IPv4). Dois projetos Free:
   `radar-dev` e `radar-prod`. Nada de recurso específico do Supabase no código de domínio.
2. **Workers: o mesmo pipeline Python roda agendado no GitHub Actions** (diário +
   disparo manual), com segredos no GitHub Secrets. Alternativa: cron local.
3. **UI no MVP: Django admin rodando localmente** na máquina de cada pessoa, apontando para o
   banco compartilhado. Sem exposição pública.
4. **Segurança do Supabase**: desativar a Data API (PostgREST) ou manter as tabelas fora do
   schema exposto (schema dedicado `radar`); conexão com usuário próprio; RLS explícito se um
   dia um frontend usar o cliente Supabase.
5. **Backups próprios**: `pg_dump` semanal pelo GitHub Actions (artefato com retenção) +
   cópia local periódica. Restauração testada na E16.
6. **Documentos brutos** não ficam no banco (limite 500 MB): guardamos URL, hash, ETag e o
   texto extraído comprimido (Supabase Storage ou coluna comprimida), com retenção.
7. **Vercel fica fora do MVP**: Hobby proíbe uso comercial e as funções não suportam os jobs.
   UI online (E29) → Django no **Google Cloud Run** em `app.scorpionbits.com`
   (ou `prospeccao.scorpionbits.com`), coberto pelo free tier/créditos do Google AI Pro.
   Vercel Pro + Next.js + Supabase Auth só se surgir necessidade de UI para não-desenvolvedores.

## Alternativas consideradas
Ver tabela em `docs/research/hosting.md` (Vercel+Supabase completo, SQLite local, VPS,
Django no Vercel).

## Consequências
+ US$ 0 no MVP; banco compartilhado desde o dia 1; sem SQLite→Postgres depois.
+ Sem lock-in: Postgres puro + container; qualquer frontend futuro lê o mesmo schema.
− Pausa do Supabase após 7 dias sem uso (o pipeline diário a evita; antes da E16, retomar manualmente).
− Sem backups no Free → responsabilidade nossa.
− Admin local exige ambiente Python em cada máquina (aceitável: usuários são desenvolvedores).
− Testes: CI usa PostgreSQL em container; localmente SQLite é aceito só para rapidez.

## Quando revisitar
- Pessoa não técnica precisa usar → UI online (E29).
- Dados > 400 MB, necessidade de backup gerenciado ou clientes dependendo do sistema → Supabase Pro (US$ 25/mês).
- `schedule` do GitHub Actions indisponível no repositório → cron externo/local.
