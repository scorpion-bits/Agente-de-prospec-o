"""Configuração do projeto. Tudo que varia por ambiente vem de variáveis de ambiente/.env.

O repositório é público (ADR-014): nenhum segredo ou dado pessoal neste arquivo.
"""

from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")  # opcional: ignora se o arquivo não existir

DEBUG = env.bool("DJANGO_DEBUG", default=False)

SECRET_KEY = env.str("DJANGO_SECRET_KEY", default="")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Defina DJANGO_SECRET_KEY (ou DJANGO_DEBUG=true em dev local).")
    SECRET_KEY = "dev-only-insecure-key"  # nunca usado fora de DEBUG

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Apps do projeto (monólito modular — docs/architecture/overview.md)
    "core",
    "collection",
    "extraction",
    "llm",
    "scoring",
    "reports",
    "radar",  # só comandos de orquestração (run_pipeline), sem modelos
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "radar.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "radar.wsgi.application"

# --- Banco (ADR-010) -------------------------------------------------------------------
# PostgreSQL. No Supabase, usar a string do POOLER (modo sessão, IPv4), nunca a conexão direta.
# As tabelas ficam num schema dedicado (DB_SCHEMA, padrão "radar"), que não é exposto pela
# Data API do Supabase (ADR-016). Vazio = usa o schema padrão.
DB_SCHEMA = env.str("DB_SCHEMA", default="radar")

_db = env.db_url("DATABASE_URL")  # sem padrão: falhar cedo é melhor que apontar para o banco errado
_db["OPTIONS"] = {
    **_db.get("OPTIONS", {}),
    # Compatível com poolers em modo transação: sem prepared statements automáticos.
    "prepare_threshold": None,
}
if DB_SCHEMA:
    _db["OPTIONS"]["options"] = f"-c search_path={DB_SCHEMA},public"
_db["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=0)
_db["DISABLE_SERVER_SIDE_CURSORS"] = True
DATABASES = {"default": _db}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Identificação do robô de coleta (usada a partir da E04). O e-mail vem do .env, não do git.
CONTACT_EMAIL = env.str("CONTACT_EMAIL", default="")
# CNPJ da empresa: dado sensível (ADR-014), só no .env; carregado por `load_company_profile`.
COMPANY_CNPJ = env.str("COMPANY_CNPJ", default="")
# Geografia (geo-relevance.md): base da empresa, polos prioritários e raios dos anéis.
HOME_MUNICIPALITY_IBGE = env.int("HOME_MUNICIPALITY_IBGE", default=3503208)  # Araraquara/SP
PRIORITY_HUBS_IBGE = env.list(
    "PRIORITY_HUBS_IBGE",
    cast=int,
    default=[3503208, 3548906, 3543402, 3506003],  # Araraquara, São Carlos, Ribeirão Preto, Bauru
)
GEO_NEAR_KM = env.float("GEO_NEAR_KM", default=40.0)  # R1: vizinhas de Araraquara
GEO_REGIONAL_KM = env.float("GEO_REGIONAL_KM", default=150.0)  # R2: interior próximo

# Retenção do texto dos documentos coletados (ADR-010: o banco do plano Free tem 500 MB).
RAW_DOCUMENT_RETENTION_DAYS = env.int("RAW_DOCUMENT_RETENTION_DAYS", default=180)
USER_AGENT = f"RadarScorpionBits/0.1 (+https://scorpionbits.com; {CONTACT_EMAIL})".replace(
    "; )", ")"
)

# Busca web (E18): provedor, chaves e teto de buscas pagas por execução.
SEARCH_PROVIDER = env.str("SEARCH_PROVIDER", default="serper")
SERPER_API_KEY = env.str("SERPER_API_KEY", default="")
BRAVE_API_KEY = env.str("BRAVE_API_KEY", default="")
SEARCH_MAX_CALLS_PER_RUN = env.int("SEARCH_MAX_CALLS_PER_RUN", default=100)

# Camada de IA (E10, ADR-033). Chaves só no .env. Teto mensal de dinheiro novo; créditos do Google
# AI Pro (Gemini pago) contam à parte; o teto por execução soma os dois. Free tier não tem teto.
LLM_MONTHLY_BUDGET_USD = env.float("LLM_MONTHLY_BUDGET_USD", default=5.0)
LLM_CREDITS_MONTHLY_USD = env.float("LLM_CREDITS_MONTHLY_USD", default=10.0)
LLM_RUN_BUDGET_USD = env.float("LLM_RUN_BUDGET_USD", default=1.0)
GEMINI_API_KEY_FREE = env.str("GEMINI_API_KEY_FREE", default="")  # free tier: só dados públicos
GEMINI_API_KEY_PAID = env.str("GEMINI_API_KEY_PAID", default="")  # projeto com faturamento/créditos
ANTHROPIC_API_KEY = env.str("ANTHROPIC_API_KEY", default="")
# Ollama: local por padrão. Servidor remoto só recebe dados públicos (LGPD).
OLLAMA_BASE_URL = env.str("OLLAMA_BASE_URL", default="http://localhost:11434")
OLLAMA_API_KEY = env.str("OLLAMA_API_KEY", default="")
# Estratégias por tarefa (JSON), ex.: {"extract_opportunity_fields": ["ollama:qwen2.5:7b", "rules"]}
LLM_TASK_STRATEGIES = env.json("LLM_TASK_STRATEGIES", default={})

# Logs: o GitHub Actions é público — nunca registrar dados pessoais (ADR-014).
LOG_PII = env.bool("LOG_PII", default=False)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": env.str("LOG_LEVEL", default="INFO")},
}

# Digest semanal (E15, ADR-037). Arquivos em data/digests/ (ignorado pelo git). E-mail opcional e só
# para a equipe: destinatários só da lista DIGEST_EMAIL_TO (sem domínio próprio ainda; ADR-005).
DIGEST_DIR = BASE_DIR / "data" / "digests"
DIGEST_BASE_URL = env.str(
    "DIGEST_BASE_URL", default="http://127.0.0.1:8000"
)  # base dos links do admin
DIGEST_EMAIL_FROM = env.str("DIGEST_EMAIL_FROM", default="")
DIGEST_EMAIL_TO = env.list("DIGEST_EMAIL_TO", default=[])
EMAIL_HOST = env.str("SMTP_HOST", default="")
EMAIL_PORT = env.int("SMTP_PORT", default=587)
EMAIL_HOST_USER = env.str("SMTP_USER", default="")
EMAIL_HOST_PASSWORD = env.str("SMTP_PASSWORD", default="")
EMAIL_USE_TLS = True
