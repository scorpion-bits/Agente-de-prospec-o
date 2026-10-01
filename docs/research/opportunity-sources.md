# Fontes de oportunidades (editais, hackathons, jams, programas, eventos)

> Levantamento: 30/09/2026 via busca web. **Nenhum endpoint foi testado diretamente**:
> o ambiente de planejamento bloqueou acesso de rede a esses domínios. A validação real
> (acesso, formato, robots.txt, termos) é a **etapa E01**. Atualize a coluna "Validado".

Confiabilidade: 5 = oficial/estruturado · 3 = agregador confiável · 1 = não oficial/frágil.

## Prioridade MVP

| # | Fonte | Tipo de oportunidade | Método de acesso | Custo | Confiab. | Validado |
|---|---|---|---|---|---|---|
| 1 | **Devpost** (`devpost.com/api/hackathons`) | Hackathons (online/presenciais, globais) | JSON público usado pelo próprio site (sem auth); filtros `status`, busca | Grátis | 4 | ⏳ E01 — termos para uso automatizado não confirmados; conector pronto (E05, ADR-028), fonte desabilitada até conferir (P16) |
| 2 | **itch.io jams** (`itch.io/jams`) | Game jams | Sem API oficial de jams; páginas de listagem aceitam sufixo `.xml` (RSS) para browse pages; `itch.io/jam/<id>/entries.json` para entradas | Grátis | 4 | ⏳ E01 — verificar se `/jams/upcoming.xml` existe |
| 3 | **Querido Diário** (API pública, Open Knowledge Brasil) | Editais, chamamentos, credenciamentos municipais em diários oficiais | API REST: busca textual por termo + município (`territory_ids`) + período; retorna trecho + PDF | Grátis | 4 | ⏳ E01 — confirmar cobertura de Araraquara e vizinhas |
| 4 | **Mapas Culturais** (mapa.cultura.gov.br e instâncias estaduais/municipais) | Oportunidades/editais culturais (inclui PNAB) | API JSON (`/api/opportunity/find`, mesmo padrão de `/api/event/find`) | Grátis | 4 | ⏳ E01 — listar instâncias relevantes (SP? Araraquara?) |
| 5 | **FAPESP — PIPE** (`fapesp.br/pipe/chamadas`) | Subvenção a inovação em pequenas empresas (até R$ 500 mil na Fase 1) | `html_watch` da página de chamadas | Grátis | 5 | ⏳ E01 — exige empresa (CNPJ) |
| 6 | **Secretaria de Cultura SP — ProAC Editais / PNAB** (`cultura.sp.gov.br` Fomento; inscrições em `proacexpresso.sp.gov.br`) | Editais culturais estaduais — **existe linha específica de jogos eletrônicos** (Edital ProAC 05/2026 "Desenvolvimento ou Finalização e Publicação de Jogos Eletrônicos"; exige PJ com sede/domicílio em SP há mais de 2 anos e objetivo cultural) | `html_watch` (arquivo de editais) | Grátis | 5 | ⏳ E01 — monitorar próxima edição; conferir se MEI é aceito |
| 6b | **Oficinas Culturais do Estado de SP (Poiesis)**, MIS-SP, editais municipais de oficinas culturais | Chamadas de propostas de oficinas/projetos | `html_watch` + Querido Diário | Grátis | 5 | ⏳ E01 |
| 7 | **Sebrae-SP** (editais, programas, eventos) | Programas de empreendedorismo, editais com FAPESP | `html_watch` (+ Sympla/eventos se houver) | Grátis | 4 | ⏳ E01 |
| 8 | **InovAtiva Brasil** | Aceleração gratuita (chamadas semestrais) | `html_watch` | Grátis | 5 | ⏳ E01 |
| 9 | **Prefeitura de Araraquara** (+ São Carlos, Matão, Américo Brasiliense) | Editais municipais de cultura/educação, chamamentos | `html_watch` das páginas de editais + Querido Diário | Grátis | 4 | ⏳ E01 — mapear URLs |
| 10 | **SESC SP** (sescsp.org.br) | Chamadas/credenciamentos de oficineiros, programação | `html_watch` (se existir página de credenciamento) | Grátis | 5 | ⏳ E01 — descobrir se existe chamamento público |

## Fase 4 / candidatas

