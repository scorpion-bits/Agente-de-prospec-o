# ADR-045 — Pipeline leve: `Deal` com estágio humano, alerta de follow-up, funil fora do go/no-go

- **Status:** aceito
- **Data:** 2026-10-04

## Contexto
A E23 do plano depende formalmente do go/no-go da E22 (P28, ≥ 4 semanas de uso). Mas ela não usa IA, custa zero e só reorganiza dado
que já existe (`Interaction`, E03b): dá para construí-la antes e **adotá-la** só se a decisão for «continuar». O risco apontado no plano
é virar um CRM gigante.

## Decisão
1. **`Deal`** (migration `core.0006`): organização + serviço (opcional) + oportunidade de origem (opcional) + estágio + valor estimado +
   motivo da perda + observação curta. Nada além disso (sem contatos, tarefas ou anexos próprios).
2. **Estágios**: Interessante → Contato → Respondeu → Reunião → Proposta → Negociação → Fechado (ganho); **Perdido** fora da linha, com
   motivo obrigatório (sem resposta, sem orçamento, escolheram outro, não é o momento, opt-out, outro). **O estágio é decisão humana**
   (admin: ação «avançar» e edição); o sistema não move negócio sozinho (ADR-005).
3. **`Interaction.deal`** (FK opcional, mesma organização, validada) agrupa o histórico. O `relationship_status` da organização continua
   derivado só das interações (ADR-020); `Deal` não o altera.
4. **`peak_stage`** guarda o estágio mais alto já alcançado, para o funil contar perdidos até onde chegaram e voltar atrás não apagar
   histórico. Datas (`stage_changed_at`, `closed_at`) saem do `save()`.
5. **Ritmo de follow-up** (`core/services/pipeline.py`): contam tentativas `message`, `call` e `proposal_sent` com data, ligadas ao negócio,
   **depois da última resposta**. Máximo **2 follow-ups** depois do primeiro contato e **7 dias** entre tentativas. Estados: sem contato,
   aguardar, **devido**, **limite** (encerrar ou pausar), respondeu, encerrado. O sistema **só alerta** (coluna e filtro «ritmo» no admin).
6. **Funil** em `make metrics` (`render_funnel`): quantos alcançaram cada estágio, onde estão agora, valor aberto e ganho. **Fica fora de
   `compute()`**: o go/no-go (E22) julga só M1–M9; um M10 poderia mudar a sugestão por causa de uma etapa que vem depois dela.
7. **Opt-out gerenciável**: ação «Registrar opt-out» na organização (`register_opt_out`): cria `Suppression` (CNPJ válido, senão nome),
   marca `do_not_contact` (que as interações não sobrescrevem) e perde os negócios abertos com motivo «opt-out». Idempotente.
   `Suppression` já era editável no admin (E03).

## Consequências
- Alternativa avaliada e adiada: HubSpot/Pipedrive free. Só vale se o volume de negócios crescer além do que o admin comporta.
- 2 follow-ups e 7 dias são hipótese do plano, em constantes do módulo (P33 pede conferir no uso).
- Valor estimado é digitado pelo humano; não há previsão de receita nem conversão por etapa além da contagem «alcançaram».
- O digest (E15) ainda não lista negócios; o follow-up do digest segue vindo de `Organization.next_action_at`. Integrar se o pipeline for adotado.
