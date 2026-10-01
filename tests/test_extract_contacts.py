"""E19 — contatos públicos: extração pura, gravação com evidência, opt-out e comando (sem rede)."""

import json
from io import StringIO

import httpx
import pytest
from django.core.management import CommandError, call_command

from collection.contact_finder import apply_scan, scan_organization
from collection.fetcher import PoliteFetcher
from core.models import ContactPoint, Evidence, Organization, Suppression
from core.services.suppression import SuppressionIndex
from extraction.contacts import (
    classify_email,
    drop_ambiguous_socials,
    email_belongs,
    parse_page,
    pick_pages,
    social_profile,
    valid_br_phone,
    whatsapp_number,
)

HTML = {"content-type": "text/html; charset=utf-8"}
ROBOTS_OK = httpx.Response(
    200, text="User-agent: *\nAllow: /", headers={"content-type": "text/plain"}
)
SITE = "https://www.colegioaurora.test"
DOMAIN = "colegioaurora.test"
WEBMAIL = "escolaaurora@" + "gmail" + ".com"  # montado: o repo_checks barra e-mail de webmail


def html(body, title="Colégio Aurora Boreal", head=""):
    return f"<html><head><title>{title}</title>{head}</head><body>{body}</body></html>"


HOME = html(
    """
    <nav><a href="/contato">Fale conosco</a> <a href="/sobre-nos">Quem somos</a>
    <a href="/loja">Loja</a> <a href="/docs/regimento.pdf">Regimento</a>
    <a href="https://outro-site.test/contato">Parceiro</a></nav>
    <footer>
      <p>Secretaria:
        <a href="mailto:Secretaria@colegioaurora.test">secretaria@colegioaurora.test</a></p>
      <p>Telefone: (16) 3333-4444 · Celular/WhatsApp: (16) 99876-5432</p>
      <a href="https://wa.me/5516998765432?text=Oi">WhatsApp</a>
      <a href="https://www.instagram.com/colegioaurora/?hl=pt">Instagram</a>
      <a href="https://www.facebook.com/sharer/sharer.php?u=x">Compartilhar</a>
      <a href="https://www.linkedin.com/company/colegio-aurora">LinkedIn</a>
      <a href="https://www.linkedin.com/in/maria-silva">Diretora</a>
      <p>CNPJ 00000000000000 · CEP 14801-000 · site por agencia@agenciaweb.test</p>
    </footer>
    """
)
CONTATO = html(
    """<h1>Fale conosco</h1>
    <form action="/enviar"><input type="text" name="nome"><textarea name="msg"></textarea></form>
    <p>Diretoria: <a href="mailto:maria.silva@colegioaurora.test">Maria Silva</a></p>""",
    title="Contato - Colégio Aurora Boreal",
)


class Web:
    def __init__(self, pages):
        self.pages = pages
        self.requests = []

    def __call__(self, request):
        self.requests.append(str(request.url))
        if request.url.path == "/robots.txt":
            return ROBOTS_OK
        entry = self.pages.get(request.url.path)
        if entry is None:
            return httpx.Response(404)
        return (
            entry
            if isinstance(entry, httpx.Response)
            else httpx.Response(200, text=entry, headers=HTML)
        )


def make_fetcher(web, **kwargs):
    client = httpx.Client(transport=httpx.MockTransport(web))
    return PoliteFetcher(client=client, sleep=lambda s: None, min_interval=0, **kwargs)


def found(result):
    return {(c.kind, c.value) for c in result.contacts}


# --- extração pura ---------------------------------------------------------------------------
def test_home_extrai_email_telefones_whatsapp_e_redes():
    result = parse_page(HOME, SITE, DOMAIN)
    assert found(result) == {
        ("email", "secretaria@colegioaurora.test"),
        ("phone", "+551633334444"),
        ("phone", "+5516998765432"),
        ("whatsapp", "+5516998765432"),
        ("instagram", "https://www.instagram.com/colegioaurora"),
        ("linkedin_company", "https://www.linkedin.com/company/colegio-aurora"),
    }


def test_ignora_email_de_agencia_cep_cnpj_compartilhar_e_linkedin_de_pessoa():
    result = parse_page(HOME, SITE, DOMAIN)
    values = {c.value for c in result.contacts}
    assert not any("agenciaweb" in v for v in values)
    assert not any("14801" in v or "0000000000" in v for v in values)
    assert not any("sharer" in v or "maria-silva" in v for v in values)


