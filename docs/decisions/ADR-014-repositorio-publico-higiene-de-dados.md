# ADR-014 — Repositório público: higiene de dados, logs e backups

- **Status:** aceito (complementa ADR-010)
- **Data:** 2026-09-30
- **Etapa:** E01b

## Contexto
O repositório `scorpion-bits/Agente-de-prospec-o` é **público**. Isso ajuda (GitHub Actions
sem limite de minutos e com `schedule`), mas tudo que entra em commit, log de workflow ou
artefato deve ser tratado como público. O sistema lida com contatos, histórico de propostas,
leads e dados do titular do MEI (LGPD).

## Decisão
1. **Nunca no git**: CNPJ, razão social do titular, endereço, e-mails, telefones, nomes de
   contatos, interações, digests, dumps do banco, chaves. Só em `.env`, banco ou
   `data/private/` (ignorado). Em `data/seeds/` (versionado) ficam **apenas dados públicos ou
   não sensíveis** (portfólio, CNAEs, datas, templates sem pessoas).
2. **Logs de workflow são públicos**: o pipeline registra só contagens e status
   (`LOG_PII=false`); nunca nome de contato, e-mail, telefone, valor de proposta ou trecho de
   interação.
3. **Backups**: `pg_dump` é **criptografado com `age`** (chave pública no secret
   `BACKUP_AGE_PUBLIC_KEY`; a privada só com o titular) antes de qualquer upload. Artefatos de
   repositório público devem ser tratados como baixáveis por terceiros; backup em claro é proibido.
   Alternativa equivalente: destino privado fora do GitHub.
4. **Digest**: nunca como artefato, commit ou Pages. É entregue por e-mail à própria equipe
   (SMTP em secret) ou gerado localmente.
5. **Workflows**: só `schedule` e `workflow_dispatch`; proibido `pull_request_target` e qualquer
   gatilho que exponha secrets a forks; aprovação exigida para workflows de colaboradores externos.
6. **`schedule` desliga após 60 dias sem commits** em repositório público: o digest e o runbook
   alertam "última coleta há X dias"; reativar manualmente ou manter commits regulares.
7. **Documentação pública**: `docs/` não contém nomes de pessoas de contato, valores de
   propostas nem condições comerciais. Estratégia de alto nível (segmentos, fontes, scoring) é aceitável.
   O histórico já publicado (E00/E00b) cita que há propostas enviadas a SESC Bauru, Ribeirão Preto
   e São Carlos — sem datas, valores ou pessoas.

## Alternativas consideradas
| Alternativa | Por que não agora |
|---|---|
| Tornar o repositório privado | Free: 2.000 min/mês e `schedule` incerto em conta gratuita; dá para voltar a esta opção se a estratégia pública incomodar |
| Dividir em dois repositórios (código público, dados privados) | Complexidade prematura; dados já ficam fora do git |

## Consequências
+ Custo zero, sem depender de minutos. − Disciplina extra (este ADR); criptografia de backup.
− `docs/` revela estratégia comercial em alto nível.

## Quando revisitar
Se a estratégia em `docs/` passar a incomodar, se houver colaboradores externos, ou ao
formalizar como ME/EPP com clientes sob NDA → repositório privado.
