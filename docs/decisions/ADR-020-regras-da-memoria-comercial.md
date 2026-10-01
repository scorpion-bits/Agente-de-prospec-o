# ADR-020 — Regras do relacionamento derivado da memória comercial

- **Status:** aceito
- **Data:** 2026-10-01
- **Etapa:** E03b

## Contexto
O ADR-012 criou `Interaction` e o status de relacionamento derivado, mas deixou em aberto **como**
derivar e como tratar histórico ainda não confirmado pelo titular (P1–P2: datas, canais, cargos).

## Decisão
1. **Datas, não horários.** `Interaction.occurred_at` e `next_action_at` são `DateField`; os
   derivados `Organization.last_interaction_at`/`next_action_at` (nulos desde a E03) passaram de
   `DateTimeField` para `DateField` (migration sem perda: estavam vazios). Ninguém registra hora.
2. **Sem data inventada.** `occurred_at` pode ser nulo e o registro leva `data_status=pending`. O
   status entra assim mesmo ("proposta enviada"); a `last_interaction_at` fica nula até haver data.
   Reimportar o CSV com a data preenchida **completa** o registro pendente (chave: organização +
   tipo + resumo), sem duplicar; registros confirmados só mudam com `--update`.
3. **Regras do status** (`core/services/relationship.py`): `do_not_contact` é humano e nunca é
   sobrescrito; `client` = alguma interação `won` ou `course_delivered` não negativa; `lost` = a
   interação mais recente terminou `lost`/`negative`; senão vale o maior estágio já alcançado
   (`proposal_sent` > `in_conversation` > `contacted`); sem interações = `never_contacted`.
4. **O próximo passo vive na interação mais recente.** `next_action_at` da organização vem só dela:
   registrar uma interação nova sem próxima ação limpa o lembrete antigo (sem estado "feito").
5. Recalculado por *signals* (`post_save`/`post_delete` de `Interaction`), cobrindo admin, importação
   e exclusão em massa.
6. **Dedupe** (`core/services/organizations.py`): CNPJ > INEP > domínio do site > nome normalizado +
   município + rede. Descoberta numa organização existente só **completa campos em branco**.
7. **Seeds seguem a regra do `load_services`**: `import_portfolio` e `load_company_profile` só criam
   o que falta; `--update` sobrescreve (edições do admin, como as do contador, são preservadas).
8. `core/models.py` virou o pacote `core/models/` (sem migration; imports `from core.models import X`
   inalterados).

## Alternativas consideradas
| Alternativa | Por que não |
|---|---|
| Guardar o status editável e só sugerir o derivado | Duas fontes da verdade; o ADR-012 pede derivado |
| `next_action_at` = menor data entre todas as interações | Lembretes velhos nunca sairiam sem estado "feito" |
| Descartar linhas sem data na importação | Esconderia as propostas SESC já enviadas, justamente o caso do M1 |

## Consequências
+ "Já falamos com eles?" responde no admin mesmo com o histórico incompleto, sem inventar dados.
− Quem muda de `do_not_contact` precisa editar a organização conscientemente (hoje só no banco/shell;
  a tela de `Suppression` gerenciável fica para a Fase 4).
− O dedupe por nome varre as organizações em Python: aceitável no MVP; indexar uma chave normalizada
  quando a base passar de alguns milhares (E04+).
