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
| 002 | SQLite no MVP, PostgreSQL no deploy compartilhado | aceito |
| 003 | IA como último recurso: pipeline determinístico + camada LLM multi-provedor | aceito |
| 004 | Evidência obrigatória e separação fato observado × inferência | aceito |
| 005 | Humano no controle: sem envio automático de mensagens | aceito |
| 006 | Pontuação determinística, explicável e por perfis | aceito |
| 007 | Fontes oficiais/abertas primeiro; sem scraping de LinkedIn/Google | aceito |
| 008 | Sistema de memória do projeto e limite do CLAUDE.md | aceito |
| 009 | MVP focado em oportunidades + escolas/SESC; empresas (CNPJ) pós-MVP | aceito |
