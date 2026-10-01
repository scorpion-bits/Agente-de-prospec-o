# Avaliação da extração de oportunidades (E11)

> **Pendente do humano (P22).** Nenhuma extração real foi rodada ainda: a rede do ambiente de desenvolvimento bloqueia
> as fontes e não há chave aqui. Este arquivo é o formulário da amostra; preencha depois de `make extract`.

## Como medir
1. `git pull`, `make migrate` (sem migration nova na E11) e `make extract DRY=1 N=20`; se a saída estiver sensata, `make extract N=20`.
2. No admin, abra 20 oportunidades extraídas (misture tipos). Para cada campo, compare com a página oficial.
3. Marque: **certo** (valor e citação conferem), **unknown** (não extraiu), **errado** (valor diferente do texto).
4. Preencha a tabela. Meta: **prazo** e **requisitos de empresa** ≥ 90% (certo + unknown), **zero errado confiante**
   (campo crítico errado que entrou na coluna). Pelo menos 1 edital real com requisito de empresa extraído com citação.

## Resultado (preencher)
| Campo | Certo | Unknown | Errado | Observações |
|---|---|---|---|---|
| prazo (`deadline_at`) | | | | |
| abertura / início | | | | |
| MEI / naturezas jurídicas | | | | |
| exige CNPJ / cota ME-EPP | | | | |
| idade mínima / CNAE | | | | |
| prêmio / valor | | | | |
| modalidade / abrangência | | | | |
| resumo | | | | |

Linha de custo: `make llm-usage` (tarefa `extract_opportunity`). Estratégias usadas: ______ (gemini / haiku / rules).
Erros típicos e o que ajustar (prompt `v2`, regras em `extraction/rules.py`): ______
