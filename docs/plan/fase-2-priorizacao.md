# Fase 2 — Priorização (MVP-B)

## E12 — Municípios IBGE, distância e perfis geográficos

**Objetivo:** dar ao sistema noção de localização e relevância geográfica contextual.
**Resultado esperado:** tabela `Municipality` carregada (5.570 municípios com
lat/lon e regiões), **polos prioritários** configuráveis (Araraquara, São Carlos, Ribeirão
Preto, Bauru), função `geo_relevance(item, profile)` retornando `(valor, explicação)`.
Localização é fator, nunca filtro (exceto elegibilidade territorial explícita).
**Ler antes:** `docs/architecture/geo-relevance.md`.
**Alterações:** `core/models.py` (`Municipality`; FKs em Organization/Opportunity);
`core/management/commands/load_municipalities.py` (IBGE localidades + centróides de
fonte pública documentada); `scoring/geo.py` (haversine, anéis R0–R5, perfis como dados);
settings `HOME_MUNICIPALITY_IBGE` e `PRIORITY_HUBS_IBGE`; migração dos campos provisórios da E03.
**Dependências:** E03.
**Modelo (desenvolvimento):** Claude Sonnet 5.5. **IA em runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** baixa.
**Riscos:** fonte de centróides sem licença clara → usar dado do IBGE; nomes de
municípios com acento/homônimos → casar por (nome normalizado, UF).
**Testes:** distâncias Araraquara–São Carlos ≈ 35–45 km, –Ribeirão Preto ≈ 75–85 km,
–Bauru ≈ 95–105 km; Bauru classificado R1 (polo); `remote_service` nunca zera por distância;
localização ausente → 0,5 + explicação.
**Critério de conclusão:**
- [x] Carga idempotente (5.571 linhas); código IBGE de Araraquara (3503208) confirmado no settings. ADR-022.
- [x] Todos os perfis de `geo-relevance.md` implementados e testados (`scoring/geo.py`, `tests/test_geo.py`). Medido: Bauru ≈ 111 km (não ~100).

---

## E13 — Scoring v1 de oportunidades + breakdown no admin

