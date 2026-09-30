# ADR-005 — Humano no controle: sem envio automático de mensagens

- **Status:** aceito
- **Data:** 2026-09-30

## Contexto
O objetivo é prospecção profissional, não spam. Empresa pequena depende de reputação
local (escolas, SESC, prefeituras se conhecem). Envio automático cria risco de LGPD,
bloqueio de domínio/número e dano reputacional.

## Decisão
O sistema **recomenda** (quem, por quê, como contatar) e, na Fase 4, **rascunha**
mensagens. O humano revisa e envia manualmente pelos próprios canais. Nenhuma integração
de envio (e-mail em massa, WhatsApp API) no MVP nem na Fase 4.

## Alternativas consideradas
| Alternativa | Por que não |
|---|---|
| Sequências automáticas (tipo Lemlist/Apollo) | Contrário ao princípio anti-spam; volume não justifica |
| Envio 1-a-1 pelo sistema com aprovação | Possível no futuro; hoje copiar/colar custa segundos |

## Consequências
+ Risco jurídico/reputacional mínimo. + Aprendizado direto do humano com cada contato.
− Não escala para centenas de contatos/semana (não é o objetivo).

## Quando revisitar
Se houver > 30 contatos qualificados/semana e o envio manual virar gargalo medido.
Mesmo assim: envio 1-a-1 aprovado, com opt-out, nunca em massa.
