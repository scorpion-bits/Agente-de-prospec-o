# Métricas

Objetivo das métricas: **decidir se vale continuar investindo tempo/dinheiro no sistema.**
Por isso priorizamos poucas métricas, calculáveis a partir de dados que o sistema já
guarda (status de triagem, logs de coleta, logs de custo LLM).

## Métricas do MVP (implementadas na E14/E22)

| # | Métrica | Como medir | Por que importa | Meta MVP |
|---|---|---|---|---|
| M1 | **Itens "interessantes" por semana** | `triage_status=interesting` criados/semana | Valor bruto entregue | ≥ 2–3/semana |
| M2 | **Precisão do topo** | % dos top-10 do digest marcados interessantes | Score está funcionando? | ≥ 40% |
| M3 | **Novidade vs. manual** | Interessantes que não estavam no baseline manual (E01) | Prova de que o sistema acha o que não acharíamos | ≥ 5 em 4 semanas |
| M4 | **Ações geradas** | Itens com status `acting` (inscrição, contato, proposta) | Valor se transforma em ação? | ≥ 3 em 4 semanas |
| M5 | **Custo variável por item interessante** | (custo LLM + busca) / M1 | Sustentabilidade | ≤ US$ 1 |
| M6 | **Tempo de triagem semanal** | Autodeclarado no fim da semana (nota em STATUS) | Economia de tempo | ≤ 30 min |
| M7 | **Saúde das fontes** | Coletas com erro / total, por conector | Fonte quebrada = oportunidade perdida | < 10% erro |
| M8 | **Motivos de descarte** | Distribuição de `discard_reason` | Diz o que ajustar (fonte, score, geo) | — (diagnóstico) |

## Métricas pós-MVP (Fase 4, quando houver pipeline)

| Métrica | Observação |
|---|---|
| Contatos realizados / respostas / reuniões | Requer registro de interações (E23) |
| Propostas enviadas / contratos fechados | Funil real |
| Receita potencial em aberto / receita conquistada atribuída ao radar | A métrica que realmente importa |
| Taxa de resposta por segmento e por serviço | Direciona onde prospectar |
| Custo por lead qualificado / por reunião | Compara com esforço manual |
| Contatos válidos (e-mail não retornou, telefone atendeu) | Qualidade da extração de contatos |

## Métricas que NÃO vamos perseguir

- "Total de leads no banco" — vaidade; incentiva lixo.
- "Número de agentes/execuções" — custo, não valor.
