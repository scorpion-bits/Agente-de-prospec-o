# Architecture Decision Records

Registre aqui decisões que **alguém poderia questionar depois** (tecnologia, custo,
escopo, ética). Não registre detalhes triviais de implementação.

Regras:
- Numeração sequencial (`ADR-009-...`). Copie `ADR-000-template.md`.
- ADR aceito **não é editado** no mérito; para mudar, crie um novo que o substitui e
  marque o antigo como `substituído por ADR-XXX`.
- Liste o ADR novo no índice abaixo.

| ADR | Título | Status |
|---|---|---|
| 001 | Monólito modular em Python + Django (admin como UI do MVP) | aceito |
| 002 | SQLite no MVP, PostgreSQL no deploy compartilhado | substituído por 010 |
| 003 | IA como último recurso: pipeline determinístico + camada LLM multi-provedor | aceito |
| 004 | Evidência obrigatória e separação fato observado × inferência | aceito |
| 005 | Humano no controle: sem envio automático de mensagens | aceito |
| 006 | Pontuação determinística, explicável e por perfis | aceito |
| 007 | Fontes oficiais/abertas primeiro; sem scraping de LinkedIn/Google | aceito |
| 008 | Sistema de memória do projeto e limite do CLAUDE.md | aceito |
| 009 | MVP focado em oportunidades + escolas/SESC; empresas (CNPJ) pós-MVP | aceito |
| 010 | Hospedagem: Supabase Postgres + workers no GitHub Actions + admin local (sem Vercel no MVP) | aceito |
| 011 | Seleção de modelos por tarefa; Gemini como provedor principal de extração | aceito |
| 012 | Memória comercial (interações) e portfólio no MVP | aceito |
| 013 | MEI: elegibilidade pelo perfil da empresa | aceito |
| 014 | Repositório público: higiene de dados, logs e backups | aceito |
| 015 | Cobertura de atividades do MEI (CNAE) como fator de elegibilidade | aceito |
| 016 | Schema dedicado `radar` e conexão pelo pooler em modo sessão | aceito |
| 017 | `Evidence` e `Triage` apontam para a entidade por `GenericForeignKey` | aceito |
| 018 | Listas de strings como `ArrayField` do PostgreSQL; JSON só para estruturas | aceito |
| 019 | Interface nova: web (sem executável), consumindo uma API do Django | aceito (princípios) |
| 020 | Regras do relacionamento derivado da memória comercial (datas, pendentes, dedupe) | aceito |
| 021 | Regras da infra de coleta (robots, bloqueio, dry-run, retenção, evidência de CSV) | aceito |
| 022 | Municípios do IBGE: texto × FK, polos e perfis geográficos como dado | aceito |
| 023 | Rede SESC-SP (CSV curado) e escolas do INEP (dataset local) | aceito |
| 024 | Organizações parecidas com o SESC (CSV curado + vocabulário fechado de tags) | aceito |
| 025 | Descoberta de site oficial: busca com cache + validação determinística | aceito |
| 026 | Contatos públicos institucionais: extração por regra, só do domínio da organização | aceito |
| 027 | Matching por regras em dados: razões com evidência, prova de portfólio, máx. 3 por organização | aceito |
| 028 | Conector Devpost: API pública, filtro de relevância e datas sem chute | aceito |
| 029 | Conector itch.io (listagem HTML) e medição de tempo/prazo no fetcher | aceito |
| 030 | Conector `html_watch` genérico: uma página = uma `Source`, candidatas sem datas, diff pelo upsert | aceito |
| 031 | Conector Querido Diário: consultas por termos, janela incremental e sondagem de cobertura | aceito |
