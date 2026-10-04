# Fase 4 — Pós-MVP (condicionada à E22)

> Estas etapas só começam se a E22 recomendar. A E22 pode reordená-las ou cortá-las.
> Nível de detalhe menor de propósito: refinar cada etapa (mesmo template) antes de executá-la.
> Ordem sugerida: **E27 (PNCP, viável com MEI)** → E23 → E24 → E29 → demais conforme a E22.

## E23 — Pipeline leve (feita em 2026-10-04, ADR-045; adoção depende do go/no-go)
**Objetivo:** acompanhar contatos até o fechamento sem planilha paralela.
**Resultado esperado:** `Deal` (organização + serviço + estágio: Interessante → Contato →
Respondeu → Reunião → Proposta → Negociação → Fechado/Perdido, valor estimado) agrupando as
`Interaction`s que já existem desde a E03b; funil no `metrics`; `Suppression` gerenciável no
admin; limite de follow-ups (2) e intervalo (7 dias) com alerta.
**Dependências:** E22. **Modelo (dev):** Sonnet 5.5. **IA runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** média.
**Riscos:** virar CRM gigante → só os campos acima; alternativa avaliada: HubSpot/Pipedrive free.
**Testes/Critério:** mover um lead por todo o funil no admin; métricas de funil no `metrics`.

## E24 — Rascunho de abordagem assistido
**Objetivo:** reduzir o tempo de escrever a primeira mensagem, sem inventar nada.
**Resultado esperado:** ação "Gerar rascunho" num lead → texto curto (e-mail ou
WhatsApp) + lista de afirmações com evidência; humano edita e copia. Entrada: evidências da
organização, match, **itens de portfólio a citar** (links públicos) e **histórico de
interações** (não repetir proposta já feita). Texto fixo de apresentação da Scorpion Bits
(`scorpionbits.com`) como prefixo cacheável.
**Dependências:** E23, E10. **Modelo (dev):** Sonnet 5.5.
**IA runtime:** A/B com 10 casos: Claude Sonnet 5.5 × Gemini 3.1 Pro (projeto pago com créditos
do AI Pro); empate → Gemini (ADR-011). Dados `internal` → só provedores pagos.
**Justificativa:** texto lido por clientes — qualidade importa; volume baixo.
**Custo:** ~US$ 0,01/rascunho (< US$ 1/mês). **Complexidade:** média.
**Riscos:** afirmação sem evidência → validador rejeita frases que citam fatos não presentes nas evidências; tom genérico → exemplos no prompt.
**Critério:** 10 rascunhos avaliados pelo humano; ≥ 7 usáveis com edição leve; toda afirmação sobre o destinatário tem evidência.

## E25 — Empresas via dados abertos do CNPJ
> **Feita em 2026-10-04 (ADR-043)** com fixture sintética (conector de arquivo local, sem dado pessoal); layout e tempo reais no P31.

**Objetivo:** base de empresas ativas da região por CNAEs mapeados a serviços
(agências de marketing/publicidade → jogos para campanhas/parceria; escolas de idiomas,
cursos livres → cursos/gamificação; editoras/educação → jogos educativos; comércio/serviços
locais → sites).
**Resultado esperado:** import dos arquivos `Estabelecimentos` filtrados por município (R0–R2)
e situação ativa; mapeamento CNAE → serviço em dados; e-mail/telefone **cadastrais** tratados
como contatos de baixa confiança.
**Decisão prévia (ADR):** construir vs. usar freemium (Casa dos Dados/Econodata) para listas pequenas.
**Dependências:** E22, E12. **Modelo (dev):** Opus 5.5 (volume de dados, desempenho).
**IA runtime:** nenhuma. **Custo:** US$ 0 (disco/tempo: filtrar em streaming, DuckDB pontual).
**Complexidade:** alta. **Riscos:** tamanho dos arquivos; dados cadastrais desatualizados; dados de MEI são de pessoa física → cuidado LGPD (não importar nome/CPF de sócios).
**Critério:** empresas da região por CNAE carregadas em < 30 min; amostra de 20 conferida.

## E26 — Sinais de necessidade web
> **Feita em 2026-10-04 (ADR-042)**, antes do go/no-go por não depender de dados reais; só página inicial, ainda fora do score e do pipeline (P30).

**Objetivo:** identificar empresas/instituições que provavelmente precisam de site/sistema.
**Sinais determinísticos:** sem site; site fora do ar; sem HTTPS; não responsivo (meta viewport ausente);
copyright antigo (ex. © 2015); só página de rede social; tecnologia obsoleta (Flash, jQuery muito antigo).
**Dependências:** E25 ou E18. **IA runtime:** nenhuma. **Custo:** US$ 0. **Complexidade:** média.
**Riscos:** falso positivo (site simples mas adequado) → sinal é fator de Fit, não verdade.
**Critério:** sinais como `Evidence(observed)` com URL; amostra conferida.

