"""Hospedagem (E29, ADR-046): health check, estáticos e configuração de produção."""

import os
import subprocess
import sys

import pytest
from django.urls import reverse


def test_healthz_is_public_and_leaks_nothing(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.content == b"ok"


def test_root_redirects_to_admin_login(client):
    resp = client.get("/", follow=True)
    assert resp.redirect_chain[-1][0].startswith(reverse("admin:login"))


def test_admin_requires_login(client):
    resp = client.get(reverse("admin:index"))
    assert resp.status_code == 302 and "login" in resp["Location"]


@pytest.fixture
def prod_env():
    return {
        **os.environ,
        "DJANGO_DEBUG": "false",
        "DJANGO_HTTPS": "true",
        "DJANGO_SECRET_KEY": "x" * 60 + "-not-a-real-key-for-tests-" + "y" * 10,
        "DJANGO_ALLOWED_HOSTS": "app.example.org",
        "DJANGO_CSRF_TRUSTED_ORIGINS": "https://app.example.org",
    }


def test_check_deploy_has_no_warnings_in_production_mode(prod_env):
    out = subprocess.run(
        [sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
        env=prod_env,
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0, out.stdout + out.stderr


def test_production_redirects_http_but_not_healthz(prod_env):
    code = (
        "import django; django.setup();"
        "from django.test import Client;"
        "c = Client(HTTP_HOST='app.example.org');"
        "r = c.get('/admin/login/');"
        "h = c.get('/healthz');"
        "s = c.get('/admin/login/', secure=True);"
        "ok = bool(c.cookies) and all(m['secure'] for m in c.cookies.values());"
        "print(r.status_code, h.status_code, s.status_code, ok, s.headers['X-Frame-Options'])"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        env={**prod_env, "DJANGO_SETTINGS_MODULE": "radar.settings"},
        capture_output=True,
        text=True,
    )
    assert out.stdout.split() == ["301", "200", "200", "True", "DENY"], out.stdout + out.stderr
