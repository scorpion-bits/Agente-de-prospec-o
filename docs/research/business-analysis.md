# Análise de negócio — Scorpion Bits

> Levantamento: 30/09/2026 (sessão de planejamento). Hipóteses marcadas como tal.

## Situação

- Estúdio independente de jogos/tecnologia, **não formalizado**, sem receita recorrente.
- Ativo mais valioso: **experiência comprovada com o SESC (Game Lab)** — prova social,
  metodologia e material didático reutilizáveis.
- Capacidade técnica: Godot, desenvolvimento web/software.
- Localização: Araraquara/SP (região central do estado, perto de São Carlos — polo
  universitário/tecnológico — e Ribeirão Preto).

## Linhas de receita, ordenadas por chance de receita no curto prazo

| # | Linha | Comprador | Ticket (hipótese) | Ciclo | Diferencial SB | Observações |
|---|---|---|---|---|---|---|
| 1 | Cursos/oficinas em outras unidades SESC | Técnicos de programação/educação das unidades | Médio, recorrente | Meses (programação semestral) | **Alto** (case Game Lab) | ~40 unidades no estado de SP; verificar se há credenciamento/chamamento de oficineiros (E01) |
| 2 | Extracurricular em escolas particulares | Direção/coordenação pedagógica | Médio, recorrente (mensal por turma) | Planejamento anual **out–dez** | Médio-alto (jogos atraem alunos; case SESC) | Concorre com robótica/programação; INEP lista escolas e etapas de ensino |
| 3 | Editais culturais e de inovação | Poder público, fundações (ProAC, PNAB, FAPESP, Sebrae) | Alto e pontual | Meses | Médio | **Muitos exigem CNPJ/MEI** e histórico; jogos são reconhecidos em alguns editais de cultura |
| 4 | Oficinas/cursos para prefeituras, bibliotecas, secretarias | Secretarias de educação/cultura | Médio | Longo (licitação/dispensa/chamamento) | Médio | Diários oficiais e PNCP revelam demandas |
| 5 | Game jams / hackathons | — (prêmios, visibilidade) | Baixo/variável | Curto | Alto (é o que sabemos fazer) | Portfólio, networking, eventualmente contratação |
| 6 | Jogos educativos/institucionais, gamificação | Empresas, ONGs, órgãos, editoras | Alto | Longo | Médio | Precisa de portfólio; agências são possíveis parceiras/canais |
| 7 | Sites, landing pages, sistemas | PMEs locais e remotas | Baixo–médio | Curto–médio | Baixo (mercado saturado) | Sinais determinísticos de necessidade (site ausente/antigo) ajudam; Fase 4 |

## Implicações para o produto

1. **O MVP deve servir primeiro às linhas 1, 2, 3 e 5** (alto encaixe, fontes públicas boas).
2. **Sazonalidade escolar**: hoje é 30/09/2026 → a janela de planejamento 2027 das escolas
   está aberta. Recomenda-se prospecção **manual em paralelo** enquanto o radar é construído.
3. **Formalização** é uma variável de negócio que o radar deve tornar visível: o digest
   deve somar "valor de oportunidades que exigem CNPJ" para informar essa decisão.
   (Nota: verificar se as atividades de desenvolvimento de jogos/cursos se enquadram
   em MEI ou exigem outra natureza jurídica — decisão fora do escopo do software.)
4. **Canais/parcerias** (agências, escolas de idiomas/cursos livres, coworkings,
   incubadoras de São Carlos/Araraquara) podem valer mais que clientes finais — o modelo
   de dados trata "parceiro" como um tipo de match, não só "cliente".
5. **Portfólio é moeda**: jams/hackathons têm valor estratégico mesmo sem prêmio;
   o fator Valor considera benefícios não monetários.

## Perguntas em aberto (para o humano)

Registradas também em `docs/plan/STATUS.md`:
- Quantas pessoas usarão o sistema e em que máquina ele vai rodar?
- Existe e-mail/domínio institucional da Scorpion Bits (para User-Agent e contato)?
- Qual o raio máximo aceitável para cursos presenciais recorrentes (hipótese: 120 km)?
- Qual teto de gasto mensal com APIs (hipótese: US$ 5–10)?
- Há intenção/plano de formalização (MEI/ME) e em que prazo?
- Quais unidades SESC já foram contatadas e com que resultado?
