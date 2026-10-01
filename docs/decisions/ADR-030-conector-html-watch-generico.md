# ADR-030 — Conector `html_watch` genérico: uma página = uma `Source`

- **Status:** aceito
- **Data:** 2026-10-01
- **Etapa:** E07

## Contexto
FAPESP/PIPE, ProAC, Oficinas Culturais, Sebrae-SP, InovAtiva e as prefeituras dos polos não têm API: só uma página
de listagem com links para os editais. O ambiente do Claude não alcança essas páginas (E01 pendente), então o HTML
real não foi visto. O plano pede ≥ 5 páginas **sem código por página** e 0 novos ao repetir a execução.

## Decisão
1. **Um conector, registrado por `kind=html_watch`** (`collection/connectors/html_watch.py`). O conector por `slug`
   (`itch-jams`) continua valendo sobre ele. Configuração em `Source.config`: `url`, `selector`, `link_patterns`,
   `keywords`, `exclude_patterns`, `same_host`, `max_links`, `min_title_chars`, `opportunity` (valores fixos da página:
   tipo, organizador, abrangência, UF, município, categorias).
2. **Sem dependência nova:** parser de `html.parser` (stdlib) que monta uma árvore tolerante (`<li>` sem fechar,
   `script`/`style` ignorados) e um subconjunto de CSS (`tag`, `.classe`, `#id`, vírgula e descendente). Seletor
   fora disso dá erro claro, não resultado silencioso.
3. **Área da listagem:** o `selector`; sem ele, ou se ele não achar nada (layout mudou), o «conteúdo principal» =
   página sem `nav`, `header`, `footer` e `aside` (fallback do plano).
4. **Novidade = o que o upsert cria.** Cada link aceito vira `Opportunity(status=unknown)` com `official_url` = link e
   chave canônica = URL (sem tracking, `www`, barra final). Repetir a coleta dá `unchanged`; link novo é `created`.
   Não há tabela de hash/snapshot: o banco já é o diff, e uma coleta em `--dry-run` não "gasta" a novidade.
5. **Só o que a página mostra (ADR-004):** título = texto do link, trecho = bloco que o cerca (`li`/`p`/`tr`/…),
   `Evidence(observed)` com o `RawDocument`. **Nenhuma data, valor ou elegibilidade é lida aqui**: é da E11 (leitura
   da página do edital). Candidata = `status=unknown` e `extraction_version` em branco.
6. **Sem flag `needs_extraction`:** o plano cita o campo, mas ele não existe no modelo e criá-lo exigiria migration
   só para uma marca que `status=unknown` + `extraction_version=""` já expressa. A E11 decide se a cria.
7. **Erros explícitos:** página sem nenhum link (típico de página só em JavaScript, que não executamos) e regex/
   seletor inválidos levantam erro; nunca "0 itens" silencioso.
8. **9 fontes iniciais** em `load_sources` (FAPESP PIPE, ProAC/PNAB, Oficinas Culturais, Sebrae-SP, InovAtiva e as
   prefeituras de Araraquara, São Carlos, Ribeirão Preto e Bauru), todas **desabilitadas e sem `robots_ok`**, como
   Devpost e itch.io. As páginas do SESC-SP ficam de fora: ainda não há URL de chamamento conhecida.

## Consequências
+ Custo zero, sem IA; adicionar página = uma linha de configuração; 20 testes (fixtures **sintéticas** antes/depois).
− URLs de memória/da pesquisa (as das prefeituras, Sebrae-SP e InovAtiva são páginas iniciais): a primeira coleta
  real provavelmente precisa de `selector`/`link_patterns` por página; o humano confere e ajusta no admin (P18).
− Ruído (notícias, menus) só é filtrado por padrões/palavras: sem calibração real, espere falsos positivos.
− Título vem do texto do link («Saiba mais») quando a página é pobre; `min_title_chars` descarta os curtos demais.
