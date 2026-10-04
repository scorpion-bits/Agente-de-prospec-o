# Imagem do admin (E29, ADR-047). Só o app web: coleta e pontuação seguem no GitHub Actions.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
# Valores só para o collectstatic rodar; os de verdade vêm do Cloud Run em tempo de execução.
RUN DJANGO_SECRET_KEY=build-only DATABASE_URL=postgres://u:p@localhost/db \
    python manage.py collectstatic --noinput

RUN useradd --no-create-home --uid 10001 app
USER app

# Cloud Run define $PORT. Sem migrate aqui: `make migrate` roda na máquina do titular (ADR-047).
CMD exec gunicorn radar.wsgi:application --bind 0.0.0.0:${PORT:-8080} --workers 2 --threads 4 --timeout 120 --access-logfile -
