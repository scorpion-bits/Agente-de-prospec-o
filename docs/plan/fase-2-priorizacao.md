# Fase 2 — Priorização (MVP-B)

## E12 — Municípios IBGE, distância e perfis geográficos

**Objetivo:** dar ao sistema noção de localização e relevância geográfica contextual.
**Resultado esperado:** tabela `Municipality` carregada (5.570 municípios com
lat/lon e regiões), função `geo_relevance(item, profile)` retornando `(valor, explicação)`.
**Ler antes:** `docs/architecture/geo-relevance.md`.
**Alterações:** `core/models.py` (`Municipality`; FKs em Organization/Opportunity);
`core/management/commands/load_municipalities.py` (IBGE localidades + centróides de
fonte pública documentada); `scoring/geo.py` (haversine, anéis R0–R5, perfis como dados);
settings `HOME_MUNICIPALITY_IBGE`; migração dos campos provisórios da E03.
**Dependências:** E03.
**Modelo (desenvolvimento):** Claude Sonnet 5.5. **IA em runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** baixa.
**Riscos:** fonte de centróides sem licença clara → usar dado do IBGE; nomes de
municípios com acento/homônimos → casar por (nome normalizado, UF).
**Testes:** distância Araraquara–São Carlos ≈ 35–45 km; perfis retornam valores esperados;
localização ausente → 0,5 + explicação.
**Critério de conclusão:**
- [ ] Carga idempotente; código IBGE de Araraquara confirmado no settings.
- [ ] Todos os perfis de `geo-relevance.md` implementados e testados.

---

## E13 — Scoring v1 de oportunidades + breakdown no admin

**Objetivo:** pontuar oportunidades com gates, fatores, perfis e confiança, mostrando o "por quê".
**Resultado esperado:** `manage.py rescore` calcula `Score` para todas as oportunidades;
admin ordena por score e mostra o breakdown linha a linha.
**Ler antes:** `docs/architecture/scoring.md`, ADR-006.
**Alterações:** `scoring/models.py` (`Score`); `scoring/factors/{value,fit,chance,timing,access,lightness}.py`;
`scoring/gates.py`; `scoring/profiles.py` (pesos versionados); `scoring/engine.py`;
comando `rescore`; admin com coluna de score, rótulo (Priorizar/Avaliar/…), breakdown.
**Dependências:** E11 (campos extraídos), E12 (geo).
**Modelo (desenvolvimento):** Claude Opus 5.5 (lógica central, precisa ser correta e explicável).
**IA em runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** média.
**Riscos:** pesos ruins → é esperado; calibração na E30. Fatores sem dado dominarem →
neutro 0,5 + confiança reduz.
**Testes:** cada fator com casos-limite; gates; soma de pesos = 1 por perfil; determinismo;
exemplo de `scoring.md` reproduzido em teste.
**Critério de conclusão:**
- [ ] Toda oportunidade não-gated tem score e breakdown.
- [ ] Humano entende o breakdown de 5 itens sem ler código.
- [ ] Mudança de pesos → nova versão → `rescore` recalcula tudo.

---

## E14 — Triagem humana, motivos de descarte e métricas básicas

**Objetivo:** permitir triagem rápida e medir se o sistema entrega valor.
**Resultado esperado:** ações em massa no admin (interessante / descartar com motivo /
em ação / concluído), filtro "não triados", e `manage.py metrics` exibindo M1–M8.
**Ler antes:** `docs/product/metrics.md`, `data-model.md` (Triage).
**Alterações:** `core/admin.py` (ações, filtros, formulário rápido de motivo);
`reports/metrics.py` + comando `metrics`.
**Dependências:** E13.
**Modelo (desenvolvimento):** Claude Sonnet 5.5. **IA em runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** baixa.
**Riscos:** triagem lenta no admin → medir; se > 30 min/semana, considerar view HTMX dedicada (registrar).
**Testes:** ações alteram status e registram autor/data; métricas calculadas com dados de teste.
**Critério de conclusão:**
- [ ] Triar 20 itens leva < 5 min.
- [ ] `metrics` mostra M1–M8 (os que já têm dados).

---

## E15 — Digest semanal

**Objetivo:** entregar toda semana, sem precisar abrir o sistema, o que importa.
**Resultado esperado:** `manage.py digest` gera `data/digests/AAAA-Www.html` (e `.md`)
com: top-10 por score (com 1 linha de "por quê"), prazos que vencem em ≤ 14 dias,
novidades desde o último digest, fontes com erro, custo do mês, valor somado de
oportunidades que exigem CNPJ. E-mail opcional **apenas para a equipe** (SMTP configurável).
**Ler antes:** `docs/product/mvp.md`, `scoring.md` (faixas).
**Alterações:** `reports/digest.py`, templates, comando `digest`, settings SMTP opcionais.
**Dependências:** E13, E14.
**Modelo (desenvolvimento):** Claude Sonnet 5.5. **IA em runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** baixa.
**Riscos:** digest longo demais → limite rígido de itens; e-mail cair no spam → é só para a equipe; alternativa: abrir o HTML.
**Testes:** geração com dados de teste; itens gated/descartados não aparecem; seção de prazos correta.
**Critério de conclusão:**
- [ ] Digest legível em < 5 min; links funcionam.
- [ ] Nada descartado/gated aparece.

---

## E16 — Agendamento, backups, logs e runbook

**Objetivo:** o radar roda sozinho e é fácil de operar/recuperar.
**Resultado esperado:** um comando `manage.py run_pipeline` (collect → extract → rescore)
e instruções de agendamento (cron Linux/macOS, Agendador de Tarefas Windows); backup
diário do SQLite com rotação; logs em arquivo com rotação; `docs/operations/runbook.md`.
**Ler antes:** `docs/architecture/overview.md` (decisões transversais).
**Alterações:** `radar/management/commands/run_pipeline.py`; `scripts/backup_db.*`;
logging config; `docs/operations/runbook.md` (como agendar, verificar, recuperar, trocar chave de API, desabilitar fonte).
**Dependências:** E15.
**Modelo (desenvolvimento):** Claude Sonnet 5.5 (ou Haiku para o runbook). **IA em runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** baixa.
**Riscos:** máquina desligada no horário → rodar "ao ligar" / catch-up; falha silenciosa → digest mostra "última coleta há X dias".
**Testes:** `run_pipeline --dry-run`; backup restaura em banco novo.
**Critério de conclusão:**
- [ ] Pipeline agendado rodou sozinho ao menos 1×.
- [ ] Restauração de backup testada.
- [ ] Runbook permite a outra pessoa operar sem ajuda.
