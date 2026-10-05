"""E18 — site oficial: busca com cache, validação e comando (respostas gravadas, sem rede)."""

import json
from io import StringIO

import httpx
import pytest
from django.core.management import CommandError, call_command

from collection.fetcher import PoliteFetcher
from collection.models import SearchQuery
from collection.search import SearchBudgetExceeded, SearchError, SearchResult, get_provider
from collection.search.brave import BraveProvider
from collection.search.serper import SerperProvider
from collection.website_finder import apply_decision, build_query, find_website, known_domains
from core.models import Evidence, Organization
from extraction.website import (
    canonical_site_url,
    decide,
    evaluate_candidate,
    is_blocked_domain,
    name_tokens,
    site_key,
)

HTML = {"content-type": "text/html; charset=utf-8"}
ROBOTS_OK = httpx.Response(
    200, text="User-agent: *\nAllow: /", headers={"content-type": "text/plain"}
)


def page(title, body):
    script = "<script>var x='Escola Ruído'</script>"
    return f"<html><head><title>{title}</title>{script}</head><body>{body}</body></html>"


SITE_CERTO = page(
    "Colégio Aurora Boreal - Início",
    "<h1>Colégio Aurora Boreal</h1><p>Rua das Flores, 100 - Araraquara/SP. Ensino fundamental.</p>",
)
SITE_HOMONIMO = page(
    "Colégio Aurora Boreal", "<h1>Colégio Aurora Boreal</h1><p>Av. Central, 5 - Franca/SP</p>"
)
SITE_OUTRO = page("Padaria do Zé", "<p>Pão quente em Araraquara</p>")


class Web:
    """Internet falsa: host → HTML (ou resposta); robots.txt liberado."""

    def __init__(self, hosts):
        self.hosts = hosts
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        if request.url.path == "/robots.txt":
            return ROBOTS_OK
        entry = self.hosts.get(request.url.host)
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


class FakeProvider:
    """Provedor com respostas gravadas; reaproveita o cache real de `SearchProvider.search`."""

    name = "fake"

    def __init__(self, serp):
        from collection.search.base import SearchProvider

        class _P(SearchProvider):
            name = "fake"

            def _request(inner, query, num):
                self.queries.append(query)
                return [SearchResult(*r) for r in serp.get(query, [])]

        self.queries = []
        self.provider = _P("chave", client=httpx.Client(), max_calls=None)

    def __getattr__(self, item):
        return getattr(self.provider, item)

    def search(self, query, **kwargs):
        return self.provider.search(query, **kwargs)


@pytest.fixture
def escola(db):
    return Organization.objects.create(
        name="Colégio Aurora Boreal",
        kind=Organization.Kind.SCHOOL,
        municipality_name="Araraquara",
        uf="SP",
    )


QUERY = "Colégio Aurora Boreal Araraquara SP"


def run_find(escola, serp, hosts, **kwargs):
    provider = FakeProvider({QUERY: serp})
    web = Web(hosts)
    decision = find_website(escola, provider, make_fetcher(web), **kwargs)
    return decision, provider, web


# --- validação (pura) ------------------------------------------------------------------------
def test_dominios_bloqueados_por_sufixo():
    assert is_blocked_domain("https://www.facebook.com/aurora")
    assert is_blocked_domain("https://pt-br.facebook.com/aurora")
    assert is_blocked_domain("https://www.escolas.com.br/escola/aurora")
    assert not is_blocked_domain("https://auroraboreal.com.br")
    assert not is_blocked_domain("https://notfacebook.com")
    assert not is_blocked_domain("https://escola.araraquara.sp.gov.br")
    assert is_blocked_domain("https://www.querobolsa.com.br/escolas/aurora")
    assert is_blocked_domain("https://www.melhorescola.com.br/escola/aurora")
    assert is_blocked_domain("http://177.21.38.106/Siave/arquivo?Id=1")  # IP puro


def test_site_key_agrupa_subdominios():
    assert site_key("lp.escola.com.br") == site_key("escola.com.br") == "escola.com.br"
    assert site_key("aurora.net.br") != site_key("aurora.com.br")
    assert site_key("escola.org") == "escola.org"


def test_tokens_ignoram_palavras_genericas():
    assert name_tokens("Escola Municipal Prof. Maria da Silva") == ["maria", "silva"]
    assert name_tokens("EMEF") == ["emef"]  # só genérico: cai para tudo, nunca fica vazio