| Fonte | Tipo | Método | Custo | Confiab. | Observação |
|---|---|---|---|---|---|
| **PNCP** (`pncp.gov.br/api/consulta`) | Contratações públicas (cursos, software, jogos educativos) | API REST pública (Swagger); `/contratacoes/proposta` (propostas abertas), `/contratacoes/publicacao` | Grátis | 5 | **Viável com o MEI** (ADR-013); cotas exclusivas ME/EPP/MEI até R$ 80 mil; 1ª candidata da Fase 4 |
| Finep (chamadas públicas) | Inovação | `html_watch` | Grátis | 5 | Geralmente exige empresa estruturada |
| MCTI / CNPq chamadas | Pesquisa/inovação | `html_watch` | Grátis | 5 | Baixo encaixe no curto prazo |
| Portal de Dados Abertos da Cultura (dados.cultura.gov.br) | Datasets do Mapa da Cultura | Dataset | Grátis | 5 | Complementa Mapas Culturais |
| Universidades da região (UFSCar, USP São Carlos, UNESP Araraquara, IFSP) | Hackathons, eventos, incubadoras, parcerias | `html_watch` páginas de eventos/agência de inovação | Grátis | 4 | Networking e parcerias |
| Incubadoras/parques (ParqTec São Carlos, Supera Ribeirão, incubadoras locais) | Programas, editais de incubação | `html_watch` | Grátis | 4 | Programa PIPE credencia incubadoras |
| Sympla / Even3 | Eventos de tecnologia/games | Página de busca/categoria (verificar API/termos) | Grátis | 3 | Cuidado com termos de uso |
| MLH, Hackathon.com, Global Game Jam, Ludum Dare | Hackathons/jams | Feeds/páginas | Grátis | 3–4 | GGJ tem sites locais (jam sites) — pode existir em São Carlos |
| BIG Festival, SBGames, Gamescom Latam, Game XP | Eventos/prêmios de games | `html_watch` | Grátis | 4 | Chamadas de jogos/palestras; valor de visibilidade |
| Abragames / Apex (programas de exportação de games) | Programas setoriais | `html_watch` | Grátis | 4 | Exige CNPJ (temos MEI — conferir natureza jurídica aceita) |
| Newsletters/agregadores de editais | Editais variados | E-mail → leitura manual ou `html_watch` | Grátis | 3 | Útil como validação de cobertura |

## Estratégia de busca por palavras-chave (Querido Diário e similares)

Consultas iniciais (ajustar após E08): `"oficina" AND ("jogos" OR "games")`,
`"curso" AND ("programação" OR "desenvolvimento de jogos")`, `"chamamento público" AND cultura`,
`"credenciamento" AND oficineiros`, `"edital" AND ("PNAB" OR "Aldir Blanc")`, `"game jam"`,
`"hackathon"`, `"gamificação"`, `"robótica" AND escola` (sinal de demanda extracurricular).

## Fontes consultadas nesta pesquisa

- Querido Diário — API pública: https://docs.queridodiario.ok.org.br/pt-br/latest/utilizando/api-publica.html
- Mapas Culturais — documentação da API: https://docs.mapasculturais.org/mc_config_api/ ; https://dados.cultura.gov.br/dataset/mapa-da-cultura
- PNCP — Manual das APIs de Consultas: https://www.gov.br/pncp/pt-br/acesso-a-informacao/manuais/ManualPNCPAPIConsultasVerso1.0.pdf (Swagger: https://pncp.gov.br/api/consulta/swagger-ui/index.html)
- itch.io — API/feeds: https://itch.io/docs/api/overview ; https://itch.io/t/23378/tag-feeds-or-query-api-integration-with-external-sites ; https://itch.io/t/5408218/game-jam-api-to-fetch-basic-jam-info
- Devpost — endpoint público descrito por wrappers: https://apify.com/automation-lab/devpost-scraper
- FAPESP PIPE: https://fapesp.br/pipe/chamadas
- ProAC 05/2026 jogos eletrônicos: https://www.cultura.sp.gov.br/sec_cultura/Arquivo_de_Editais/Editais_Fomento_Cultsp/Fomento_CultSP_2026/desenvolvimento_ou_finalizacao_e_publicacao_de_jogos_eletronicos_2026/
- Oficinas culturais (exemplos de edital municipal/estadual): https://www.marilia.sp.gov.br/portal/noticias/0/3/10010/secretaria-da-cultura-lanca-edital-para-contratacao-de-projetos-de-oficinas-culturais ; https://mis-sp.org.br/selecao-de-projetos/
- MEI em licitações: https://effecti.com.br/mei-pode-ser-licitante/ ; https://www.loggi.com/conteudos/empreendedorismo/limite-faturamento-mei/
- ProAC: https://www.cultura.sp.gov.br/sec_cultura/Fomento/Programa_ProAC_(Editais) ; https://www.cultura.sp.gov.br/sec_cultura/Fomento/Fomento_Editais_e_PNAB
- Sebrae-SP + FAPESP: https://sp.agenciasebrae.com.br/cultura-empreendedora/sebrae-sp-e-fapesp-lancam-dois-editais-para-financiamento-de-startups/
