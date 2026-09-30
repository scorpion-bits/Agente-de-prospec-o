# MVP

## Pergunta que o MVP precisa responder

> **"A Scorpion Bits consegue usar esta plataforma para encontrar oportunidades
> comerciais reais que não encontraria facilmente manualmente?"**

Critério de sucesso (avaliado na etapa **E22**, após ~4 semanas de uso real):

1. Em 4 semanas, **≥ 10 oportunidades/leads marcados como "interessante"**, dos quais
   **≥ 5 não estavam no baseline manual** (coletado na E01).
2. **≥ 3 ações concretas** a partir do radar (inscrição, contato, proposta).
3. **Memória em dia**: 100% das propostas/contatos da semana registrados; nenhum follow-up
   vencido sem decisão.
4. Triagem semanal **≤ 30 min**.
5. Dinheiro novo gasto **≤ US$ 10/mês**.

Se falhar: documentar por quê (fontes? score? segmento?) e decidir ajustar ou parar — em ADR.

## Por que este recorte

A tração existente é **educação presencial com o SESC** — hipótese **validada** (Game Lab
realizado, propostas enviadas a Bauru, Ribeirão Preto e São Carlos). Os leads com maior
chance de receita no curto prazo são **unidades SESC, organizações parecidas com o SESC e
escolas particulares** dos polos (Araraquara, São Carlos, Ribeirão Preto, Bauru) e interior.
As oportunidades de menor custo de entrada são **editais, game jams e hackathons** — agora
com elegibilidade real, pois a empresa é **MEI** (ADR-013). Empresas via base CNPJ ficam para
depois (ADR-009).

Calendário: escolas planejam o ano seguinte entre **outubro e dezembro** → a trilha de
leads foi antecipada no plano e a prospecção manual deve continuar em paralelo.

## Entra no MVP

**0. Memória comercial e portfólio** (Fase 0 — E03b, primeiro marco útil)
- `Interaction` por organização (propostas, reuniões, curso realizado, próxima ação).
- Importação do histórico existente (Game Lab, propostas SESC).
- `PortfolioItem` (Game Lab SESC, AstroDash, Tirania, protótipo, jogos no itch.io).
- `CompanyProfile` (MEI) para elegibilidade.
- Admin responde: "Já falamos com essa organização? Quando? Sobre o quê? Resultado? Próximo passo?"

**A. Leads institucionais** (Fase 3, antecipada)
- Unidades SESC-SP (rede com unidades) + organizações parecidas com o SESC (Sistema S,
  Oficinas Culturais, ETECs/IFSP, secretarias/bibliotecas dos polos).
- Escolas privadas (INEP) dos polos e interior próximo.
- Site oficial (API de busca com cota grátis + validação) e contatos institucionais públicos.
- Matching serviço ↔ organização por regras, **com item de portfólio como prova**.

**B. Radar de oportunidades** (Fase 1)
- Conectores: Devpost, itch.io, páginas monitoradas (FAPESP, ProAC — inclui linha de jogos
  eletrônicos —, Oficinas Culturais, Sebrae-SP, InovAtiva, prefeituras dos polos), Querido
  Diário, Mapas Culturais.
- Extração estruturada de editais (Gemini, com citação verificada), incluindo requisitos de
  empresa (aceita MEI? tempo mínimo de CNPJ/sede? CNAE? cota ME/EPP?).

**C. Priorização** (Fase 2)
- Geografia contextual com polos prioritários (fator, não filtro).
- Score explicável com elegibilidade MEI, relacionamento e portfólio.
- Triagem humana, digest semanal (top oportunidades, leads, **follow-ups**, prazos,
  oportunidades bloqueadas por requisito da empresa, custos).
- Pipeline agendado no GitHub Actions; banco no Supabase (ADR-010).

**Interface:** Django admin local (sem frontend customizado, sem hospedagem da UI).

## Fora do MVP (deliberadamente)

| Item | Por que não agora | Quando reconsiderar |
|---|---|---|
| Envio automático de mensagens | Risco de spam/reputação | Talvez nunca; no máximo 1-a-1 assistido |
| CRM completo (estágios, valores, funil) | Memória de interações já cobre o essencial | Fase 4 (E23) |
| Rascunho de mensagens por IA | Primeiro provar que os leads são bons | Fase 4 (E24) |
| UI online em `app.scorpionbits.com` | Usuários são devs; admin local basta | Fase 4 (E29) ou quando alguém não técnico precisar |
| Vercel / frontend Next.js | Hobby proíbe uso comercial; admin já resolve | Se houver UI para não-devs (Vercel Pro) |
| Empresas via base CNPJ | Base pesada, sinal fraco | Fase 4 (E25–E26) |
| Licitações PNCP | Viável com MEI, mas MVP precisa ser pequeno | **1ª candidata da Fase 4 (E27)** |
| Agente de pesquisa autônomo | Custo imprevisível | Fase 4 (E28), se houver lacuna medida; enquanto isso, Gemini Deep Research manual |
| Multi-agentes, filas, microserviços, vector DB | Overengineering | Gatilho medido |
| Scraping de LinkedIn / Google Maps | Termos de uso | Não |
| Descoberta de contatos pessoais | LGPD, risco | Só manual e pontual |
| Dashboards | Digest + admin bastam | Quando houver métrica invisível |
| Oportunidades internacionais presenciais | Fora da capacidade atual | Pós-MVP |
