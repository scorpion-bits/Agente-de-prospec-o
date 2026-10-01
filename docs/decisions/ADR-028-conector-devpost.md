# ADR-028 — Conector Devpost (API pública) com filtro de relevância e datas sem chute

- **Status:** aceito
- **Data:** 2026-10-01
- **Etapa:** E05

## Contexto
Devpost lista hackathons em JSON público (`/api/hackathons`). O ambiente do Claude não alcança devpost.com e a E01
(validação das fontes) segue pendente: o formato da resposta vem de documentação de terceiros e de memória.

## Decisão
1. **Conector `api` sem IA** (`collection/connectors/devpost.py`), sempre via `PoliteFetcher`; até `max_api_pages`
   (padrão 5) páginas com `status[]=open&status[]=upcoming`; para quando a página vem vazia ou repetida.
2. **Fonte nasce desabilitada e sem `robots_ok`** (`load_sources`): termos de uso para uso automatizado não foram
   confirmados (P16). O humano confere termos e robots.txt, marca «coleta permitida» e habilita no admin.
3. **Filtro de relevância em `normalize`** (configurável em `Source.config`): precisa de tema/título nas palavras de
   interesse (jogos, educação, impacto social, tema aberto, comunidade, iniciante) **e** ser online ou no Brasil
   (`allow_in_person` libera o resto); hackathon só por convite é ignorado.
4. **Datas:** a API só dá o período como texto («Sep 01 - Oct 30, 2026»). Lemos início e fim quando a forma é
   inequívoca (ano da data final; virada de ano inferida); qualquer outra forma deixa as datas **em branco** (ADR-004).
   Abertura = 00:00 e prazo = 23:59 no fuso `America/Sao_Paulo`.
5. **Dedupe** pela URL do hackathon sem parâmetros de rastreio (`ref_feature`, `utm_*`); revisitar atualiza o prazo.
6. **Evidência:** título, organizador, modalidade, local, temas, período, prêmio e situação, todos `observed` com a URL
   do hackathon. Prêmio `$0` não é registrado.

## Consequências
+ Custo zero; testado com fixture **sintética** (`tests/fixtures/devpost/`), sem rede.
− Se o JSON real diferir, o erro aparece como «Resposta inesperada» e a fonte falha inteira (nada é gravado errado).
− Palavras de interesse e filtro são hipóteses: revisar com a primeira coleta real (P16).
