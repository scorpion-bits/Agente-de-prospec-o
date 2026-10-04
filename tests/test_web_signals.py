"""E26 — sinais de necessidade web: análise pura, gravação com evidência, opt-out e comando."""

from io import StringIO

import httpx
import pytest
from django.core.management import CommandError, call_command

from collection.fetcher import PoliteFetcher
from collection.web_signal_finder import (
    CHECKED_FIELD,
    apply_scan,
    pending_organizations,
    scan_organization,
)
from core.models import Evidence, Organization, Suppression
from core.services.suppression import SuppressionIndex
from extraction.web_signals import analyze_home, is_social_only

HTML = {"content-type": "text/html; charset=utf-8"}
ROBOTS_OK = httpx.Response(
    200, text="User-agent: *\nAllow: /", headers={"content-type": "text/plain"}
)
SITE = "https://www.escolaaurora.test"
FILLER = "Matrículas abertas para o ensino fundamental e médio em nossa unidade. " * 5


def page(body="", head="", year=None):
    foot = f"<footer>© {year} Escola Aurora</footer>" if year else ""
    return (
        f"<html><head><title>Escola Aurora</title>{head}</head>"
        f"<body><p>{FILLER}</p>{body}{foot}</body></html>"
    )


VIEWPORT = '<meta name="viewport" content="width=device-width, initial-scale=1">'


def codes(signals):
    return {s.code for s in signals}


# --- análise pura ------------------------------------------------------------------------------
def test_site_moderno_nao_tem_sinais():
    assert analyze_home(page(head=VIEWPORT, year=2026), SITE, current_year=2026) == []


def test_sem_https_olha_a_url_final():
    signals = analyze_home(page(head=VIEWPORT), "http://escolaaurora.test/", current_year=2026)
    assert codes(signals) == {"no_https"}
    assert analyze_home(page(head=VIEWPORT), SITE, current_year=2026) == []  # redirecionou p/ https


def test_sem_viewport_e_inferido_e_so_com_texto_suficiente():
    (signal,) = analyze_home(page(), SITE, current_year=2026)
    assert (signal.code, signal.observed) == ("no_viewport", False)
    shell = "<html><head><title>x</title></head><body><div id='root'></div></body></html>"
    assert analyze_home(shell, SITE, current_year=2026) == []  # casca de JS: unknown, não «sem»


def test_copyright_antigo_usa_o_maior_ano_e_cita_trecho():
    (signal,) = analyze_home(page(head=VIEWPORT, year="2012 - 2016"), SITE, current_year=2026)
    assert (signal.code, signal.value, signal.observed) == ("old_copyright", 2016, True)
    assert "© 2012 - 2016" in signal.excerpt
    assert analyze_home(page(head=VIEWPORT, year=2023), SITE, current_year=2026) == []
    assert analyze_home(page(head=VIEWPORT, year=2022), SITE, current_year=2026)  # 4 anos: antigo


def test_copyright_futuro_ou_absurdo_e_ignorado():
    assert analyze_home(page(head=VIEWPORT, year=2031), SITE, current_year=2026) == []
    assert analyze_home(page(head=VIEWPORT, year=1850), SITE, current_year=2026) == []


@pytest.mark.parametrize(
    ("snippet", "tech"),
    [
        ('<embed src="banner.swf" type="application/x-shockwave-flash">', "flash"),
        ('<script src="/js/jquery-1.11.3.min.js"></script>', "jquery_1"),
        ('<script src="/wp-includes/jquery.js?ver=2.2.4"></script>', "jquery_2"),
        ('<script src="/js/jquery-3.7.1.min.js"></script>', None),
        ("<frameset cols='20%,80%'></frameset>", "frameset"),
    ],
)
def test_tecnologia_obsoleta(snippet, tech):
    signals = analyze_home(page(snippet, head=VIEWPORT), SITE, current_year=2026)
    if tech is None:
        assert signals == []
    else:
        (signal,) = signals
        assert signal.code == "obsolete_tech" and signal.value == [tech] and signal.observed


def test_so_rede_social():
    assert is_social_only("https://www.instagram.com/escolaaurora/")
    assert is_social_only("https://linktr.ee/escolaaurora")
    assert not is_social_only(SITE)
    assert not is_social_only("")


# --- varredura e gravação ----------------------------------------------------------------------
class Web:
    def __init__(self, home):
        self.home = home

    def __call__(self, request):
        if request.url.path == "/robots.txt":
            return ROBOTS_OK
        if request.url.path in ("", "/"):
            if isinstance(self.home, httpx.Response):
                return self.home
            return httpx.Response(200, text=self.home, headers=HTML)
        return httpx.Response(404)


def make_fetcher(home, **kwargs):
    client = httpx.Client(transport=httpx.MockTransport(Web(home)))
    return PoliteFetcher(client=client, sleep=lambda s: None, min_interval=0, **kwargs)


