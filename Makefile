# Radar Scorpion Bits — comandos do dia a dia.  `make help` lista os alvos.
.DEFAULT_GOAL := help
UV ?= uv

.PHONY: help setup run migrate seed memory collect superuser test lint fmt docs-check check

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
