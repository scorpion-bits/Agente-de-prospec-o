# Hospedagem — análise (Vercel, Supabase e alternativas)

> Levantamento: 30/09/2026. Limites de free tier mudam; revalidar na E01b.
> Decisão resultante: **ADR-010**.

## Requisitos reais

| Requisito | Detalhe |
|---|---|
| Custo inicial ≈ zero | Sem servidor próprio no começo |
| Banco compartilhado | 1–3 pessoas vendo os mesmos dados |
| Jobs de coleta | 5–30 min/dia; Python (HTML/PDF/LLM); não cabem em funções de 10–60 s |
| UI interna | Django admin (ADR-001); acesso online **não** é obrigatório no MVP |
| Sem lock-in | Poder sair de qualquer provedor com `pg_dump` + container |
| Uso comercial | A ferramenta serve a uma empresa (MEI) → planos "somente pessoal" não servem |

## Fatos levantados

**Vercel**
- Plano Hobby (grátis) é **restrito a uso pessoal e não comercial**; uso comercial exige Pro
  (~US$ 20/membro/mês). Uma ferramenta interna da Scorpion Bits é uso comercial.
- Funções Python (Django via WSGI) são possíveis, mas stateless, com timeout curto no Hobby
  (10–60 s conforme a configuração) → inadequado para coleta/extração.
- Cron no Hobby: no máximo 1×/dia, horário com precisão de 1 h.
- Excelente para frontends Next.js — o que não temos no MVP.

**Supabase (plano Free)**
- PostgreSQL gerenciado (500 MB), Auth (50k MAU), Storage (1 GB), Edge Functions, 2 projetos
  ativos, egress de 5 GB. Uso comercial permitido.
- ⚠ Projeto **pausa após 7 dias sem requisições** (dados preservados; retomada manual).
- ⚠ **Sem backups** no Free (nem PITR) → precisamos de `pg_dump` próprio.
- ⚠ Conexão direta é IPv6; de ambientes só IPv4 (ex.: GitHub Actions) usar o **pooler
  Supavisor** (string de conexão do pooler).
- Edge Functions são Deno/TypeScript, com tempo limitado → não servem para o pipeline Python.
- A "Data API" (PostgREST) expõe o schema `public` automaticamente → como não a usamos,
  desativá-la ou usar schema dedicado (ver ADR-010).
- Pro: US$ 25/mês (backups diários, sem pausa).

**GitHub Actions**
- Repositórios públicos: minutos grátis. Privados (plano Free): 2.000 min/mês em runners Linux.
- Agendamento (`schedule`) + disparo manual (`workflow_dispatch`). Há relatos de que
  `schedule` não dispara em repositórios privados de contas gratuitas → **verificar na E01b**;
  alternativa: serviço externo gratuito (ex. cron-job.org) chamando `workflow_dispatch`, ou cron local.
- Jobs até 6 h; Python completo; segredos via GitHub Secrets.

**Google Cloud Run**
- Container qualquer (Django), escala a zero; free tier mensal ~2 milhões de requisições,
  180 mil vCPU-s, 360 mil GiB-s. Uso comercial permitido.
- Os **US$ 10/mês em créditos de Google Cloud do Google AI Pro** (após ativar os benefícios de
  desenvolvedor) cobrem sobras.

**Outros**: VPS pequena (US$ 5–10/mês, exige manutenção); Oracle Cloud Always Free (VM
generosa, mas operação e conta mais trabalhosas); Render/Railway (free tiers limitados/mutáveis).

## Comparação de arquiteturas

| Opção | Custo MVP | Prós | Contras | Veredito |
|---|---|---|---|---|
| **A. Vercel (Next.js) + Supabase (tudo)** | US$ 20+/mês (Vercel Pro por uso comercial) | Stack moderna; Auth pronto; bom para UI externa | Reescrever UI que o Django admin dá grátis; jobs Python não cabem em Vercel/Edge Functions; Hobby proibido | **Não agora.** Caminho futuro se houver UI para não-devs |
| **B. Supabase (Postgres) + workers Python no GitHub Actions + Django admin local** | **US$ 0** | Zero servidor; banco compartilhado; mesmo código local e agendado; sem lock-in (Postgres puro) | Admin só roda na máquina de quem tem o repo; pausa do Supabase se ninguém usar; backups por nossa conta | **Recomendado para o MVP** |
| C. B + Django no Cloud Run em `app.scorpionbits.com` | US$ 0–5 | UI online com domínio próprio; escala a zero | Configurar container, domínio, segurança | **Quando precisar de acesso online (E29)** |
| D. SQLite local (plano anterior) | US$ 0 | Simplicidade máxima | Não compartilha; não roda em workers agendados na nuvem; migração depois | Substituída por B |
| E. VPS com tudo | US$ 5–10 | Controle total | Manutenção, segurança, backup manuais | Só se B/C falharem |
| F. Django no Vercel (Python) | US$ 20+ (Pro) | Domínio fácil | Uso comercial exige Pro; funções curtas; cold start | Não |

## Arquitetura recomendada (evolutiva)

```text
MVP (US$ 0)                                   Depois (se/quando necessário)
─────────────                                 ──────────────────────────────
Máquina do dev ─ Django admin (local) ─┐      app.scorpionbits.com ─ Django no Cloud Run
                                       │                             (ou front Next.js no Vercel Pro
GitHub Actions (cron) ─ pipeline Python┼──►  Supabase PostgreSQL       + Supabase Auth, se houver
                                       │     (+ Storage p/ textos)      usuários não técnicos)
Backups: pg_dump semanal → artefato ───┘      Supabase Pro quando backups/sem-pausa forem necessários
```

O **contrato entre as partes é o schema PostgreSQL** (gerido pelas migrations do Django).
Qualquer frontend futuro (inclusive Next.js no Vercel) pode ler o mesmo banco sem tocar
nos workers → não ficamos presos.

## Fontes

- Vercel Hobby (não comercial): https://vercel.com/docs/plans/hobby ; https://zplatform.ai/guides/is-vercel-free/
- Vercel limites de funções/cron: https://vercel.com/docs/functions/limitations ; https://crontap.com/blog/vercel-cron-hourly-limit-and-how-to-beat-it ; https://kuberns.com/blogs/vercel-python/
- Supabase Free: https://uibakery.io/blog/supabase-pricing ; https://designrevision.com/blog/supabase-pricing
- Supabase IPv4/pooler: https://supabase.com/docs/guides/database/connecting-to-postgres ; https://supabase.com/docs/guides/troubleshooting/supabase--your-network-ipv4-and-ipv6-compatibility-cHe3BP
- GitHub Actions cobrança/agendamento: https://docs.github.com/en/actions/reference/usage-limits-billing-and-administration ; https://devactivity.com/insights/github-actions-cron-schedules-a-hidden-free-tier-hurdle-impacting-developer-productivity/
- Cloud Run: https://cloud.google.com/run/pricing
- Créditos Google AI Pro: https://blog.google/innovation-and-ai/technology/developers-tools/gdp-premium-ai-pro-ultra/