**Objetivo:** pontuar oportunidades com gates, fatores, perfis e confiança, mostrando o "por quê",
incluindo **elegibilidade da empresa (MEI) vs. requisitos** (ADR-013).
**Resultado esperado:** `manage.py rescore` calcula `Score` para todas as oportunidades;
admin ordena por score e mostra o breakdown linha a linha.
**Ler antes:** `docs/architecture/scoring.md`, ADR-006.
**Alterações:** `scoring/models.py` (`Score`); `scoring/factors/{value,fit,chance,timing,access,lightness}.py`;
`scoring/gates.py`; `scoring/eligibility.py` (compara requisitos extraídos com `CompanyProfile`:
gate explícito, alerta ambíguo, bônus cota ME/EPP/MEI, alerta de limite do MEI);
`scoring/profiles.py` (pesos versionados); `scoring/engine.py`;
comando `rescore`; admin com coluna de score, rótulo (Priorizar/Avaliar/…), breakdown.
**Dependências:** E11 (campos extraídos), E12 (geo), E03b (`CompanyProfile`).
**Modelo (desenvolvimento):** Claude Opus 5.5 (lógica central, precisa ser correta e explicável).
**IA em runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** média.
**Riscos:** pesos ruins → é esperado; calibração na E30. Fatores sem dado dominarem →
neutro 0,5 + confiança reduz.
**Testes:** cada fator com casos-limite; gates; elegibilidade (não aceita MEI → gate; "sede há
> 2 anos" com CNPJ mais novo → gate; cota ME/EPP → bônus; valor > limite MEI → alerta); soma de
pesos = 1 por perfil; determinismo; exemplo de `scoring.md` reproduzido em teste.
**Critério de conclusão:**
- [x] Toda oportunidade não-gated tem score e breakdown (`rescore`; testes em `tests/test_scoring.py`). ADR-035.
- [ ] Humano entende o breakdown de 5 itens sem ler código (admin pronto; conferir com dados reais, P23).
- [x] Mudança de pesos → nova versão → `rescore` recalcula tudo (testado).

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
- [ ] Triar 20 itens leva < 5 min (conferir com dados reais, P24).
- [x] `make metrics` mostra M1–M9 (os que já têm dados). ADR-036.

---

## E15 — Digest semanal

**Objetivo:** entregar toda semana, sem precisar abrir o sistema, o que importa.
**Resultado esperado:** `manage.py digest` gera `data/digests/AAAA-Www.html` (e `.md`)
com: **follow-ups vencendo/vencidos** (resumo da última interação), top-10 oportunidades por
score (com 1 linha de "por quê"), prazos que vencem em ≤ 14 dias, novidades desde o último
digest, **oportunidades bloqueadas por requisito da empresa** (e valor somado), fontes com
erro, custo do mês (dinheiro novo e créditos). E-mail opcional **apenas para a equipe**
(remetente/destinatário `@scorpionbits.com`). Seções de leads (se E21 concluída): "Leads da
semana" (top-10 com contato sugerido, razão e portfólio a citar) e "Em andamento".
**Ler antes:** `docs/product/mvp.md`, `scoring.md` (faixas).
**Alterações:** `reports/digest.py`, templates, comando `digest`, settings SMTP opcionais.
**Dependências:** E13, E14 (E21 para as seções de leads; E03b para follow-ups).
**Modelo (desenvolvimento):** Claude Sonnet 5.5. **IA em runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** baixa.
**Riscos:** digest longo demais → limite rígido de itens; e-mail cair no spam → é só para a equipe; alternativa: abrir o HTML.
**Testes:** geração com dados de teste; itens gated/descartados não aparecem; seção de prazos correta.
**Critério de conclusão:**
- [ ] Digest legível em < 5 min; links funcionam.
- [ ] Nada descartado/gated aparece.

---

## E16 — Agendamento no GitHub Actions, backups, logs e runbook

**Objetivo:** o radar roda sozinho, sem servidor, e é fácil de operar/recuperar (ADR-010).
**Resultado esperado:** comando `manage.py run_pipeline` (collect → extract → match → rescore →
digest); workflow `.github/workflows/pipeline.yml` (`schedule` diário + `workflow_dispatch`,
segredos no GitHub Secrets, conexão via pooler do Supabase); workflow `backup.yml` semanal
(`pg_dump` comprimido **e criptografado com age** → artefato com retenção; repositório público, ADR-014) + instrução de cópia local; `docs/operations/runbook.md`.
O pipeline diário também evita a pausa do Supabase Free por inatividade.
**Ler antes:** `docs/architecture/overview.md` (decisões transversais), `docs/research/hosting.md`.
**Alterações:** `radar/management/commands/run_pipeline.py`; workflows; `docs/operations/runbook.md`
(como agendar, verificar, retomar projeto Supabase pausado, restaurar backup, trocar chave, desabilitar fonte;
fallback de agendamento: cron externo chamando `workflow_dispatch` ou cron local).
**Dependências:** E15.
**Modelo (desenvolvimento):** Claude Sonnet 5.5 (ou Haiku para o runbook). **IA em runtime:** nenhuma.
**Custo:** US$ 0. **Complexidade:** baixa.
**Riscos:** `schedule` indisponível no repositório → fallback documentado; repositório público (minutos
ilimitados), mas `schedule` desliga após 60 dias sem commits → alerta no digest e no runbook; falha silenciosa → digest mostra "última coleta há X dias".
**Testes:** `run_pipeline --dry-run`; backup restaura no projeto `radar-dev`.
**Critério de conclusão:**
- [ ] Pipeline agendado rodou sozinho ao menos 1×.
- [ ] Restauração de backup testada.
- [ ] Runbook permite a outra pessoa operar sem ajuda.