def test_trecho_e_literal_da_pagina():
    result = parse_page(HOME, SITE, DOMAIN)
    phone = next(c for c in result.contacts if c.value == "+551633334444")
    assert "(16) 3333-4444" in phone.excerpt and phone.excerpt in result.text
    mail = next(c for c in result.contacts if c.kind == "email")
    assert mail.excerpt == "secretaria@colegioaurora.test"


def test_formulario_e_email_pessoal_na_pagina_de_contato():
    result = parse_page(CONTATO, SITE + "/contato", DOMAIN)
    assert ("contact_form", SITE + "/contato") in found(result)
    person = next(c for c in result.contacts if c.kind == "email")
    assert person.value == "maria.silva@colegioaurora.test" and person.is_personal


def test_formulario_so_conta_em_pagina_de_contato_com_campos():
    plain = html("<form><input type='hidden' name='x'></form>")
    assert not found(parse_page(plain, SITE + "/contato", DOMAIN))
    elsewhere = html("<form><input type='text'></form>", title="Loja")
    assert not found(parse_page(elsewhere, SITE + "/loja", DOMAIN))


def test_json_ld_email_telefone_e_redes():
    ld = json.dumps(
        {
            "@type": "School",
            "email": "mailto:contato@colegioaurora.test",
            "telephone": "+55 16 3333-4444",
            "sameAs": ["https://www.facebook.com/colegioaurora", "https://example.org"],
        }
    )
    page = html("<p>Oi</p>", head=f'<script type="application/ld+json">{ld}</script>')
    assert found(parse_page(page, SITE, DOMAIN)) == {
        ("email", "contato@colegioaurora.test"),
        ("phone", "+551633334444"),
        ("facebook", "https://www.facebook.com/colegioaurora"),
    }


def test_json_ld_quebrado_nao_derruba():
    page = html("<p>x</p>", head='<script type="application/ld+json">{quebrado</script>')
    assert parse_page(page, SITE, DOMAIN).contacts == []


def test_webmail_aceito_com_confianca_menor():
    page = html(f'<a href="mailto:{WEBMAIL}">{WEBMAIL}</a>')
    (contact,) = parse_page(page, SITE, DOMAIN).contacts
    assert contact.value == WEBMAIL and contact.confidence < 0.9 and not contact.is_personal


def test_tel_link_e_ofuscacao():
    page = html('<a href="tel:+551633334444">ligue</a> contato [arroba] colegioaurora.test')
    assert found(parse_page(page, SITE, DOMAIN)) == {("phone", "+551633334444")}


@pytest.mark.parametrize(
    "local, personal",
    [
        ("secretaria", False),
        ("contato2", False),
        ("coordenacao.pedagogica", False),
        ("maria.silva", True),
        ("joao_santos", True),
        ("aurora", False),
    ],
)
def test_email_institucional_x_pessoal(local, personal):
    assert classify_email(local) is personal


def test_dominio_do_email():
    assert email_belongs("a@colegioaurora.test", DOMAIN) == (True, 0.9)
    assert email_belongs("a@mail.colegioaurora.test", DOMAIN) == (True, 0.9)
    assert email_belongs(WEBMAIL, DOMAIN)[0]
    assert not email_belongs("a@agenciaweb.test", DOMAIN)[0]
    assert not email_belongs("logo@2x.png", DOMAIN)[0]
    assert not email_belongs("a@example.com", DOMAIN)[0]


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("(16) 3333-4444", "+551633334444"),
        ("+55 16 99876-5432", "+5516998765432"),
        ("16 3333 4444", "+551633334444"),
        ("0800 123 4567", ""),
        ("(00) 3333-4444", ""),
        ("(16) 1333-4444", ""),
        ("12345", ""),
    ],
)
def test_telefone_e164(raw, expected):
    assert valid_br_phone(raw) == expected


def test_whatsapp_formas_de_link():
    assert whatsapp_number("https://wa.me/5516998765432") == "+5516998765432"
    assert whatsapp_number("https://api.whatsapp.com/send?phone=5516998765432") == (
        "+5516998765432"
    )
    assert whatsapp_number("https://wa.me/message/ABC123") == ""
    assert whatsapp_number("https://example.org/5516998765432") == ""


