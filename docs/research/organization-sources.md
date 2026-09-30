# Fontes de organizações (escolas, SESCs, empresas, instituições)

> Levantamento: 30/09/2026. Validação prática na **E01** (acesso de rede bloqueado no
> ambiente de planejamento).

| # | Fonte | Entidades | Método | Custo | Confiab. | Uso | Validado |
|---|---|---|---|---|---|---|---|
| 1 | **INEP — Catálogo de Escolas** (gov.br/inep → dados abertos → inep-data → catálogo de escolas) | Todas as escolas de educação básica (~226 mil), com endereço, telefone, etapas/modalidades, dependência administrativa (privada/pública), porte | Consulta/exportação no portal; dados atualizados anualmente pelo Censo Escolar | Grátis | 5 | **MVP (E17)**: escolas privadas na região, com etapas (fund. II, médio) | ⏳ E01 — verificar se há exportação CSV por município |
| 2 | **INEP — Microdados do Censo Escolar** | Escolas + infraestrutura (laboratório de informática, internet…) | Download CSV anual (sem auth) | Grátis | 5 | Alternativa/complemento ao catálogo; sinais (tem lab de informática?) | ⏳ E01 |
| 3 | **Lista semente SESC-SP** | ~40 unidades no estado | CSV curado manualmente a partir de sescsp.org.br (nome, cidade, site da unidade, contato institucional) | Grátis | 5 | **MVP (E17)** | ⏳ E01 |
| 4 | **IBGE — municípios** | 5.570 municípios, códigos, regiões imediatas/intermediárias; coordenadas | API de localidades do IBGE / tabelas públicas de centróides | Grátis | 5 | **MVP (E12)**: geografia | ⏳ E12 |
| 5 | **Receita Federal — Dados abertos do CNPJ** (`arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/`, também em dados.gov.br) | Todas as empresas: CNAE, município, porte, situação, e-mail/telefone cadastrais | Download mensal (CSV em partes; completo ~60 GB comprimido). Filtrar só `Estabelecimentos` por município/CNAE. Espelhos: Casa dos Dados, CNPJ Aberto | Grátis | 5 | **Fase 4 (E25)** | — |
| 6 | **OpenStreetMap (Overpass API)** | Estabelecimentos com nome, endereço, telefone, site (quando mapeados) | Overpass QL; política: poucos pedidos/dia na instância pública; ODbL (atribuição) | Grátis | 3 | Complemento para empresas locais (cobertura incerta em Araraquara) | — |
| 7 | **Site da própria organização** | Contatos institucionais, oferta (etapas, cursos), sinais | PoliteFetcher (≤ 5 páginas/site) | Grátis | 4 | **MVP (E19)** contatos; sinais de necessidade (E26) | — |
| 8 | **API de busca web** (Brave Search / Serper) | Descobrir o site oficial de uma organização | Query `"<nome>" <cidade>` com cache permanente | Brave: US$5 crédito/mês (~1.000 buscas); Serper: 2.500 grátis e depois ~US$1/1k | 3 | **MVP (E18)** | — |
| 9 | e-MEC (cadastro de IES) | Universidades/faculdades | Consulta pública | Grátis | 5 | Pós-MVP: parcerias, eventos | — |
| 10 | Google Places API | Estabelecimentos locais | API paga; cotas grátis por SKU (ex. 5.000 Text Search Pro/mês), depois ~US$32–35/1.000; termos restringem armazenamento de dados (exceto `place_id`) | Cota grátis → caro | 4 | **Evitar** como base; uso pontual se necessário | — |

## Organizações parecidas com o SESC (trilha E17b)

Critério de "parecida": oferece educação não formal/cultural ao público, contrata
oficineiros/instrutores externos e tem unidades na região. Lista semente curada à mão
(CSV com URL oficial de cada unidade) + monitoramento das páginas de chamamento/credenciamento.

| Rede/organização | O que procurar | Método | Confiab. | Validado |
|---|---|---|---|---|
| **SESC-SP** (todas as unidades) | Unidades, programação, credenciamento/chamamentos, contatos institucionais | Seed CSV + `html_watch` | 5 | ⏳ E01 |
| SENAC-SP | Cursos livres de tecnologia/games, parcerias | Seed CSV | 5 | ⏳ E01 |
| SESI-SP / SENAI-SP | Atividades de tecnologia/robótica em escolas SESI; eventos | Seed CSV | 5 | ⏳ E01 |
| Oficinas Culturais do Estado de SP (Poiesis) | Oficinas culturais; chamadas de propostas de oficineiros | `html_watch` | 5 | ⏳ E01 |
| Fábricas de Cultura / MIS-SP (seleção de projetos) | Programação formativa; seleção de projetos | `html_watch` | 5 | ⏳ E01 |
| Centro Paula Souza (ETECs/FATECs) e IFSP (campi da região) | Eventos, semanas de tecnologia, extensão, parcerias | Seed CSV + `html_watch` | 5 | ⏳ E01 |
| Secretarias municipais de cultura/educação, bibliotecas, casas de cultura (polos) | Editais de oficinas culturais (ex.: prefeituras que contratam oficinas por edital) | Querido Diário + `html_watch` | 4 | ⏳ E01 |
| Museus/centros de ciência, ONGs educativas | Oficinas de tecnologia | Seed CSV | 3–4 | — |

## Não usar

| Fonte | Motivo |
|---|---|
| Raspagem do Google Maps / Google Search | Viola termos; bloqueios; risco jurídico |
| Raspagem do LinkedIn (perfis, empresas) | Viola termos de uso; dados pessoais. Humano pode consultar manualmente |
| Bases compradas de contatos pessoais | LGPD e reputação |
| Instância pública de SearXNG em produção | Motores bloqueiam após uso contínuo (captcha); instável. Auto-hospedado só como experimento |

## Referências

- CNPJ: https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/ ; https://dados.gov.br/dados/conjuntos-dados/cadastro-nacional-da-pessoa-juridica---cnpj ; https://github.com/rictom/cnpj-sqlite
- INEP Catálogo de Escolas: https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/inep-data/catalogo-de-escolas
- INEP Microdados: https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-escolar
- Overpass API e política de uso: https://wiki.openstreetmap.org/wiki/Overpass_API ; https://operations.osmfoundation.org/policies/api/
- Google Places pricing (2026): https://www.safegraph.com/guides/google-places-api-pricing/
- SearXNG bloqueios: https://apiserpent.com/blog/searxng-self-hosted-serp-api-tested
