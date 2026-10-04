# ADR-046 — Hospedagem do admin: Cloud Run, banco no Supabase, deploy manual

- **Status:** aceito
- **Data:** 2026-10-04

## Contexto
O admin só rodava em `localhost` (ADR-010). O titular usa **mais de um computador** e, em breve, outras pessoas da equipe: o admin precisa
estar online. A E29 do plano previa Django no Cloud Run; ela estava parada esperando o go/no-go (E22), mas hospedar o que já existe
(admin + banco) não depende dele. O repositório é **público** (ADR-014) e o admin mostra dados comerciais e contatos (LGPD).

## Decisão
1. **Google Cloud Run** (como no plano, ADR-010): escala a zero, free tier mensal e créditos do Google AI Pro cobrem o uso interno
   (US$ 0–5). Banco continua no Supabase (pooler em modo sessão). Nada de segredo no repositório: `DJANGO_SECRET_KEY` e `DATABASE_URL`
   ficam no **Secret Manager**; o resto são variáveis de ambiente do serviço.
2. **Alternativas descartadas por não serem claramente mais simples ou baratas:** Render/Railway/Fly (free tiers mutáveis, outro
   cadastro com cartão, o Supabase continuaria à parte); VPS (US$ 5–10 e manutenção); Vercel (ADR-010: Hobby não permite uso comercial).
   `gcloud run deploy --source .` seria o caminho mais curto, mas exige mais permissões (Cloud Build) e um terminal configurado em cada
   computador; o workflow manual abaixo evita as duas coisas.
3. **Imagem:** `Dockerfile` (python:3.12-slim + uv, usuário sem privilégio, gunicorn, estáticos via **WhiteNoise**). Sem `migrate` na
   inicialização: migrations continuam com `make migrate` na máquina do titular (evita corrida entre instâncias e dá ao humano o controle).
4. **Deploy:** `.github/workflows/deploy.yml`, **só `workflow_dispatch` e só da `main`**, autenticando por **Workload Identity Federation**
   (sem chave JSON). IDs do projeto/região/provedor ficam em *Variables* do GitHub (não são segredos).
5. **Segurança (configuração em `radar/settings.py`):** `DJANGO_HTTPS=true` liga redirect para HTTPS, cookies seguros, HSTS (1 ano, sem
   preload) e `X-Frame-Options: DENY`; `DEBUG` desligado por padrão; `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` explícitos; senha com
   **≥ 12 caracteres**; sessão de 12 h em produção; caminho do admin configurável (`DJANGO_ADMIN_URL`); `/healthz` público e sem dados.
   `manage.py check --deploy` sem avisos é testado (`tests/test_hosting.py`).
6. **Fora desta etapa (registrado):** 2FA, bloqueio por tentativas (django-axes) e camada extra (Cloudflare Access/IAP). Com 2–3 contas
   e senhas fortes o risco é aceitável por ora; reavaliar quando houver mais usuários ou dados mais sensíveis. Domínio próprio
   (`app.scorpionbits.com`) é opcional: a URL `*.run.app` já tem HTTPS.

## Consequências
+ Admin acessível de qualquer computador, mesmo banco que o terminal e o GitHub Actions usam.
+ Custo ≈ US$ 0 em uso interno; sem servidor para manter.
− Cold start de alguns segundos após período parado (aceitável).
− O admin fica exposto na internet com autenticação só por senha: depende de senhas fortes (P34).
− Conta Google Cloud com faturamento é pré-requisito (ação do titular, P34). Imagem não foi construída no ambiente do Claude (sem Docker);
  o primeiro deploy valida o `Dockerfile`.
