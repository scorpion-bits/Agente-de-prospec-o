# ADR-017 — Evidence e Triage apontam para a entidade por GenericForeignKey

- **Status:** aceito
- **Data:** 2026-10-01
- **Etapa:** E03

## Contexto
`Evidence` (ADR-004) e `Triage` valem para mais de um tipo de entidade — hoje `Organization` e
`Opportunity`; `Score` (E13) seguirá o mesmo padrão. O `data-model.md` previa um par genérico
(`entity_type` + `entity_id`) e o plano da E03 pedia documentar a escolha entre
`GenericForeignKey` e um par de campos simples.

## Decisão
1. Usar o `GenericForeignKey` do Django (`content_type` + `object_id`), limitado por
   `limit_choices_to` às entidades permitidas (`ENTITY_MODELS` em `core/models.py`).
2. `Organization` e `Opportunity` declaram `GenericRelation` (`evidence_items`, `triage_items`):
   apagar a entidade apaga suas evidências e triagens (sem registros órfãos).
3. Como o banco não tem chave estrangeira real, a integridade na criação vem do código:
   `Evidence.clean()`/`Triage.clean()` checam que o ID existe e `record_evidence` só aceita
   entidades já salvas dos tipos permitidos.

## Alternativas consideradas
| Alternativa | Por que não |
|---|---|
| Par `entity_type` (texto) + `entity_id` | Chave estável e legível em SQL, mas sem cascade (órfãos), sem inlines no admin e sem `prefetch_related`: exigiria código próprio para os três |
| Duas FKs anuláveis (`organization`, `opportunity`) + restrição "exatamente uma" | Integridade real e consultas simples, mas cada nova entidade vira migration + restrição, e foge do `data-model.md`. É a melhor alternativa se o conjunto de entidades parar de crescer |
| Uma tabela de evidência por entidade | Duplica modelo, helper e admin; dificulta "todas as evidências de um campo" |

## Consequências
+ Cascade automático, inlines genéricos no admin e `prefetch_related("entity")`.
− Sem FK no banco: a garantia está em `clean()`/`record_evidence`, não em restrição SQL.
− Os IDs de `ContentType` diferem entre bancos. Os backups são `pg_dump` (preservam os IDs);
  **não** exportar evidências por `dumpdata`/fixture sem chaves naturais.
− Consultas SQL manuais precisam juntar com `django_content_type`.

## Quando revisitar
Se o conjunto de entidades com evidência se estabilizar (duas FKs seriam mais simples e
seguras), ou se for preciso exportar/importar evidências entre bancos.
