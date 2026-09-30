# ADR-001 — Monólito modular em Python + Django (admin como UI do MVP)

- **Status:** aceito
- **Data:** 2026-09-30
- **Etapa:** E00

## Contexto
Ferramenta interna para 1–3 pessoas, sem orçamento, mantida por equipe mínima que também
faz jogos. Carga principal: coleta web, parsing de HTML/PDF, dados tabulares, chamadas a
LLMs. Precisa de CRUD com filtros, busca, edição e login desde o primeiro dia.

## Decisão
Python 3.12 + Django 5 em um único projeto com apps por módulo (`core`, `collection`,
`extraction`, `llm`, `scoring`, `reports`). **Django admin customizado é a interface do
MVP.** Jobs como comandos `manage.py` agendados por cron.

## Alternativas consideradas
| Alternativa | Prós | Contras | Por que não |
|---|---|---|---|
| Planilha + scripts | Zero infra | Sem dedupe/histórico/evidências; frágil | Não sustenta rastreabilidade e score |
| n8n/Make/Zapier (no-code) | Rápido para fluxos | Lógica de score/dedupe difícil de testar; custo em escala; lock-in | Testabilidade e custo |
| FastAPI + SQLModel + HTMX/React | Leve, moderno | Precisa construir UI, auth, admin do zero | Mais código para o mesmo resultado |
| Node/Next.js + Prisma | Um só idioma web | Ecossistema de scraping/PDF/dados mais fraco que Python | Adequação ao problema |
| Microserviços (coletor, extrator, API, UI) | Escala independente | Operação complexa para 1–3 usuários | Overengineering |
| Godot como UI | Familiaridade | Não é ferramenta para CRUD/web | Não faz sentido |

## Consequências
+ Admin pronto (listas, filtros, busca, ações, permissões, histórico de alterações).
+ ORM + migrations; ecossistema Python para coleta e LLM.
− Admin tem limites de UX (ok para uso interno; views HTMX pontuais se necessário).
− Django é mais "pesado" que FastAPI (irrelevante nesta escala).

## Quando revisitar
Se a UI do admin impedir a triagem em ≤ 30 min/semana, ou se surgir necessidade de
usuários externos.