def test_url_canonica_vira_raiz_quando_e_pagina_inicial():
    assert canonical_site_url("https://x.com.br/index.php?a=1") == "https://x.com.br"
    assert canonical_site_url("https://x.com.br/") == "https://x.com.br"
    assert canonical_site_url("https://prefeitura.sp.gov.br/escolas/aurora?utm=1") == (
        "https://prefeitura.sp.gov.br/escolas/aurora"
    )


def test_texto_do_html_ignora_script():
    verdict = evaluate_candidate(
        SearchResult("x", "https://aurora.com.br"),
        name="Escola Ruído Verde",
        municipality="Araraquara",
        page_html=page("Outro", "<p>Araraquara</p>"),
    )
    assert verdict.verdict == "reject"  # "Ruído" só existe dentro do <script>


def test_decide_vazio_e_nao_encontrado():
    assert decide([]).status == "not_found"


# --- find_website ----------------------------------------------------------------------------
def test_site_certo_e_encontrado(escola):
    serp = [
        ("Colégio Aurora Boreal", "https://auroraboreal.com.br/index.html", "Ensino"),
        ("Aurora no Facebook", "https://www.facebook.com/auroraboreal", ""),
    ]
    decision, _, web = run_find(escola, serp, {"auroraboreal.com.br": SITE_CERTO})
    assert decision.status == "found"
    assert decision.url == "https://auroraboreal.com.br"
    assert not any(r.url.host == "www.facebook.com" for r in web.requests)  # bloqueado: nem baixa


def test_diretorio_e_rede_social_nunca_viram_site(escola):
    serp = [
        (
            "Aurora - Escolas.com.br",
            "https://www.escolas.com.br/aurora",
            "Colégio Aurora Boreal Araraquara",
        ),
        ("Aurora", "https://www.instagram.com/auroraboreal", "Colégio Aurora Boreal Araraquara"),
    ]
    decision, _, web = run_find(escola, serp, {})
    assert decision.status == "not_found"
    assert web.requests == []


def test_homonimo_em_outra_cidade_nao_e_found(escola):
    serp = [("Colégio Aurora Boreal", "https://auroraboreal-franca.com.br", "")]
    decision, *_ = run_find(escola, serp, {"auroraboreal-franca.com.br": SITE_HOMONIMO})
    assert decision.status == "ambiguous"
    assert "município" in decision.reason


def test_pagina_sem_relacao_e_nao_encontrado(escola):
    serp = [("Padaria", "https://padariadoze.com.br", "Colégio Aurora Boreal Araraquara")]
    decision, *_ = run_find(escola, serp, {"padariadoze.com.br": SITE_OUTRO})
    assert decision.status == "not_found"


def test_dois_dominios_que_conferem_viram_ambiguo(escola):
    serp = [
        ("Aurora", "https://auroraboreal.com.br", ""),
        ("Aurora", "https://auroraboreal.net.br", ""),
    ]
    hosts = {"auroraboreal.com.br": SITE_CERTO, "auroraboreal.net.br": SITE_CERTO}
    decision, *_ = run_find(escola, serp, hosts)
    assert decision.status == "ambiguous"
    assert len(decision.candidates) == 2


def test_pagina_que_nao_baixa_no_maximo_fraco(escola):
    serp = [("Colégio Aurora Boreal", "https://auroraboreal.com.br", "Araraquara, SP")]
    decision, *_ = run_find(escola, serp, {"auroraboreal.com.br": httpx.Response(403)})
    assert decision.status == "ambiguous"  # nunca found sem ler a página


def test_robots_que_proibe_impede_found(escola):
    class Robots(Web):
        def __call__(self, request):
            if request.url.path == "/robots.txt":
                return httpx.Response(200, text="User-agent: *\nDisallow: /")
            return super().__call__(request)

    provider = FakeProvider({QUERY: [("Aurora", "https://auroraboreal.com.br", "Araraquara")]})
    web = Robots({"auroraboreal.com.br": SITE_CERTO})
    decision = find_website(escola, provider, make_fetcher(web))
    assert decision.status != "found"
    assert not any(r.url.path == "/" for r in web.requests)


def test_dominio_ja_usado_por_outra_organizacao_vira_ambiguo(escola):
    Organization.objects.create(
        name="Outra", kind="school", website="https://www.auroraboreal.com.br/inicio"
    )
    serp = [("Aurora", "https://auroraboreal.com.br", "")]
    decision, *_ = run_find(
        escola, serp, {"auroraboreal.com.br": SITE_CERTO}, taken=known_domains()
    )
    assert decision.status == "ambiguous"
    assert "outra organização" in decision.reason


