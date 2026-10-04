# ADR-046 — Rascunho de abordagem: fatos com origem, validador, `rules` como piso, nada enviado

- **Status:** aceito
- **Data:** 2026-10-04

## Contexto
A E24 do plano (rascunho de abordagem assistido) depende formalmente do go/no-go da E22 (P28). Mas toda a parte de código (fatos, validador,
modelo, admin) roda com `FakeProvider`, e só o A/B com modelos reais precisa de chave paga e de dados. Dá para construir agora e **adotar** só
se a decisão for «continuar». Risco central: texto lido por clientes com afirmação inventada.

## Decisão
1. **Fatos antes de texto** (`core/services/outreach.py`). O modelo recebe só uma lista de fatos com id (`F1…`) e tipo: apresentação da
   Scorpion Bits (`intro`), registro da organização (`record`), evidência **observada** com trecho (`observed`; nunca `contact.*`), serviço
   (`offer`), hipótese do match (`hypothesis`, marcada «não confirmada»), trabalhos de portfólio **públicos e confirmados** (`portfolio`, com
   link) e histórico de interações (`history`: data, tipo, serviço, resultado; **sem o texto livre** do resumo). Inferência nunca vira fato (ADR-004).
2. **Saída com afirmações ligadas a fatos**: `{subject, body, claims[{text, about, facts[]}]}`. `about` (`recipient`/`scorpion`/`offer`/`history`)
   exige fato do tipo certo: algo sobre o destinatário só se apoia em registro ou observado, nunca em hipótese ou portfólio.
3. **Validador determinístico** (`validate_draft`): afirmação sem fato, fato inexistente ou de tipo errado; **link** que não está nos fatos;
   **número** que não está nos fatos; e-mail/telefone no texto; tamanho; assunto no WhatsApp. Limite assumido: não prova que cada frase do
   corpo está em `claims` nem que a paráfrase é fiel; a leitura humana continua obrigatória.
4. **Estratégias da tarefa `draft_outreach`**: `gemini-paid:gemini-3.1-pro`, `anthropic:claude-sonnet-5-5`, `rules` (modelo de texto sem IA,
   sempre válido). Rascunho rejeitado cai para a próxima; o motivo fica em `attempts`. `LLM_TASK_STRATEGIES` troca a lista. Dado do histórico é
   `internal`: só provedor pago ou local, nunca free tier (llm-strategy.md).
5. **A/B**: `make draft ORG="…" CMP=1` roda cada estratégia **sozinha, sem fallback** e grava também o rejeitado; o humano avalia no admin
   (`rating`: usável / reescrever / inútil) e `make draft REPORT=1` resume por estratégia (válidos, usáveis, custo médio). Empate → Gemini (ADR-011).
6. **Humano no controle** (ADR-005): o sistema só grava `OutreachDraft` (migration `core.0007`). Não envia, não lê contatos, não cria
   `Interaction`. Organização em opt-out/«não contatar» não gera rascunho. Quem já recebeu proposta do mesmo serviço recebe texto de retomada
   (não repete a oferta).
7. Ação «Gerar rascunho de abordagem» na organização (até 5 por vez, e-mail, serviço do melhor match) e `make draft`.

## Consequências
- `rules` é o piso e a linha de base do A/B: se os modelos não ganharem do modelo de texto, a IA não se paga (ADR-003).
- Prompt versionado em `core/prompts/draft_outreach_v1.txt` (`PROMPT_VERSION` invalida o cache).
- Nenhuma chamada real foi feita; preços de `gemini-3.1-pro`/`claude-sonnet-5-5` vêm de `llm/pricing.py` (P21/P34 pedem conferir).
- Pendente: canal WhatsApp só foi exercitado com `rules`; sem integração com `Deal` além de o rascunho citar o histórico da organização.
