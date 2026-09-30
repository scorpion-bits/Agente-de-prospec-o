# Riscos

Revisar na E22 e sempre que um risco se materializar (registrar em STATUS).

## Produto

| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| O radar não acha nada que não acharíamos manualmente | Média | Alto | Baseline manual (E01) + métrica M3; avaliação E22 com opção de parar |
| Excesso de ruído (itens irrelevantes) → ninguém lê o digest | Alta | Alto | Gates, filtros por fonte, top-10 fixo, motivos de descarte para ajustar |
| Sistema fica pronto depois da janela escolar | Alta | Médio | Prospecção manual em paralelo; ordem alternativa das fases |
| Construir demais antes de validar | Média | Alto | Etapas pequenas; Fase 4 condicionada à E22 |
| Ninguém faz a triagem semanal | Média | Alto | Digest curto; triagem ≤ 30 min; responsável definido |

## Técnicos

| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| Fonte muda formato/sai do ar (endpoints não oficiais: Devpost, itch.io) | Alta | Médio | Conectores isolados, fixtures, alerta de erro no digest, várias fontes |
| Sites bloqueiam coleta | Média | Baixo | Coleta educada; fonte desabilitada e revisada, sem contornar |
| Extração LLM erra prazo/elegibilidade | Média | Alto | Citação verificada, regex de datas, `unknown` permitido, amostra revisada |
| PDFs escaneados sem texto | Média | Baixo | Marcar `needs_ocr`; revisão humana (OCR só se frequente) |
| SQLite insuficiente | Baixa | Baixo | ORM portável; migração planejada (E29) |
| Perda de dados (máquina local) | Média | Médio | Backup diário + restauração testada (E16) |
| Contexto perdido entre sessões do Claude | Média | Médio | CLAUDE.md, STATUS, etapas pequenas, histórico |

## Financeiros

| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| Free tiers mudam/acabam | Alta | Baixo | Multi-provedor; fallback barato com teto |
| Custo de LLM/busca fora de controle | Baixa | Médio | Teto mensal rígido na camada `llm/` e de busca; cache; sem agentes no MVP |
| Tempo da equipe (custo real) consumido pelo sistema | Média | Alto | Métrica M6; parar/ajustar se triagem + manutenção > benefício |

## Legais e reputacionais

| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| Violação de termos de uso de fonte | Baixa | Médio | Checklist por fonte; sem LinkedIn/Google scraping |
| LGPD (dados pessoais de contatos) | Média | Alto | Minimização, contatos institucionais, evidência, opt-out, retenção |
| Contato percebido como spam | Média | Alto | Humano no controle, 1-a-1, personalizado, limite de follow-ups |
| Informação inventada numa abordagem | Baixa | Alto | Evidência obrigatória; rascunhos só com fatos citados |
| Inelegibilidade por falta de CNPJ descoberta tarde | Média | Médio | Campo "exige CNPJ" extraído e destacado no digest |
