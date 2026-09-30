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
| PDFs escaneados sem texto | Média | Baixo | Entrada nativa de PDF do Gemini (ADR-011); revisão humana se falhar |
| Supabase Free pausa após 7 dias sem uso | Média | Baixo | Pipeline diário mantém ativo; retomada manual documentada |
| Supabase Free sem backups | Média | Alto | `pg_dump` semanal (artefato) + cópia local; restauração testada (E16) |
| `schedule` desliga após 60 dias sem commits (repositório público) | Média | Médio | Alerta "última coleta há X dias" no digest; runbook de reativação; commits regulares |
| Vazamento por repositório público (logs, artefatos, commits) | Média | Alto | ADR-014: nada pessoal em git/logs; backup criptografado; digest por e-mail; revisão antes de cada commit |
| Limite de 500 MB do banco | Baixa | Médio | Sem binários no banco; texto comprimido com retenção |
| Perda de dados | Média | Alto | Ver backups do Supabase acima; restauração testada (E16) |
| Contexto perdido entre sessões do Claude | Média | Médio | CLAUDE.md, STATUS, etapas pequenas, histórico |

## Financeiros

| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| Free tiers mudam/acabam | Alta | Baixo | Multi-provedor; fallback barato com teto |
| Usar Vercel Hobby para ferramenta comercial | Baixa | Médio | Não usar no MVP; Cloud Run ou Vercel Pro quando necessário (ADR-010) |
| Créditos do Google AI Pro não ativados/expirados | Média | Baixo | Ativação na E01b; monitorar no digest |
| Custo de LLM/busca fora de controle | Baixa | Médio | Teto mensal rígido na camada `llm/` e de busca; cache; sem agentes no MVP |
| Tempo da equipe (custo real) consumido pelo sistema | Média | Alto | Métrica M6; parar/ajustar se triagem + manutenção > benefício |

## Legais e reputacionais

| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| Violação de termos de uso de fonte | Baixa | Médio | Checklist por fonte; sem LinkedIn/Google scraping |
| LGPD (dados pessoais de contatos) | Média | Alto | Minimização, contatos institucionais, evidência, opt-out, retenção |
| Contato percebido como spam | Média | Alto | Humano no controle, 1-a-1, personalizado, limite de follow-ups |
| Informação inventada numa abordagem | Baixa | Alto | Evidência obrigatória; rascunhos só com fatos citados |
| Inelegibilidade (MEI não aceito, CNPJ/sede recente, CNAE) descoberta tarde | Média | Médio | Requisitos extraídos e comparados ao `CompanyProfile`; seção no digest (ADR-013) |
| Contrato acima do limite do MEI (R$ 81 mil/ano) | Baixa | Médio | Alerta "exigiria migrar para ME"; decisão de negócio |
| Vender software/web/jogos sob encomenda fora dos CNAEs do MEI | Média | Alto | `mei_coverage` + alerta (ADR-015); confirmar com contador; decidir migração para ME |
| Conta Google pessoal concentra créditos de IA | Média | Baixo | Chave gratuita + reserva Claude; migrar para conta da empresa depois |
| Recontato indevido de organização já prospectada | Média | Alto | Memória comercial; carência de 21 dias; follow-ups explícitos (ADR-012) |
| Dados pessoais em interações (nomes de contatos) | Média | Médio | Fora do git; só no banco; mínimo necessário; só provedores de IA pagos |