@pytest.fixture
def school(db):
    return Organization.objects.create(name="Escola Aurora", kind="school", website=SITE)


def evidence(org, field):
    return Evidence.objects.filter(object_id=org.pk, field=field)


@pytest.mark.django_db
def test_gravar_cria_evidencia_observada_com_url_e_trecho_verificado(school):
    home = page(head=VIEWPORT, year=2014)
    scan = scan_organization(school, make_fetcher(home), SuppressionIndex.load())
    assert scan.status == "ok" and codes(scan.signals) == {"old_copyright"}
    assert apply_scan(school, scan) == 1
    item = evidence(school, "web.signal.old_copyright").get()
    assert (item.kind, item.value, item.verified) == ("observed", 2014, True)
    assert item.source_url == SITE
    assert evidence(school, CHECKED_FIELD).count() == 1


@pytest.mark.django_db
def test_ausencia_vira_evidencia_inferida_sem_url(school):
    scan = scan_organization(school, make_fetcher(page()), SuppressionIndex.load())
    apply_scan(school, scan)
    item = evidence(school, "web.signal.no_viewport").get()
    assert (item.kind, item.source_url, item.method) == ("inferred", "", "rule:web_signals")


@pytest.mark.django_db
def test_site_fora_do_ar_e_inferido_robots_nao_conclui_nada(school):
    down = scan_organization(school, make_fetcher(httpx.Response(503)), SuppressionIndex.load())
    assert down.status == "unreadable" and codes(down.signals) == {"site_down"}
    apply_scan(school, down)
    assert evidence(school, "web.signal.site_down").get().kind == "inferred"

    blocked = scan_organization(school, make_fetcher(httpx.Response(403)), SuppressionIndex.load())
    assert blocked.status == "skipped" and not blocked.signals


@pytest.mark.django_db
def test_sem_site_e_so_rede_social_nao_baixam_nada(db):
    nowhere = Organization.objects.create(
        name="Escola Sem Site", kind="school", website_status="not_found"
    )
    social = Organization.objects.create(
        name="Escola Rede", kind="school", website="https://www.instagram.com/escolarede"
    )

    def boom(request):
        raise AssertionError("não deveria baixar nada")

    fetcher = PoliteFetcher(client=httpx.Client(transport=httpx.MockTransport(boom)))
    index = SuppressionIndex.load()
    assert codes(scan_organization(nowhere, fetcher, index).signals) == {"no_site"}
    assert codes(scan_organization(social, fetcher, index).signals) == {"social_only"}


@pytest.mark.django_db
def test_opt_out_nao_le_o_site(school):
    Suppression.objects.create(kind="domain", value="escolaaurora.test")
    scan = scan_organization(school, make_fetcher(page()), SuppressionIndex.load())
    assert scan.status == "suppressed"


@pytest.mark.django_db
def test_pendentes_so_com_site_ou_sem_site_confirmado_e_frescor(school):
    unknown = Organization.objects.create(name="Escola Nunca Pesquisada", kind="school")
    nowhere = Organization.objects.create(
        name="Escola Sem Site", kind="school", website_status="not_found"
    )
    assert set(pending_organizations()) == {school, nowhere}
    assert unknown not in pending_organizations()
    apply_scan(school, scan_organization(school, make_fetcher(page()), SuppressionIndex.load()))
    assert set(pending_organizations()) == {nowhere}
    assert school in pending_organizations(refresh=True)


# --- comando -----------------------------------------------------------------------------------
@pytest.fixture
def web(monkeypatch):
    holder = {"home": page(head=VIEWPORT, year=2013)}

    def factory(**kwargs):
        return make_fetcher(holder["home"], **kwargs)

    monkeypatch.setattr("collection.management.commands.web_signals.PoliteFetcher", factory)
    return holder


@pytest.mark.django_db
def test_comando_grava_e_resume_so_com_contagens(school, web):
    out = StringIO()
    call_command("web_signals", stdout=out)
    text = out.getvalue()
    assert "1 de 1 organizações" in text and "1 old_copyright" in text
    assert school.name not in text and SITE not in text  # logs públicos: sem dado identificável
    assert evidence(school, "web.signal.old_copyright").exists()
    out = StringIO()
    call_command("web_signals", stdout=out)  # já checada: nada a fazer
    assert "0 de 0" in out.getvalue()


@pytest.mark.django_db
def test_dry_run_nao_grava(school, web):
    out = StringIO()
    call_command("web_signals", "--dry-run", stdout=out)
    assert out.getvalue().startswith("[dry-run]") and "1 old_copyright" in out.getvalue()
    assert not Evidence.objects.filter(object_id=school.pk).exists()


@pytest.mark.django_db
def test_limite_invalido():
    with pytest.raises(CommandError):
        call_command("web_signals", "--limit", "0")
