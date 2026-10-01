import pytest
from django.conf import settings
from django.db import connection


def test_installed_apps_present():
    for app in ("core", "collection", "extraction", "llm", "scoring", "reports"):
        assert app in settings.INSTALLED_APPS


def test_locale_and_timezone():
    assert settings.LANGUAGE_CODE == "pt-br"
    assert settings.TIME_ZONE == "America/Sao_Paulo"


def test_user_agent_identifies_the_bot_without_dangling_separator(settings):
    assert settings.USER_AGENT.startswith("RadarScorpionBits/0.1 (+https://scorpionbits.com")
    assert "; )" not in settings.USER_AGENT


@pytest.mark.django_db
def test_admin_login_page_is_served(client):
    response = client.get("/admin/login/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_admin_requires_login_and_root_redirects(client):
    assert client.get("/admin/").status_code == 302
    assert client.get("/").status_code == 302


@pytest.mark.django_db
def test_tables_live_in_dedicated_schema_not_public():
    schema = settings.DB_SCHEMA
    assert schema, "DB_SCHEMA deve estar definido (ADR-016)"
    with connection.cursor() as cursor:
        cursor.execute(
            "select table_schema, count(*) from information_schema.tables "
            "where table_name like 'django\\_%' or table_name like 'auth\\_%' group by 1"
        )
        found = dict(cursor.fetchall())
    assert found.get(schema, 0) > 0
    assert found.get("public", 0) == 0