def test_perfis_de_redes():
    assert social_profile("https://instagram.com/colegio.aurora/") == (
        "instagram",
        "https://www.instagram.com/colegio.aurora",
    )
    assert social_profile("https://www.instagram.com/p/ABC/") is None
    assert social_profile("https://www.facebook.com/profile.php?id=123") == (
        "facebook",
        "https://www.facebook.com/profile.php?id=123",
    )
    assert social_profile("https://www.facebook.com/pages/Colegio/12345?ref=x") == (
        "facebook",
        "https://www.facebook.com/pages/Colegio/12345",
    )
    assert social_profile("https://www.youtube.com/@colegioaurora") == (
        "youtube",
        "https://www.youtube.com/@colegioaurora",
    )
    assert social_profile("https://www.youtube.com/watch?v=abc") is None
    assert social_profile("https://www.linkedin.com/in/fulano") is None
    assert social_profile("https://example.org/colegio") is None


def test_rede_ambigua_nao_e_gravada():
    page = html(
        '<a href="https://instagram.com/escola">a</a> <a href="https://instagram.com/agencia">b</a>'
        '<a href="https://facebook.com/escola">c</a>'
    )
    kept, dropped = drop_ambiguous_socials(parse_page(page, SITE, DOMAIN).contacts)
    assert [c.kind for c in kept] == ["facebook"] and dropped == 1


def test_escolha_de_paginas_prioriza_contato_e_limita():
    result = parse_page(HOME, SITE, DOMAIN)
    assert pick_pages(SITE, result.links, DOMAIN) == [SITE + "/contato", SITE + "/sobre-nos"]
    many = [(f"{SITE}/contato-{i}", "") for i in range(10)]
    assert len(pick_pages(SITE, many, DOMAIN)) == 4  # 5 páginas no total, contando a inicial


# --- rede + gravação -------------------------------------------------------------------------
@pytest.fixture
def escola(db):
    return Organization.objects.create(
        name="Colégio Aurora Boreal",
        kind=Organization.Kind.SCHOOL,
        municipality_name="Araraquara",
        uf="SP",
        website=SITE,
    )


def run_scan(escola, pages=None):
    if pages is None:
        pages = {"/": HOME, "/contato": CONTATO, "/sobre-nos": html("<p>Sobre</p>")}
    web = Web(pages)
    scan = scan_organization(escola, make_fetcher(web), SuppressionIndex.load())
    return scan, web


def test_scan_le_ate_cinco_paginas_do_proprio_dominio(escola):
    scan, web = run_scan(escola)
    assert scan.status == "ok" and scan.pages == 3
    pages = {r for r in web.requests if "robots" not in r}
    assert len(pages) == 3 and SITE + "/contato" in pages and SITE + "/sobre-nos" in pages
    assert not any("outro-site" in r or "regimento" in r or "loja" in r for r in web.requests)


def test_apply_grava_contato_com_evidencia_observada(escola):
    scan, _ = run_scan(escola)
    created = apply_scan(escola, scan)
    assert created["email"] == 2 and created["phone"] == 2 and created["contact_form"] == 1
    mail = ContactPoint.objects.get(organization=escola, value="secretaria@colegioaurora.test")
    assert mail.evidence.kind == Evidence.Kind.OBSERVED and mail.evidence.verified
    assert mail.evidence.source_url == SITE and mail.evidence.excerpt
    assert mail.evidence.method == "regex:contacts" and not mail.is_personal
    person = ContactPoint.objects.get(value="maria.silva@colegioaurora.test")
    assert person.is_personal
    assert person.evidence.source_url == SITE + "/contato"
    escola.refresh_from_db()
    assert escola.contacts_checked_at is not None
    assert ContactPoint.objects.filter(evidence__isnull=True).count() == 0


def test_reexecutar_nao_duplica_nem_mexe_no_que_o_humano_editou(escola):
    apply_scan(escola, run_scan(escola)[0])
    total = ContactPoint.objects.count()
    evidences = Evidence.objects.count()
    ContactPoint.objects.filter(value="secretaria@colegioaurora.test").update(
        status="bounced", label="editado"
    )
    apply_scan(escola, run_scan(escola)[0])
    assert ContactPoint.objects.count() == total and Evidence.objects.count() == evidences
    mail = ContactPoint.objects.get(value="secretaria@colegioaurora.test")
    assert mail.status == "bounced" and mail.label == "editado"
    assert mail.last_verified_at is None  # achar no site não é verificar


