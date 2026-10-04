# Admin online no Cloud Run (E29, ADR-047) — passo a passo para o titular

> Faça tudo isto **uma vez**, no fim, junto com os demais itens P. Nunca cole senha, `DATABASE_URL` ou chaves no chat ou no git.
> Pode usar o **Cloud Shell** do console do Google (terminal no navegador, já com `gcloud`): não precisa instalar nada.
> Troque os valores `<…>`. Região sugerida: `southamerica-east1` (São Paulo).

## 1. Projeto e faturamento
1. Em console.cloud.google.com crie um projeto (ex.: `scorpion-radar`) e **vincule o faturamento** (Cloud Run exige, mas o uso
   interno fica no free tier; crie um **alerta de orçamento** de US$ 5 em Faturamento → Orçamentos).
2. No Cloud Shell:
```bash
gcloud config set project <PROJECT_ID>
gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com iamcredentials.googleapis.com
gcloud artifacts repositories create radar --repository-format=docker --location=<REGION>
```

## 2. Segredos (Secret Manager)
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))" | gcloud secrets create radar-secret-key --data-file=-
# DATABASE_URL = a string do Session pooler do Supabase (docs/operations/supabase-setup.md). Digite no prompt:
read -rsp "DATABASE_URL: " U; echo; printf %s "$U" | gcloud secrets create radar-database-url --data-file=-; unset U
```

## 3. Conta de serviço e login do GitHub (sem chave JSON)
```bash
PN=$(gcloud projects describe <PROJECT_ID> --format='value(projectNumber)')
gcloud iam service-accounts create radar-deployer
SA=radar-deployer@<PROJECT_ID>.iam.gserviceaccount.com
for R in run.admin artifactregistry.writer iam.serviceAccountUser; do
  gcloud projects add-iam-policy-binding <PROJECT_ID> --member=serviceAccount:$SA --role=roles/$R; done
# o serviço roda com a conta padrão do Compute; ela precisa ler os segredos:
for S in radar-secret-key radar-database-url; do
  gcloud secrets add-iam-policy-binding $S --member=serviceAccount:$PN-compute@developer.gserviceaccount.com --role=roles/secretmanager.secretAccessor; done
gcloud iam workload-identity-pools create github --location=global
gcloud iam workload-identity-pools providers create-oidc github-repo --location=global --workload-identity-pool=github \
  --issuer-uri=https://token.actions.githubusercontent.com \
  --attribute-mapping=google.subject=assertion.sub,attribute.repository=assertion.repository \
  --attribute-condition="assertion.repository=='scorpion-bits/Agente-de-prospec-o'"
gcloud iam service-accounts add-iam-policy-binding $SA --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/$PN/locations/global/workloadIdentityPools/github/attribute.repository/scorpion-bits/Agente-de-prospec-o"
echo "projects/$PN/locations/global/workloadIdentityPools/github/providers/github-repo"   # = GCP_WIF_PROVIDER
echo "$PN"   # número do projeto (usado no passo 4)
```

## 4. Variáveis no GitHub (Settings → Secrets and variables → Actions → **Variables**)
| Variável | Valor |
|---|---|
| `GCP_PROJECT` | `<PROJECT_ID>` |
| `GCP_REGION` | `<REGION>` |
| `GCP_WIF_PROVIDER` | a linha `projects/…/providers/github-repo` do passo 3 |
| `GCP_SERVICE_ACCOUNT` | `radar-deployer@<PROJECT_ID>.iam.gserviceaccount.com` |
| `APP_HOSTS` | `radar-admin-<NÚMERO_DO_PROJETO>.<REGION>.run.app` (acrescente `,app.scorpionbits.com` se usar domínio) |

## 5. Publicar
Actions → **Deploy admin (Cloud Run)** → *Run workflow* (branch `main`). Ao fim, a URL aparece no log do passo «Publicar» (a mesma de `APP_HOSTS`).
Se der `DisallowedHost`/400, a URL difere do que está em `APP_HOSTS`: corrija a variável e rode de novo.

## 6. Primeiro acesso
1. Banco já migrado? Se não, na sua máquina: `make migrate` (o container **não** migra).
2. Usuário do admin: na sua máquina, com o `.env` apontando para o mesmo Supabase, `make superuser` (senha ≥ 12 caracteres, única, de gerenciador de senhas).
3. Abra a URL, entre em `/admin/`. Crie as contas dos colegas no admin (grupo/permissões mínimas; sem «superusuário» sem necessidade).

## Opcional
- **Domínio próprio:** Cloud Run → *Gerenciar domínios personalizados* → `app.scorpionbits.com` (cria registro DNS e certificado); depois acrescente em `APP_HOSTS` e rode o deploy.
- **Trocar o caminho do admin:** acrescente `DJANGO_ADMIN_URL=<algo-longo>/` às variáveis do serviço (`gcloud run services update radar-admin --update-env-vars …`).
- **Custo/desligar:** `gcloud run services delete radar-admin --region <REGION>`. Escala a zero sozinho.
