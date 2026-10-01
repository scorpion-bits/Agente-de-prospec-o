# ADR-018 — Listas de strings como ArrayField do PostgreSQL; JSON só para estruturas

- **Status:** aceito
- **Data:** 2026-10-01
- **Etapa:** E03

## Contexto
O modelo tem muitas listas curtas de strings: `categories`, `benefits`, `eligible_legal_forms`,
`keywords`, `target_org_kinds`, `required_cnaes`, `similarity_tags`… O admin é a UI do MVP
(ADR-001): quem edita é uma pessoa de negócio, não um desenvolvedor.

## Decisão
1. Lista plana de strings → `ArrayField(CharField)`. Mostra no admin como texto separado por
   vírgula e valida cada item.
2. Vocabulário controlado (categorias, benefícios, naturezas jurídicas, tipos de organização) →
   `ChoiceArrayField` (`core/fields.py`): o `ArrayField` com `choices` no item, que no admin vira
   **seleção múltipla** em vez de pedir códigos de cor.
3. `JSONField` só para estruturas aninhadas: `Evidence.value`, `Match.reasons`, `Source.config`.
4. CNAEs ficam como digitados (`62.01-5` ou `6201-5`); **a comparação é sempre só pelos
   dígitos** (regra para E13/E20).

## Alternativas consideradas
| Alternativa | Por que não |
|---|---|
| `JSONField` para tudo | Funciona em qualquer banco, mas o admin mostra JSON cru (`["MEI","ME"]`), sem validar itens nem oferecer opções |
| Tabelas de junção | Rigor desnecessário: as listas são pequenas, sem atributos próprios e editadas junto ao registro |

## Consequências
+ Admin utilizável por não-desenvolvedores; consultas `__contains`/`__overlap` (e índice GIN, se
  um dia precisar).
− Acopla o modelo ao PostgreSQL. Já é assim: ADR-010/016 e os testes exigem PostgreSQL.
− Mudar o vocabulário de um `ChoiceArrayField` gera migration (só de estado).

## Quando revisitar
Se deixarmos o PostgreSQL, ou se um item da lista passar a ter atributos próprios (aí vira tabela).
