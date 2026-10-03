# ADR-037 — Digest semanal: arquivo local, listas com limite, e-mail só para a equipe

- **Status:** aceito
- **Data:** 2026-10-03

## Contexto
A E15 entrega o que importa da semana sem abrir o sistema (`docs/plan/fase-2-priorizacao.md`). O digest mistura dados públicos
(oportunidades) e privados (follow-ups com resumo de interações), e o repositório é público (ADR-014). O envio automático de
mensagens a terceiros é vetado (ADR-005).

## Decisão
1. **`reports/digest.py` + `make digest`**: só leitura do banco, sem IA e sem rede. Gera `data/digests/AAAA-Www.html` (template
   Django, com escape) e `.md`; `data/` já é ignorado pelo git. `DRY=1` imprime o Markdown sem gravar.
2. **Seções**: follow-ups vencidos ou nos próximos 7 dias (última interação, resumo cortado em 160 caracteres), top-10 por pontuação
   com «por quê» (os dois fatores que mais pontuaram + primeiro alerta, do próprio `Score`), prazos em ≤ 14 dias, novidades desde
   o último digest, bloqueadas por requisito da empresa (contagem e valor somado só das que têm valor), fontes habilitadas com
   erro ou sem coleta há mais de 7 dias, custo do mês (dinheiro novo e créditos). Todas com limite rígido de itens.
3. **Nada gated, descartado ou concluído nas listas de ação.** Bloqueadas só aparecem na seção própria, e apenas as de gate
   `company_requirement`; as barradas por prazo ou território ficam fora. Top e prazos excluem rótulo «ignorar» e oportunidades encerradas.
4. **«Desde o último digest»** vem de `data/digests/.state.json` (sem migration); sem o arquivo, 7 dias; `--since AAAA-MM-DD` força.
   No GitHub Actions (E16) o estado local não persiste: lá se usará `--since`/janela fixa.
5. **E-mail opcional (`--email`)**: destinatários só da lista `DIGEST_EMAIL_TO` do `.env` (nunca de argumento de linha de comando ou banco);
   sem a lista o comando falha **antes** de gerar. A equipe ainda não tem domínio próprio (usa o Gmail da empresa e e-mails pessoais
   dos membros), então a trava é a lista explícita, não o domínio. Remetente: `DIGEST_EMAIL_FROM` ou `SMTP_USER`; credenciais SMTP
   só no `.env`. Sem envio para terceiros (ADR-005). **Atenção:** o e-mail leva resumos de interações; só liste quem pode ver isso.
6. **Seções de leads** ficam para quando a E21 existir; o digest avisa isso no rodapé.

## Consequências
- O digest com dados pessoais nunca vai para o git nem para logs (o comando imprime só contagens).
- M2 (E14) continua usando o ranking atual do `Score`, não o top-10 entregue: guardar o top entregue exigiria tabela nova; reavaliar se o M2 divergir do que a equipe viu.
- E16 chamará `digest` no `run_pipeline`; artefato do Actions é público para quem acessa o repositório: **não** publicar o digest como artefato, só enviar por e-mail da equipe.