## E27 — Conector PNCP (contratações públicas)
> **Feita em 2026-10-04 (ADR-041)**, antes do go/no-go por não depender de dados reais; fonte desabilitada até o P29.

**Objetivo:** detectar contratações públicas abertas relacionadas a cursos, oficinas,
desenvolvimento de software/jogos educativos, sites.
**Resultado esperado:** `/contratacoes/proposta` filtrado por palavras-chave/modalidade/UF →
`Opportunity(kind=procurement)`; reusa extração da E11.
**Dependências:** E22, E11. **IA runtime:** reusa E11. **Custo:** ~US$ 0. **Complexidade:** média.
**Riscos:** habilitação exigida (documentos, atestados de capacidade técnica) → extrair como
requisito; volume alto → filtros por UF SP e termos. Vantagem: cotas exclusivas ME/EPP/MEI até R$ 80 mil (ADR-013).

## E28 — Agente de pesquisa sob demanda (condicional)
**Condição:** E22 mostrar que leads/oportunidades de alto valor ficam sem informação suficiente.
**Objetivo:** botão "Pesquisar a fundo" que roda um agente com ferramentas restritas
(`search_web`, `fetch_page`, `get_known_facts`, `propose_evidence`) e teto rígido de custo;
resultados são **propostas** de evidência para aprovação humana.
**Dependências:** E10, E22. **Modelo (dev):** Opus 5.5 (carregar skill `claude-api` se usar Claude).
**IA runtime:** comparar Gemini (Flash/Pro) com Search grounding (cota grátis de ~5 mil/mês;
conferir termos de armazenamento) × Claude Sonnet 5.5 + API de busca; teto ~US$ 0,50/execução e
~US$ 10/mês. Até esta etapa existir: Gemini Deep Research manual (assinatura AI Pro).
**Complexidade:** alta. **Riscos:** custo (teto), alucinação (verificação de citação + aprovação), loops (máx. N passos).
**Critério:** 5 execuções avaliadas: evidências novas úteis em ≥ 3; custo dentro do teto.

## E29 — UI online em `app.scorpionbits.com`
> **Parte feita (2026-10-04, ADR-047):** o **admin** já tem Dockerfile, settings de produção e deploy manual no Cloud Run (`docs/operations/hosting.md`, P35). Resta a UI web nova (front + API, ADR-019) e, se preciso, camada extra de acesso.
**Objetivo:** acesso de 2–3 pessoas de qualquer lugar (inclusive não desenvolvedores) com segurança.
**Resultado esperado:** Django em container no **Google Cloud Run** (escala a zero; free tier +
créditos do AI Pro), domínio `app.scorpionbits.com` ou `prospeccao.scorpionbits.com` (DNS do
domínio existente), HTTPS gerenciado, estáticos via WhiteNoise, segredos no Secret Manager,
banco continua no Supabase. Usuários Django com senha forte + camada extra opcional
(Cloudflare Access ou IAP). Reavaliar Supabase Pro (US$ 25) para backups gerenciados.
**Alternativas registradas (ADR-010):** Vercel Pro + front Next.js + Supabase Auth (se precisar de
UI além do admin; ~US$ 20/membro); VPS (US$ 5–10). Vercel Hobby **não** (uso comercial).
**Dependências:** E22. **Modelo (dev):** Sonnet 5.5. **Custo:** US$ 0–5/mês. **Complexidade:** média.
**Riscos:** exposição do admin → camada extra de acesso; cold start → aceitável para uso interno.

## E30 — Calibração de pesos
> **Ferramenta feita em 2026-10-04 (ADR-044, `make calibrate`)**; a calibração em si espera ≥ 50 triagens reais (P32).

**Objetivo:** ajustar pesos do score com base na triagem real (≥ 50 itens triados).
**Resultado esperado:** relatório comparando fatores entre interessantes e descartados;
proposta de novos pesos; nova `scoring_version`; ADR.
**Dependências:** E14 com dados. **IA runtime:** nenhuma. **Custo:** US$ 0. **Complexidade:** baixa.
**Critério:** precisão do topo (M2) melhora na simulação retroativa sem piorar M3.

## Ideias registradas (sem etapa ainda)
- Envio 1-a-1 assistido por e-mail com domínio próprio (só se ADR-005 for revisto).
- Embeddings para matching semântico (só se regras falharem comprovadamente).
- Oportunidades internacionais presenciais.
- Alertas diários para prazos curtos (< 7 dias).
- Aprendizado com respostas/fechamentos (quais segmentos convertem).
