# Visão do produto

## Em uma frase

Um **radar comercial** que, toda semana, mostra à Scorpion Bits as poucas oportunidades
que mais valem o tempo dela — com fonte, justificativa e próximo passo — em vez de uma
planilha com centenas de nomes.

## Problema

A Scorpion Bits é pequena, sem caixa e sem equipe comercial. Hoje, encontrar
oportunidades depende de busca manual e esporádica:

- editais, game jams e hackathons aparecem em dezenas de sites diferentes e passam do prazo
  antes de serem vistos;
- escolas e instituições que poderiam contratar cursos existem, mas ninguém mapeou quais,
  onde, com quem falar e em que época do ano;
- não há critério para decidir "vale a pena gastar tempo nisso?".

## Para quem

Usuários internos (1–3 pessoas da Scorpion Bits). Não é produto SaaS. Não há clientes
externos usando a plataforma.

## O que o produto faz (visão de longo prazo)

1. **Descobre** oportunidades e organizações em fontes públicas e confiáveis.
2. **Pesquisa** cada item: o que é, onde fica, quem é, como contatar — sempre com fonte.
3. **Qualifica e relaciona** a necessidade provável da organização com o serviço da
   Scorpion Bits que a atende e com o **trabalho do portfólio que prova a capacidade**
   ("Escola X → curso extracurricular de jogos, porque…; referência: Game Lab SESC").
4. **Prioriza** com pontuação explicável e relevância geográfica contextual.
5. **Prepara** o contato (mensagem personalizada) — humano revisa e envia.
6. **Lembra** de tudo: com quem já falamos, quando, sobre o quê, resultado e próximo passo
   (memória comercial desde o MVP); evolui para um funil leve e mede o que gera receita.

## O que o produto NÃO é

- Não é disparador de e-mails/WhatsApp em massa.
- Não é base de dados pessoais nem ferramenta de enriquecimento de pessoas.
- Não é uma "empresa de IA": IA é ferramenta pontual, não o produto.

## Princípio de evolução

```
MVP (memória comercial + portfólio + leads SESC/escolas + radar de oportunidades + score)
 → pipeline leve → preparação de abordagem
 → empresas (CNPJ) e sinais de necessidade → agentes sob demanda → automações
 → inteligência comercial (aprendizado com resultados)
```

Cada passo só começa quando o anterior provou valor pelas métricas de `metrics.md`.

## Contexto de negócio

Análise completa em `docs/research/business-analysis.md`. Resumo:

| Linha | Por que importa agora | Proximidade importa? |
|---|---|---|
| Cursos/oficinas em SESCs | **Validado**: Game Lab realizado; propostas enviadas a Bauru, Ribeirão Preto e São Carlos | Alta (presencial; polos) |
| Organizações parecidas com o SESC | Mesmo modelo educacional (Sistema S, Oficinas Culturais, ETECs/IFSP…) | Alta (presencial) |
| Escolas particulares (extracurricular) | Mercado grande e local; ciclo anual de planejamento (out–dez) | Alta |
| Editais (cultura, inovação, educação) | Dinheiro não reembolsável; empresa é MEI → elegibilidade por requisito | Depende da abrangência |
| Game jams / hackathons | Portfólio, visibilidade, prêmios; baixo custo | Baixa (maioria online) |
| Software/web para empresas | Mercado enorme, concorrência alta | Baixa |
| Jogos educativos / gamificação para empresas e instituições | Ticket maior, ciclo longo; AstroDash/Tirania como prova | Baixa |
