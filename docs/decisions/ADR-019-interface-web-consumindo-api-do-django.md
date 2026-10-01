# ADR-019 — Interface nova: web (sem app executável), consumindo uma API do Django

- **Status:** aceito (princípios); tecnologia e hospedagem do front ficam para a etapa de UI
- **Data:** 2026-10-01
- **Etapa:** E03 (decisão do titular durante a sessão)

## Contexto
O titular quer uma grande mudança visual: interface própria, no estilo do site da empresa
(`scorpionbits.com`), no lugar do Django admin. Perguntou se compensaria um executável
(Windows/Linux) ou só um site. Já existem um projeto Supabase e um projeto Vercel, ambos ligados
ao GitHub. A identidade visual está em `docs/product/ui-direction.md`.

## Decisão
1. A interface é **web** (responsiva, instalável como PWA se fizer sentido), **não** executável.
2. O front novo **só conversa com uma API do nosso Django**. Nenhum front acessa o Supabase
   diretamente (Data API, chave publicável, RLS): vale a regra do ADR-016, só o Django toca
   no banco.
3. A identidade visual vem do site: usamos os **tokens** (cores, fontes, raios, linhas finas),
   não os efeitos decorativos.
4. Enquanto a interface nova não existe, o Django admin é a UI de retaguarda.

## Alternativas consideradas
| Alternativa | Por que não |
|---|---|
| App executável (Tauri, Electron, PyInstaller) | A senha do banco não pode ir num binário distribuído (dados pessoais, LGPD), então ainda precisaria de servidor; exige dois builds, assinatura de código e atualização; não cobre celular, onde acontece a prospecção em campo |
| Front direto no Supabase (RLS) | Dados pessoais exigiriam políticas por linha e uma superfície de ataque nova; contraria o ADR-016 |
| Só o Django admin com tema | Barato, mas não entrega a identidade nem a experiência pretendidas |

## Consequências
+ Um deploy atualiza todos; funciona em qualquer sistema e no celular; credenciais ficam no
  servidor.
− Exige projetar e manter uma **API** e autenticação. Os contratos seguem o modelo de dados:
  não construir antes de E03b/E04 estabilizarem as entidades.
− Impacto no plano: a E29 ("Django no Cloud Run") passa a ser "front + API". Replanejar quando
  o humano pedir.
− O Vercel conectado a **este** repositório tentará um deploy a cada push, sem front para
  construir: ver o aviso em `STATUS.md` (P9).

## Quando revisitar
Se surgir requisito que só app nativo atenda (uso offline pesado, arquivos ou hardware locais):
um invólucro fino sobre a mesma URL resolve sem refazer o produto.