def test_consulta_nunca_se_repete(escola):
    serp = [("Aurora", "https://auroraboreal.com.br", "")]
    decision, provider, _ = run_find(escola, serp, {"auroraboreal.com.br": SITE_CERTO})
    find_website(escola, provider, make_fetcher(Web({"auroraboreal.com.br": SITE_CERTO})))
    assert provider.queries == [QUERY]  # a 2ª veio do cache
    assert provider.cache_hits == 1
    assert SearchQuery.objects.count() == 1


# --- gravação --------------------------------------------------------------------------------
def test_found_grava_site_e_evidencia_inferida_verificada(escola):
    serp = [("Colégio Aurora Boreal", "https://auroraboreal.com.br/index.html", "")]
    decision, *_ = run_find(escola, serp, {"auroraboreal.com.br": SITE_CERTO})
    apply_decision(escola, decision, provider_name="fake")
    escola.refresh_from_db()
    assert (escola.website, escola.website_status) == ("https://auroraboreal.com.br", "found")
    evidence = Evidence.objects.get(field="website")
    assert evidence.kind == "inferred" and evidence.method == "rule:website_match"
    assert evidence.verified  # o trecho é literal da página
    assert "Aurora Boreal" in evidence.excerpt
    assert evidence.source_url == "https://auroraboreal.com.br/index.html"


def test_ambiguo_guarda_candidatos_para_o_humano_sem_site(escola):
    serp = [("Aurora", "https://auroraboreal-franca.com.br", "")]
    decision, *_ = run_find(escola, serp, {"auroraboreal-franca.com.br": SITE_HOMONIMO})
    apply_decision(escola, decision, provider_name="fake")
    escola.refresh_from_db()
    assert (escola.website, escola.website_status) == ("", "ambiguous")
    assert list(Evidence.objects.values_list("field", flat=True)) == ["website_candidate"]


def test_nao_encontrado_so_muda_a_situacao(escola):
    decision, *_ = run_find(escola, [], {})
    apply_decision(escola, decision, provider_name="fake")
    escola.refresh_from_db()
    assert escola.website_status == "not_found" and not Evidence.objects.exists()


# --- provedores ------------------------------------------------------------------------------
def serper_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_serper_le_resultados_e_usa_cache(db):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.headers["x-api-key"] == "k"
        body = json.loads(request.content)
        assert body["q"] == "escola x" and body["gl"] == "br"
        return httpx.Response(
            200,
            json={
                "organic": [
                    {"title": "T", "link": "https://a.com.br", "snippet": "S"},
                    {"title": "sem link"},
                ]
            },
        )

    provider = SerperProvider("k", client=serper_client(handler))
    first = provider.search("escola x")
    again = provider.search("Escola  X!")  # normaliza para a mesma chave
    assert first == again == [SearchResult("T", "https://a.com.br", "S")]
    assert len(calls) == 1 and provider.calls == 1 and provider.cache_hits == 1


def test_brave_le_resultados(db):
    def handler(request):
        assert request.headers["x-subscription-token"] == "k"
        assert request.url.params["country"] == "BR"
        payload = {
            "web": {"results": [{"title": "T", "url": "https://b.com.br", "description": "D"}]}
        }
        return httpx.Response(200, json=payload)

    provider = BraveProvider("k", client=serper_client(handler))
    assert provider.search("escola y") == [SearchResult("T", "https://b.com.br", "D")]


@pytest.mark.parametrize("status", [401, 402, 429, 500])
def test_falha_do_provedor_nao_vai_para_o_cache(db, status):
    provider = SerperProvider("k", client=serper_client(lambda r: httpx.Response(status)))
    with pytest.raises(SearchError):
        provider.search("escola z")
    assert not SearchQuery.objects.exists()


def test_teto_de_buscas_conta_so_chamadas_pagas(db):
    handler = lambda r: httpx.Response(200, json={"organic": []})  # noqa: E731
    provider = SerperProvider("k", client=serper_client(handler), max_calls=1)
    provider.search("um")
    provider.search("um")  # cache: não conta
    with pytest.raises(SearchBudgetExceeded):
        provider.search("dois")


def test_provedor_sem_chave_ou_desconhecido(settings):
    settings.SERPER_API_KEY = ""
    with pytest.raises(SearchError, match="Chave"):
        get_provider("serper")
    with pytest.raises(SearchError, match="desconhecido"):
        get_provider("bing")


