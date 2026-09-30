# Análise de negócio — Scorpion Bits

> Levantamento: 30/09/2026 (E00 + complemento do mesmo dia). Hipóteses marcadas como tal.

## Situação

- Estúdio de jogos/tecnologia em estágio inicial, **formalizado como MEI** (CNPJ disponível).
- Domínio próprio: **scorpionbits.com** (app futuro em subdomínio, ex. `app.` ou `prospeccao.`).
- **Portfólio público**: AstroDash, Tirania, um protótipo de jogo, jogos publicados no itch.io
  (URLs a registrar na E01b). Capacidade técnica: Godot, web/software.
- **SESC é hipótese validada**: curso/experiência de ensino de desenvolvimento de jogos
  (Game Lab) já realizado com o SESC; **propostas já enviadas** a unidades de Bauru,
  Ribeirão Preto e São Carlos.
- Localização: Araraquara/SP. Polos com relevância comercial já demonstrada: Araraquara,
  São Carlos, Ribeirão Preto, Bauru. Clientes de software/web/jogos podem estar em qualquer lugar.

## Linhas de receita, ordenadas por chance de receita no curto prazo

| # | Linha | Comprador | Ticket (hipótese) | Ciclo | Diferencial SB | Observações |
|---|---|---|---|---|---|---|
| 1 | **Cursos/oficinas em unidades SESC** | Técnicos de programação/educação das unidades | Médio, recorrente | Meses (programação semestral — confirmar) | **Muito alto** (Game Lab realizado) | Acompanhar propostas em andamento; mapear demais unidades do SESC-SP |
| 2 | **Organizações parecidas com o SESC** | Sistema S (SENAC, SESI, SENAI), Oficinas Culturais do Estado (Poiesis), Fábricas de Cultura, Centro Paula Souza (ETECs/FATECs), IFSP, secretarias municipais de cultura/educação, bibliotecas, museus de ciência | Médio | Meses; algumas por edital/chamamento | Alto (mesmo modelo educacional + case SESC) | Várias contratam oficineiros por **chamamento público** → aparecem em diários oficiais/editais |
| 3 | Extracurricular em escolas particulares | Direção/coordenação pedagógica | Médio, recorrente | Planejamento anual **out–dez** | Médio-alto (case SESC + jogos atraem alunos) | INEP lista escolas e etapas |
| 4 | Editais culturais e de inovação | ProAC (inclui linha de **jogos eletrônicos** — ex. edital 05/2026), PNAB, FAPESP, Sebrae | Alto e pontual | Meses | Médio | Requisitos de PJ: tempo de sede/CNPJ, natureza jurídica, CNAE → elegibilidade por perfil (ADR-013) |
| 5 | Oficinas/cursos para prefeituras | Secretarias | Médio | Longo (licitação/dispensa/chamamento) | Médio | MEI pode licitar; contratações até R$ 80 mil podem ser exclusivas ME/EPP/MEI |
| 6 | Game jams / hackathons | — | Baixo/variável | Curto | Alto | Portfólio, visibilidade, networking |
| 7 | Jogos educativos/institucionais, gamificação | Empresas, ONGs, órgãos, editoras | Alto | Longo | Médio (AstroDash/Tirania como prova) | Agências como canal |
| 8 | Sites, landing pages, sistemas | PMEs em qualquer lugar | Baixo–médio | Curto–médio | Baixo/médio (portfólio web ainda a construir) | Sinais de necessidade (Fase 4) |

## Implicações para o produto

1. **Memória comercial no MVP** (ADR-012): registrar Game Lab e as propostas SESC; o sistema
   nunca "redescobre" quem já foi contatado e lembra follow-ups.
2. **Rede SESC + similares** como trilha prioritária de leads (E17/E17b), antes da base de escolas completa.
3. **Portfólio como evidência** (ADR-012): cada match cita o trabalho que prova a capacidade
   (Game Lab → cursos; AstroDash/Tirania → jogos; sites futuros → web).
4. **Elegibilidade real do MEI** (ADR-013): o digest mostra oportunidades bloqueadas por
   requisito (ex. "sede há mais de 2 anos") — insumo para decidir quando migrar para ME.
5. **Limite do MEI** (R$ 81 mil/ano em 2026): contratos grandes exigiriam mudar de regime —
   mostrar como alerta, não bloquear.
6. **Sazonalidade escolar**: janela 2027 aberta agora (out–dez/2026) → prospecção manual de
   escolas em paralelo e trilha de leads antecipada no plano.

## Perguntas em aberto (para o humano) — também em `docs/plan/STATUS.md`

- Qual unidade SESC realizou o Game Lab, quando, quantos alunos? (vira `PortfolioItem` + `Interaction`)
- Datas, contatos (cargo) e status das propostas a Bauru, Ribeirão Preto e São Carlos.
- URLs públicas de AstroDash, Tirania, protótipo e da página no itch.io.
- Data de abertura e CNAEs do MEI (para elegibilidade).
- E-mail em `@scorpionbits.com` para User-Agent e digest.
- Raio aceitável para cursos presenciais além dos polos (proposta: interior até ~150 km).
- Teto mensal de dinheiro novo com APIs (proposta: US$ 5).

## Atualização E01b (2026-09-30) — respostas do titular

- **Game Lab**: realizado no **SESC Araraquara** (data, nº de alunos e cargo do contato: pendentes).
- **Propostas** a SESC Bauru, Ribeirão Preto e São Carlos: existem; datas, canais, cargos, serviço
  proposto e status: pendentes (template em `data/seeds/interactions.template.csv`).
- **Portfólio público**: site scorpionbits.com; jogos Tirania e AstroDash no itch.io (URLs em `data/seeds/portfolio.csv`); protótipo sem URL.
- **MEI** aberto em 10/04/2025 (≈ 17 meses hoje; **2 anos em 10/04/2027**). Atividade principal:
  ensino de arte e cultura; secundárias incluem treinamento em informática. Desenvolvimento de
  software/web/jogos eletrônicos **não constam** (ADR-015).
- **Consequência**: a prioridade do MVP (cursos/oficinas em SESC, similares e escolas) é exatamente
  o que o enquadramento atual cobre. Editais que exigem 2 anos de sede (ex. ProAC 05/2026 de jogos
  eletrônicos) só ficam elegíveis a partir de abril/2027 — o radar deve avisar quando a próxima
  edição sair.
