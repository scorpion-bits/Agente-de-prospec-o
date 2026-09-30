# Ferramentas de prospecção existentes — o que aprender

> Levantamento: 30/09/2026. Objetivo: entender padrões, não copiar ferramentas.

## Categorias e exemplos

| Categoria | Exemplos | Problema que resolvem | Como fazem | Custo típico |
|---|---|---|---|---|
| Bases B2B brasileiras (CNPJ) | Speedio, Econodata, Casa dos Dados, CNPJ.biz, Data Stone | "Liste empresas do CNAE X na cidade Y" | Base aberta da Receita Federal + filtros + enriquecimento (telefones, sites, sócios) | Freemium a centenas de R$/mês |
| Bases B2B globais | Apollo, ZoomInfo, Lusha | Contatos de decisores | Bases proprietárias de pessoas (crowdsourcing, extensões de navegador) | US$ 50–500+/usuário/mês |
| Enriquecimento orquestrado | Clay | "Para cada empresa, rode 10 fontes e um LLM" | Planilha com colunas = chamadas a APIs/LLMs em cascata ("waterfall") | Créditos; caro em escala |
| Agentes SDR com IA | 11x, Artisan, AiSDR e similares | Prospecção + envio automático | LLM gera e envia sequências em massa | Alto; risco reputacional |
| Engajamento/sequências | Apollo, Lemlist, Reply | Cadências de e-mail | Automação de envio | US$ 30–100/usuário/mês |
| CRMs | HubSpot (free), Pipedrive, RD Station CRM | Funil e histórico | Pipeline + atividades | Grátis a moderado |
| Radares de editais | Portais agregadores (ex.: Prosas, sites de "editais abertos"), newsletters, Confap | "Quais editais estão abertos para mim?" | Curadoria manual + busca | Grátis a assinatura |
| Agregadores de hackathons/jams | Devpost, itch.io/jams, MLH, Hackathon.com | Descoberta de eventos | Plataformas onde organizadores publicam | Grátis |
| Diários oficiais | Querido Diário (Open Knowledge Brasil) | Busca textual em diários municipais | Raspadores abertos + API pública | Grátis |

## Funcionalidades realmente importantes (e o que faremos)

| Funcionalidade | Importância para nós | Decisão |
|---|---|---|
| Filtro por segmento + localização | Alta | Sim — INEP (escolas), seeds (SESC), CNPJ na Fase 4 |
| Deduplicação e histórico | Alta | Sim, desde o início |
| Enriquecimento em cascata (waterfall) | Média | Versão simples: fonte oficial → site próprio → busca (cota grátis). Sem APIs pagas de contato |
| Pontuação de fit/intenção | Alta | Sim, determinística e explicável |
| Sinais de intenção (notícias, vagas, mudanças) | Média | Pós-MVP; sinais baratos (site ausente/antigo, edital publicado no diário) primeiro |
| Contatos de decisores (pessoas) | Baixa-média | **Não automatizar.** Humano busca pontualmente, quando o lead é priorizado |
| Sequências automáticas de e-mail | Baixa | **Não.** Rascunho assistido, envio manual (ADR-005) |
| Pipeline/CRM | Média | Mínimo na Fase 4; alternativa: HubSpot/Pipedrive free se o nosso não bastar |
| Alertas de oportunidades | Alta | Digest semanal (e diário para prazos curtos, se necessário) |

## O que é caro e não vale agora

- Bases proprietárias de contatos pessoais (Apollo/ZoomInfo/Lusha): caro, pouco útil
  para escolas/SESC brasileiros, risco LGPD.
- Plataformas de agentes SDR: contrárias ao princípio anti-spam.
- Clay-like waterfall com muitas APIs pagas: custo por lead alto para nosso volume.
- Google Places API como fonte principal: US$ 32–35 por 1.000 buscas acima da cota
  gratuita e termos restringem armazenamento; usar só pontualmente, se necessário.

## O que é simples e dá muito valor

- Dados abertos oficiais (INEP, Receita/CNPJ, IBGE) + filtros locais.
- APIs públicas de oportunidades (Devpost, Querido Diário, Mapas Culturais, PNCP).
- Monitor de páginas de editais (diff) — barato e eficaz.
- Extração de contatos do próprio site da organização (regex).
- Score explicável + digest semanal curto.

## Alternativa "comprar em vez de construir" (considerada)

Para a trilha de empresas (Fase 4), avaliar antes de construir: o freemium de
Casa dos Dados/Econodata pode bastar para listas pequenas. Registrar decisão em ADR na E25.