# --- comando ---------------------------------------------------------------------------------
@pytest.fixture
def cmd(monkeypatch):
    """Roda `find_websites` com busca e internet falsas; devolve (saída, provedor)."""

    def run(serp, hosts, *args, max_calls=None):
        provider = FakeProvider(serp)
        provider.provider.max_calls = max_calls
        web = Web(hosts)
        monkeypatch.setattr(
            "collection.management.commands.find_websites.get_provider", lambda *a, **k: provider
        )
        monkeypatch.setattr(
            "collection.management.commands.find_websites.PoliteFetcher",
            lambda **k: make_fetcher(web, **k),
        )
        out = StringIO()
        call_command("find_websites", *args, stdout=out)
        return out.getvalue(), provider

    return run


def test_comando_preenche_e_so_mostra_contagens(escola, cmd):
    serp = {QUERY: [("Aurora", "https://auroraboreal.com.br", "")]}
    out, _ = cmd(serp, {"auroraboreal.com.br": SITE_CERTO}, "--kind", "school")
    escola.refresh_from_db()
    assert escola.website_status == "found"
    assert "1 encontradas" in out and "Aurora" not in out  # sem nomes no log público


def test_comando_dry_run_nao_grava(escola, cmd):
    serp = {QUERY: [("Aurora", "https://auroraboreal.com.br", "")]}
    out, _ = cmd(serp, {"auroraboreal.com.br": SITE_CERTO}, "--dry-run")
    escola.refresh_from_db()
    assert escola.website == "" and escola.website_status == "unknown"
    assert out.startswith("[dry-run]") and not Evidence.objects.exists()


def test_details_mostra_decisao_e_motivo_so_quando_pedido(escola, cmd):
    serp = {QUERY: [("Aurora", "https://auroraboreal.com.br", "")]}
    out, _ = cmd(serp, {"auroraboreal.com.br": SITE_CERTO}, "--dry-run", "--details")
    assert "found | Colégio Aurora Boreal (Araraquara) | https://auroraboreal.com.br" in out
    assert "auroraboreal.com.br [match:" in out


def test_comando_ignora_quem_ja_tem_site_ou_foi_pesquisado(escola, cmd):
    Organization.objects.create(name="Com site", kind="school", website="https://x.com.br")
    Organization.objects.create(
        name="Já vista", kind="school", municipality_name="Bauru", website_status="not_found"
    )
    Organization.objects.create(name="Sem cidade", kind="school")
    out, provider = cmd({QUERY: []}, {})
    assert provider.queries == [QUERY]
    assert "1 de 1 processadas" in out and "1 sem município" in out


def test_comando_retry_reavalia_nao_encontradas_sem_nova_busca_paga(escola, cmd):
    cmd({QUERY: []}, {})
    out, provider = cmd({QUERY: []}, {}, "--retry")
    assert provider.queries == [] and provider.cache_hits == 1  # a busca foi paga só na 1ª vez
    assert "1 de 1 processadas" in out


def test_comando_respeita_limit_e_teto(db, cmd):
    for i in range(3):
        Organization.objects.create(
            name=f"Escola Nova {i}", kind="school", municipality_name="Araraquara", uf="SP"
        )
    out, _ = cmd({}, {}, "--limit", "2")
    assert "2 de 2 processadas" in out
    with pytest.raises(CommandError, match="Teto"):
        cmd({}, {}, "--limit", "3", max_calls=0)  # sem verba para buscas pagas


def test_build_query(escola):
    assert build_query(escola) == QUERY


def test_subdominios_do_mesmo_site_contam_uma_vez(escola):
    serp = [
        ("Aurora", "https://lp.auroraboreal.com.br/agende-uma-visita", ""),
        ("Aurora", "https://www.auroraboreal.com.br/", ""),
    ]
    hosts = {"lp.auroraboreal.com.br": SITE_CERTO, "auroraboreal.com.br": SITE_CERTO}
    decision, *_ = run_find(escola, serp, hosts)
    assert decision.status == "found"
    assert decision.url.startswith("https://lp.auroraboreal.com.br")  # o 1º resultado vale


def test_escola_ignora_resultados_em_gov_br(escola):
    serp = [
        ("Lista de escolas", "https://educacao.araraquara.sp.gov.br/escolas", ""),
        ("Colégio Aurora Boreal", "https://auroraboreal.com.br", ""),
    ]
    decision, _, web = run_find(escola, serp, {"auroraboreal.com.br": SITE_CERTO})
    assert decision.status == "found"
    assert not any(r.url.host.endswith(".gov.br") for r in web.requests)
