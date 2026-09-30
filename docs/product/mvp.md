# MVP

## Pergunta que o MVP precisa responder

> **"A Scorpion Bits consegue usar esta plataforma para encontrar oportunidades
> comerciais reais que não encontraria facilmente manualmente?"**

Critério de sucesso (avaliado na etapa **E22**, após ~4 semanas de uso real):

1. Em 4 semanas, o radar mostrou **≥ 10 oportunidades/leads marcados como "interessante"**
   pelo humano, dos quais **≥ 5 não estavam no radar manual** (baseline coletado na E01).
2. **≥ 3 ações concretas** tomadas a partir do radar (inscrição, contato, proposta).
3. Tempo semanal de triagem **≤ 30 min** (o digest resolve; não precisa garimpar).
4. Custo variável **≤ US$ 10/mês**.

Se falhar: documentar por quê (fontes ruins? score ruim? segmento errado?) e decidir
entre ajustar ou parar — registrado em ADR.

## Por que este recorte

A tração existente é **educação presencial (SESC)**. Os leads com maior chance de gerar
receita no curto prazo são **SESCs e escolas particulares da região**, e as oportunidades
de menor custo de entrada são **editais, game jams e hackathons**. Empresas (via CNPJ)
para software/web ficam para depois do MVP porque exigem base pesada (dezenas de GB),
têm concorrência alta e sinal de necessidade mais fraco.

Observação de calendário: escolas planejam atividades extracurriculares do ano seguinte
entre **outubro e dezembro**. O MVP deve priorizar a trilha de escolas cedo o bastante
para aproveitar o ciclo 2027 — ou, se não der tempo, a Scorpion Bits deve prospectar
escolas manualmente em paralelo (ver `docs/plan/STATUS.md`, riscos).

## Entra no MVP

**A. Radar de oportunidades (Fase 1)**
- Conectores: hackathons (Devpost), game jams (itch.io), páginas monitoradas
  (FAPESP/PIPE, Sebrae-SP, InovAtiva, ProAC/Secretaria de Cultura SP, Prefeitura de
  Araraquara e vizinhas), diários oficiais municipais (Querido Diário), Mapas Culturais.
- Normalização, deduplicação, histórico de coleta.
- Extração estruturada de editais (prazo, elegibilidade, prêmio, exige CNPJ…) com LLM
  barato/gratuito **e verificação de evidência** (a citação precisa existir no texto).

**B. Priorização (Fase 2)**
- Localização (municípios IBGE + distância) e relevância geográfica por tipo.
- Score explicável v1 com gates (prazo vencido, inelegível) e fatores.
- Triagem humana no admin: interessante / descartado (com motivo) / em ação.
- Digest semanal (HTML/Markdown; e-mail opcional só para a própria equipe).
- Agendamento por cron.

**C. Leads institucionais (Fase 3)**
- Escolas privadas da região (INEP) + unidades SESC-SP (lista semente curada).
- Descoberta de site (API de busca com cota gratuita + validação determinística).
- Extração determinística de contatos públicos institucionais do próprio site.
- Matching serviço ↔ organização por regras (catálogo de serviços como dado).
- Score de leads + inclusão no digest.
- Métricas e avaliação do MVP (E22).

**Interface:** Django admin (listas, filtros, busca, edição, "por que este score").
Nenhum frontend customizado.

## Fora do MVP (deliberadamente)

| Item | Por que não agora | Quando reconsiderar |
|---|---|---|
| Envio automático de mensagens | Risco de spam/reputação; volume não justifica | Talvez nunca; no máximo envio 1-a-1 assistido |
| CRM completo | Sem volume de negociações que justifique | Fase 4 (E23), versão mínima |
| Rascunho de mensagens por IA | Primeiro provar que os leads são bons | Fase 4 (E24) |
| Empresas via base CNPJ | Base pesada, sinal fraco, concorrência alta | Fase 4 (E25–E26) |
| Licitações PNCP | Útil, mas exige formalização e é menos provável no curto prazo | Fase 4 (E27) |
| Agente de pesquisa autônomo | Custo imprevisível; pipeline determinístico cobre o MVP | Fase 4 (E28), se dados mostrarem lacuna |
| Multi-agentes, filas, microserviços | Overengineering para 1–3 usuários | Quando houver gargalo medido |
| Embeddings / vector DB / RAG | Palavras-chave + regras bastam para o volume | Se matching por regras falhar comprovadamente |
| Scraping de LinkedIn / Google Maps | Viola termos de uso | Não |
| Descoberta de contatos pessoais | LGPD, risco, pouco valor | Só manual e pontual pelo humano |
| Dashboards | O digest semanal e o admin bastam | Quando houver métricas que ninguém consegue ver |
| Oportunidades internacionais presenciais | Fora da capacidade atual | Pós-MVP; online já entram via Devpost/itch.io |
| Deploy compartilhado com auth externa | Pode rodar local no MVP | Fase 4 (E29) |
