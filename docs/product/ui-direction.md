# Direção da interface (UI)

> Estado: **direção decidida, nada construído**. O Django admin segue como UI de retaguarda do
> MVP (ADR-001). Decisões: ADR-019. Esta página guarda o que foi decidido e a identidade
> visual de referência, para a etapa de UI (E29) começar informada.

## Decidido pelo titular (2026-10-01)

- Interface **web**, não executável (ADR-019). Sem Windows/Linux separados: um deploy só.
- O front novo **consome uma API do nosso Django**. Ninguém, além do Django, acessa o Supabase
  (ADR-016). Chave publicável e URL da Data API do Supabase **não são usadas** pelo projeto.
- Visual **próximo do site da empresa** (`scorpionbits.com`).

## Identidade do site (referência)

Fonte: repositório `scorpion-bits/scorpion-bits.github.io`, commit `d7ea7d4` (2026-10-01).
Site estático (HTML + 1 CSS + 1 JS, **sem build e sem CDN**), GitHub Pages, domínio por `CNAME`.
Cabeçalho do CSS: "paleta tirada da logo (cubo isométrico) + tipografia própria".

| Token (nome no site) | Valor | Uso no site |
|---|---|---|
| `--ink-950` / `900` / `850` / `800` | `#05090f` / `#080e16` / `#0c141f` / `#111c2a` | fundos (tema escuro, azulado) |
| `--cyan` `--blue` `--indigo` `--violet` | `#6ad8fe` `#51a8f6` `#5b6bf5` `#8b5cf6` | acentos |
| `--amber` `--mint` | `#ffc46b` `#7ee2a8` | destaque quente / sucesso |
| `--text` `-soft` `-dim` `-faint` | `#eef5fb` `#b4c6d7` `#7d94aa` `#55697d` | hierarquia de texto |
| `--hair` / `--hair-lit` | `rgba(126,190,232,.14)` / `.34` | linhas finas e bordas |
| `--grid-line` | `rgba(106,216,254,.055)` | motivo de grade no fundo |
| raios | `10px` `14px` `26px` pílula | cantos |
| fontes | **Grotesk** (títulos, 300–700), **Inter** (corpo), mono do sistema | `woff2` próprio, subset latin |
| escala | `clamp()` fluida de `--s--1` a `--s-4` | tipografia responsiva |

Também tem: navegação em "dock" fixa, `theme-color #05090f`, idioma `pt-BR`, e um **modo leve**
(desliga efeitos em máquina com ≤ 2 núcleos/2 GB ou economia de dados).

## Como aplicar no app (proposta)

- **Reusar os tokens** (mesmos nomes de variável CSS, para compartilhar com o site). Tema escuro
  como padrão. **Não** levar os efeitos decorativos (paralaxe, vídeo do mascote, orbes) para telas
  de dados; manter a ideia do modo leve.
- **Fato × inferência (ADR-004) na identidade da marca:** observado → `--mint`, inferido →
  `--violet` com borda **tracejada**, manual → `--cyan`; sempre ícone + texto, não só cor.
- **Acessibilidade** (contraste WCAG medido sobre `ink-950` / `ink-800`):
  `--text-faint` dá 3,5:1 / 3,0:1 e **não serve para texto pequeno** (só decoração ou texto
  grande); `--violet` e `--indigo` passam sobre `ink-950` (4,7 / 4,6) mas **não** sobre cartões
  `ink-800` (4,1 / 4,0): usar tom mais claro ou texto maior nesses casos. Os demais passam.
- **Fontes:** confirmar a licença de "Grotesk" e do Inter antes de copiar os `woff2` para este
  repositório (são fontes livres comuns, mas conferir o arquivo de licença de cada uma).

## Em aberto (decidir na etapa de UI, com o humano)

1. Tecnologia do front: páginas leves (HTMX/Alpine, mais perto do site atual) ou SPA (React).
2. Hospedagem: o Vercel já está conectado, mas o Django (API) precisa de hospedagem própria
   (Cloud Run, ADR-010); decidir se o Vercel serve só o front.
3. Autenticação (sessão do Django ou token), CORS/CSRF e estilo da API (DRF ou Django Ninja).
4. Repositório do front: pasta `web/` neste repo ou repositório separado.
5. Telas candidatas, na ordem do valor: "Já falamos com eles?" (organização + histórico, M1),
   triagem de oportunidades com a explicação do score, digest semanal, follow-ups, catálogo e
   cobertura do MEI.

## Sequência sugerida (não alterei o plano)

API e telas seguem o modelo de dados: **E03b e E04 antes**, para não refazer contratos. O M1
("já falamos com eles?") já sai no admin. Planejar a UI com telas reais depois do M1; a E29
muda de "Django no Cloud Run" para "front + API" quando o humano pedir o replanejamento.
