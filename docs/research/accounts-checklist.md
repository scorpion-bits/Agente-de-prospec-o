# Checklist de contas e infraestrutura

> Sem segredos, e-mails ou CNPJ (repositório público — ADR-014). Atualizado na E01b, 2026-09-30.
> Legenda: ✅ confirmado · ⏳ pendente (humano) · 🔎 verificar na prática

## Já confirmado

| Item | Situação |
|---|---|
| Domínio `scorpionbits.com` | ✅ existe; site no ar (https://scorpionbits.com/) |
| Repositório GitHub | ✅ **público** → minutos de Actions sem limite; `schedule` funciona; logs/commits públicos (ADR-014) |
| Empresa | ✅ MEI ativa desde 10/04/2025; CNAEs em `data/seeds/company_profile.json`; CNPJ só no `.env` (ADR-015) |
| Conta Google | ✅ conta pessoal do titular do MEI tem (ou terá) o Google AI Pro |
| Contato para User-Agent/digest | ✅ Gmail de contato (definido em `CONTACT_EMAIL` no `.env`, não no git) |

## Pendências para o humano

| # | Ação | Por quê / observação |
|---|---|---|
| A1 | Criar projetos **Supabase** `radar-dev` e `radar-prod` (região mais próxima, ex. São Paulo); anotar a string do **pooler** (não a direta); guardar a senha em gerenciador | Banco do MVP (ADR-010). Ninguém além do Django deve acessar; as tabelas ficam no schema `radar`, fora da Data API (ADR-016). Passo a passo: `docs/operations/supabase-setup.md` |
| A2 | Ativar os **benefícios de desenvolvedor do Google AI Pro** em google.dev ("Activate Developer Benefits") | ~US$ 10/mês em créditos de Cloud; 🔎 conferir em Billing que valem para a Gemini API |
| A3 | Criar **chave do Google AI Studio** (free tier) e, separadamente, projeto Cloud com faturamento para a chave paga | Free tier só para documentos públicos; dados internos só na chave paga (ADR-011) |
| A4 | Escolher busca: **Serper** (2.500 buscas grátis) ou **Brave** (US$ 5 de crédito/mês) | 🔎 conferir se pedem cartão; 1 busca por organização, com cache |
| A5 | Gerar par de chaves **age** para backup; guardar a privada fora do GitHub; colocar a pública em secret | Backup criptografado (ADR-014) |
| A6 | Configurar **GitHub Secrets** (DATABASE_URL, chaves de IA/busca, SMTP, chave pública age) e restringir workflows de forks | Fazer na E16; não colar segredos em issues/PRs |
| A7 | (Opcional) Criar `contato@scorpionbits.com` (encaminhamento de e-mail do provedor de DNS) | Mais credibilidade nas abordagens e no User-Agent; não bloqueia nada |
| A8 | (Adiar) Conta da **Anthropic API** com limite de gasto baixo | Só se Gemini falhar na extração (E11) |
| A9 | **Consultar contador**: CNAEs para desenvolvimento de software/web/jogos sob encomenda, migração para ME, enquadramento de cursos | ADR-015 |

## Riscos de infraestrutura registrados

- **Conta Google pessoal** concentra os créditos: se o titular perder acesso, a IA paga para.
  Mitigação: chave gratuita + Claude como reserva; revisar quando houver Workspace da empresa.
- **`schedule` desliga após 60 dias sem commits** (repositório público): alerta no digest.
- Free tier do Supabase **pausa** após 7 dias sem uso e **não tem backups**.
