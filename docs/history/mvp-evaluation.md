# Avaliação do MVP (E22) — go/no-go

> **Status: pendente.** Preencher só depois de ≥ 4 semanas de uso real com triagem semanal (ADR-040).
> Sem dados pessoais (repositório público, ADR-014): contagens, percentuais e casos anonimizados.

## Como gerar os números
1. `make pipeline` rodando e triagem semanal feita (P24–P27).
2. `make evaluate M3=<n> M6=<min>` → `data/evaluations/AAAA-MM-DD.md` (não versionado).
3. Copiar a tabela de métricas para a seção abaixo.

## Período avaliado
- De: ____ a: ____ (dias de uso real: __) · triagens decididas: __

## Métricas (M1–M9)
| # | Valor | Meta | Situação |
|---|---|---|---|
| M1 | | ≥ 2/semana | |
| M2 | | ≥ 40% | |
| M3 | | ≥ 5 em 4 semanas | |
| M4 | | ≥ 3 em 4 semanas | |
| M5 | | ≤ US$ 1 | |
| M6 | | ≤ 30 min | |
| M7 | | < 10% erro | |
| M8 | | diagnóstico | |
| M9 | | 0 vencidos | |

## Baseline manual (E01)
Itens achados à mão × itens do sistema; tempo gasto em cada caminho. *(pendente: `docs/research/baseline-manual.md`)*

## Custos
Dinheiro novo: US$ __ · créditos usados: US$ __ · busca web (fatura do provedor): US$ __ · tempo de triagem semanal: __ min.

## Casos
- Sucesso (2–3): ____
- Fracasso (2–3): ____

## Decisão
Sugestão do relatório: ____ · **Decisão humana:** continuar (etapas da Fase 4: ____) / ajustar / parar. ADR: ____