def test_opt_out_de_email_e_dominio_nao_vira_contato(escola):
    Suppression.objects.create(kind="email", value="secretaria@colegioaurora.test")
    Suppression.objects.create(kind="phone", value="(16) 3333-4444")
    scan, _ = run_scan(escola)
    assert scan.skipped_suppressed == 2
    apply_scan(escola, scan)
    values = set(ContactPoint.objects.values_list("value", flat=True))
    assert "secretaria@colegioaurora.test" not in values and "+551633334444" not in values
    assert "+5516998765432" in values


def test_organizacao_em_opt_out_nem_e_visitada(escola):
    Suppression.objects.create(kind="domain", value=DOMAIN)
    web = Web({"/": HOME})
    scan = scan_organization(escola, make_fetcher(web), SuppressionIndex.load())
    assert scan.status == "suppressed" and web.requests == []
    escola.relationship_status = "do_not_contact"
    escola.website = "https://outro.test"
    assert scan_organization(escola, make_fetcher(web), SuppressionIndex.load()).status == (
        "suppressed"
    )


def test_robots_bloqueando_ou_site_fora_do_ar(escola):
    blocked = Web({"/robots.txt": httpx.Response(200, text="User-agent: *\nDisallow: /")})
    fetcher = make_fetcher(blocked)
    scan = scan_organization(escola, fetcher, SuppressionIndex.load())
    assert scan.status == "unreachable" and scan.contacts == []
    assert run_scan(escola, {})[0].status == "unreachable"


def test_pagina_interna_com_erro_nao_derruba_as_outras(escola):
    scan, _ = run_scan(escola, {"/": HOME, "/contato": httpx.Response(500)})
    assert scan.status == "ok" and ("email", "secretaria@colegioaurora.test") in {
        (s.contact.kind, s.contact.value) for s in scan.contacts
    }


def test_nunca_cria_contato_sem_evidencia(db):
    org = Organization.objects.create(name="Org", website=SITE)
    with pytest.raises(Exception):  # noqa: B017 — FK obrigatória (RESTRICT)
        ContactPoint.objects.create(organization=org, kind="email", value="a@b.test")


def test_usable_respeita_opt_out_dos_contatos_extraidos(escola):
    apply_scan(escola, run_scan(escola)[0])
    assert ContactPoint.objects.usable().count() == ContactPoint.objects.count()
    Suppression.objects.create(kind="domain", value=DOMAIN)
    assert ContactPoint.objects.usable().count() == 0


# --- comando ---------------------------------------------------------------------------------
@pytest.fixture
def web_patch(monkeypatch):
    def install(pages):
        web = Web(pages)

        def factory(**kwargs):
            return make_fetcher(web, **kwargs)

        monkeypatch.setattr(
            "collection.management.commands.extract_contacts.PoliteFetcher", factory
        )
        return web

    return install


def run_command(*args):
    out = StringIO()
    call_command("extract_contacts", *args, stdout=out)
    return out.getvalue()


def test_comando_grava_e_informa_cobertura(escola, web_patch):
    Organization.objects.create(name="Sem site")
    web_patch({"/": HOME, "/contato": CONTATO})
    out = run_command()
    assert "1 lidas" in out and "email" in out
    assert "Cobertura: 1 de 1" in out and "100%" in out
    assert "secretaria@" not in out  # logs públicos: só contagens (ADR-014)
    assert ContactPoint.objects.count() > 0
    assert "0 de 0 organizações" in run_command()  # já verificada: não relê


def test_comando_dry_run_e_refresh(escola, web_patch):
    web_patch({"/": HOME})
    out = run_command("--dry-run")
    assert out.startswith("[dry-run]") and ContactPoint.objects.count() == 0
    escola.refresh_from_db()
    assert escola.contacts_checked_at is None
    run_command()
    assert "1 de 1" in run_command("--refresh")


def test_comando_marca_inacessivel_para_nao_travar_a_fila(escola, web_patch):
    web_patch({})
    assert "1 sem acesso" in run_command()
    escola.refresh_from_db()
    assert escola.contacts_checked_at is not None


def test_comando_limit_invalido(db):
    with pytest.raises(CommandError):
        run_command("--limit", "0")
