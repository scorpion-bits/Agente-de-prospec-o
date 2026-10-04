# Radar Scorpion Bits — comandos do dia a dia.  `make help` lista os alvos.
.DEFAULT_GOAL := help
UV ?= uv

.PHONY: help setup run migrate seed memory collect websites contacts signals match rescore metrics evaluate calibrate digest pipeline backup extract superuser test lint fmt docs-check check

help:  ## Lista os comandos
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-12s %s\n", $$1, $$2}'

setup:  ## Instala dependências (uv) e cria o .env a partir do exemplo
	$(UV) sync
	@test -f .env || (cp .env.example .env && echo ".env criado a partir do .env.example (PostgreSQL local em 127.0.0.1:5432; ajuste DATABASE_URL se usar o Supabase)")

migrate:  ## Aplica migrations (cria o schema dedicado se preciso)
	$(UV) run python manage.py migrate

seed:  ## Carrega catálogo de serviços, municípios do IBGE e fontes de coleta (não sobrescreve edições)
	$(UV) run python manage.py load_services
	$(UV) run python manage.py load_municipalities
	$(UV) run python manage.py load_sources

memory:  ## Carrega perfil da empresa, portfólio e (se existir) o histórico privado de interações
	$(UV) run python manage.py load_company_profile
	$(UV) run python manage.py import_portfolio
	@test -f data/private/interactions.csv && $(UV) run python manage.py import_interactions \
		|| echo "data/private/interactions.csv não existe: copie data/seeds/interactions.template.csv e preencha (P1/P2)"

collect:  ## Roda os conectores das fontes habilitadas (collect --all); DRY=1 simula
	$(UV) run python manage.py collect --all $(if $(DRY),--dry-run)

websites:  ## Acha o site oficial de escolas sem site (E18); N=20 organizações, DRY=1 simula
	$(UV) run python manage.py find_websites --kind school --limit $(or $(N),20) $(if $(DRY),--dry-run)

signals:  ## Sinais de necessidade web no site das organizações (E26); N=20, DRY=1 simula
	$(UV) run python manage.py web_signals --limit $(or $(N),20) $(if $(DRY),--dry-run)

match:  ## Gera hipóteses serviço × organização × portfólio (E20); DRY=1 simula
	$(UV) run python manage.py match_services $(if $(DRY),--dry-run)

contacts:  ## Extrai contatos públicos do site oficial (E19); N=20 organizações, DRY=1 simula
	$(UV) run python manage.py extract_contacts --limit $(or $(N),20) $(if $(DRY),--dry-run)

rescore:  ## Pontua as oportunidades (E13); DRY=1 simula
	$(UV) run python manage.py rescore $(if $(DRY),--dry-run)

metrics:  ## Mostra as métricas M1–M9 (E14)
	$(UV) run python manage.py metrics

evaluate:  ## Relatório de go/no-go do MVP em data/evaluations (E22); M3=n M6=min; DRY=1 imprime
	$(UV) run python manage.py evaluate $(if $(M3),--m3 $(M3)) $(if $(M6),--m6 $(M6)) $(if $(DRY),--dry-run)

calibrate:  ## Proposta de pesos do score em data/calibrations (E30); DRY=1 imprime
	$(UV) run python manage.py calibrate $(if $(DRY),--dry-run)

digest:  ## Gera o digest semanal em data/digests (E15); MAIL=1 envia só à equipe
	$(UV) run python manage.py digest $(if $(MAIL),--email) $(if $(DRY),--dry-run)

pipeline:  ## Cadeia collect → extract → match → rescore (E16); DRY=1 simula, DIGEST=1 inclui o digest
	$(UV) run python manage.py run_pipeline $(if $(DRY),--dry-run) $(if $(DIGEST),--digest)

backup:  ## Backup criptografado (age) do schema em data/backups (E16); precisa de pg_dump e age
	bash scripts/backup.sh

extract:  ## Extrai campos das oportunidades candidatas (E11); N=20 itens, DRY=1 simula
	$(UV) run python manage.py extract_opportunities --limit $(or $(N),20) $(if $(DRY),--dry-run)

llm-smoke:  ## Chamada real de fumaça à IA (E10); S=gemini-free:gemini-3.1-flash-lite escolhe a estratégia
	$(UV) run python manage.py llm_smoke $(if $(S),--strategy $(S))

llm-usage:  ## Custo e uso da IA no mês (E10)
	$(UV) run python manage.py llm_usage

superuser:  ## Cria um usuário administrador
	$(UV) run python manage.py createsuperuser

run:  ## Sobe o admin em http://127.0.0.1:8000/admin/
	$(UV) run python manage.py runserver

test:  ## Testes (precisam de DATABASE_URL apontando para um PostgreSQL)
	$(UV) run pytest -q

lint:  ## Ruff: lint + formatação
	$(UV) run ruff check .
	$(UV) run ruff format --check .

fmt:  ## Corrige formatação e lint automaticamente
	$(UV) run ruff check --fix .
	$(UV) run ruff format .

docs-check:  ## Limites de CLAUDE.md/STATUS.md e dados sensíveis (ADR-014)
	$(UV) run python scripts/repo_checks.py

check: lint  ## Tudo que o CI roda
	$(UV) run python manage.py check
	$(UV) run python manage.py makemigrations --check --dry-run
	$(UV) run pytest -q
	$(UV) run python scripts/repo_checks.py
