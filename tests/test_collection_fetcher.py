"""E04 — PoliteFetcher: robots.txt, rate limit, cache condicional, retries e limites (sem rede)."""

import gzip

import httpx
import pytest

from collection.fetcher import (
    FetchBlocked,
    FetchError,
    FetchHTTPError,
    FetchTooLarge,
    PageBudgetExceeded,
    PoliteFetcher,
    RobotsDisallowed,
    UnsupportedContent,
)
from collection.models import RawDocument

HTML = {"content-type": "text/html; charset=utf-8"}


class Clock:
    """Relógio falso: `sleep` só avança o tempo, então os testes não esperam de verdade."""

    def __init__(self):
        self.now = 1000.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class Site:
    """Servidor falso: `routes` mapeia caminho → resposta (ou lista de respostas, em ordem)."""

    def __init__(self, routes):
        self.routes = {k: (list(v) if isinstance(v, list) else [v]) for k, v in routes.items()}
        self.requests = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        queue = self.routes.get(request.url.path)
        if queue is None:
            return httpx.Response(404)
        response = queue.pop(0) if len(queue) > 1 else queue[0]
        return response() if callable(response) else response

    def paths(self):
        return [r.url.path for r in self.requests]


def make_fetcher(site, clock=None, **kwargs):
    clock = clock or Clock()
    client = httpx.Client(transport=httpx.MockTransport(site))
    fetcher = PoliteFetcher(
        client=client,
        user_agent="RadarScorpionBits/0.1 (+https://scorpionbits.com; contato@example.org)",
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        **kwargs,
    )
    return fetcher, clock


def page(text="<p>olá</p>", **headers):
    return httpx.Response(200, text=text, headers={**HTML, **headers})


pytestmark = pytest.mark.django_db
URL = "https://example.org/editais"


class TestBasics:
    def test_downloads_stores_text_and_identifies_itself(self):
        site = Site({"/robots.txt": httpx.Response(404), "/editais": page("<p>Edital 2027</p>")})
        fetcher, _ = make_fetcher(site)
        result = fetcher.fetch(URL)
        assert result.text == "<p>Edital 2027</p>"
        assert not result.from_cache
        assert result.changed
        document = RawDocument.objects.get(url=URL)
        assert document.text == "<p>Edital 2027</p>"
        assert document.content_hash
        assert document.expires_at > document.fetched_at
        assert gzip.decompress(bytes(document.text_gz)).decode() == "<p>Edital 2027</p>"
        agent = site.requests[-1].headers["user-agent"]
        assert agent.startswith("RadarScorpionBits/") and "scorpionbits.com" in agent

    def test_http_errors_that_are_not_retryable_are_not_retried(self):
        site = Site({"/robots.txt": httpx.Response(404), "/editais": httpx.Response(404)})
        fetcher, clock = make_fetcher(site)
        with pytest.raises(FetchHTTPError) as error:
            fetcher.fetch(URL)
        assert error.value.status_code == 404
        assert site.paths().count("/editais") == 1
        assert RawDocument.objects.count() == 0

    def test_binary_content_is_not_stored(self):
        pdf = httpx.Response(200, content=b"%PDF-1.7", headers={"content-type": "application/pdf"})
        fetcher, _ = make_fetcher(Site({"/robots.txt": httpx.Response(404), "/editais": pdf}))
        with pytest.raises(UnsupportedContent):
            fetcher.fetch(URL)
        assert RawDocument.objects.count() == 0

    def test_json_and_xml_variants_are_text(self):
        site = Site(
            {
                "/robots.txt": httpx.Response(404),
                "/a": httpx.Response(200, json={"ok": 1}),
                "/b": httpx.Response(
                    200, text="<x/>", headers={"content-type": "application/atom+xml"}
                ),
            }
        )
        fetcher, _ = make_fetcher(site, min_interval=0)
        assert fetcher.fetch("https://example.org/a").text == '{"ok":1}'
        assert fetcher.fetch("https://example.org/b").text == "<x/>"

    def test_size_limit_by_header_and_by_streaming(self):
        big = httpx.Response(200, content=b"x" * 2000, headers={"content-type": "text/plain"})
        fetcher, _ = make_fetcher(
            Site({"/robots.txt": httpx.Response(404), "/editais": big}), max_bytes=1000
        )
        with pytest.raises(FetchTooLarge):
            fetcher.fetch(URL)

        streamed = httpx.Response(
            200, content=iter([b"x" * 600, b"x" * 600]), headers={"content-type": "text/plain"}
        )
        fetcher, _ = make_fetcher(
            Site({"/robots.txt": httpx.Response(404), "/editais": streamed}), max_bytes=1000
        )
        with pytest.raises(FetchTooLarge):
            fetcher.fetch(URL)

    def test_page_budget_per_run(self):
        site = Site({"/robots.txt": httpx.Response(404), "/a": page(), "/b": page()})
        fetcher, _ = make_fetcher(site, max_requests=1, min_interval=0)
        fetcher.fetch("https://example.org/a")
        with pytest.raises(PageBudgetExceeded):
            fetcher.fetch("https://example.org/b")

    def test_redirects_are_followed_and_each_hop_checks_robots(self):
        site = Site(
            {
                "/robots.txt": httpx.Response(404),
                "/old": httpx.Response(301, headers={"location": "/new"}),
                "/new": page("novo"),
            }
        )
        fetcher, _ = make_fetcher(site, min_interval=0)
        result = fetcher.fetch("https://example.org/old")
        assert result.text == "novo"
        assert result.url == "https://example.org/new"

    def test_redirect_loops_stop(self):
        site = Site(
            {
                "/robots.txt": httpx.Response(404),
                "/a": httpx.Response(302, headers={"location": "/a"}),
            }
        )
        fetcher, _ = make_fetcher(site, min_interval=0)
        with pytest.raises(FetchError, match="Redirecionamentos"):
            fetcher.fetch("https://example.org/a")


class TestRobots:
    ROBOTS = "User-agent: *\nDisallow: /privado/\n"

    def test_disallowed_path_is_not_downloaded(self):
        site = Site({"/robots.txt": httpx.Response(200, text=self.ROBOTS), "/privado/x": page()})
        fetcher, _ = make_fetcher(site)
        with pytest.raises(RobotsDisallowed):
            fetcher.fetch("https://example.org/privado/x")
        assert "/privado/x" not in site.paths()

    def test_allowed_path_passes_and_robots_is_cached_for_a_day(self):
        site = Site(
            {
                "/robots.txt": httpx.Response(200, text=self.ROBOTS),
                "/a": page(),
                "/b": page(),
            }
        )
        fetcher, clock = make_fetcher(site, min_interval=0)
        fetcher.fetch("https://example.org/a")
        fetcher.fetch("https://example.org/b")
        assert site.paths().count("/robots.txt") == 1
        clock.now += 25 * 3600
        fetcher.fetch("https://example.org/a")
        assert site.paths().count("/robots.txt") == 2

    def test_our_user_agent_token_is_honoured(self):
        robots = "User-agent: RadarScorpionBits\nDisallow: /\n"
        site = Site({"/robots.txt": httpx.Response(200, text=robots), "/a": page()})
        fetcher, _ = make_fetcher(site)
        with pytest.raises(RobotsDisallowed):
            fetcher.fetch("https://example.org/a")

    def test_missing_robots_means_no_restrictions(self):
        site = Site({"/robots.txt": httpx.Response(404), "/a": page()})
        fetcher, _ = make_fetcher(site)
        assert fetcher.fetch("https://example.org/a").text

    @pytest.mark.parametrize("status", [401, 403, 500])
    def test_unavailable_or_forbidden_robots_blocks_everything(self, status):
        site = Site({"/robots.txt": httpx.Response(status), "/a": page()})
        fetcher, _ = make_fetcher(site, max_retries=0)
        with pytest.raises(RobotsDisallowed):
            fetcher.fetch("https://example.org/a")
        assert "/a" not in site.paths()

    def test_robots_unreachable_blocks_everything(self):
        def boom(request):
            raise httpx.ConnectError("sem rede")

        client = httpx.Client(transport=httpx.MockTransport(boom))
        clock = Clock()
        fetcher = PoliteFetcher(
            client=client, sleep=clock.sleep, monotonic=clock.monotonic, max_retries=1
        )
        with pytest.raises(RobotsDisallowed):
            fetcher.fetch("https://example.org/a")

    def test_each_domain_has_its_own_robots(self):
        site = Site({"/robots.txt": httpx.Response(404), "/a": page()})
        fetcher, _ = make_fetcher(site, min_interval=0)
        fetcher.fetch("https://example.org/a")
        fetcher.fetch("https://other.example.com/a")
        assert site.paths().count("/robots.txt") == 2


class TestRateLimit:
    def test_waits_between_requests_to_the_same_domain(self):
        site = Site({"/robots.txt": httpx.Response(404), "/a": page(), "/b": page()})
        fetcher, clock = make_fetcher(site, min_interval=5)
        fetcher.fetch("https://example.org/a")
        clock.sleeps.clear()
        fetcher.fetch("https://example.org/b")
        assert clock.sleeps == [5]

    def test_no_wait_when_enough_time_has_passed(self):
        site = Site({"/robots.txt": httpx.Response(404), "/a": page()})
        fetcher, clock = make_fetcher(site, min_interval=5)
        fetcher.fetch("https://example.org/a")
        clock.now += 10
        clock.sleeps.clear()
        fetcher.fetch("https://example.org/a")
        assert clock.sleeps == []


class TestRetries:
    def test_503_is_retried_with_exponential_backoff(self):
        site = Site(
            {
                "/robots.txt": httpx.Response(404),
                "/editais": [httpx.Response(503), httpx.Response(503), page("ok")],
            }
        )
        fetcher, clock = make_fetcher(site, min_interval=0)
        assert fetcher.fetch(URL).text == "ok"
        assert site.paths().count("/editais") == 3
        assert clock.sleeps == [2.0, 4.0]

    def test_429_honours_retry_after(self):
        site = Site(
            {
                "/robots.txt": httpx.Response(404),
                "/editais": [httpx.Response(429, headers={"retry-after": "7"}), page("ok")],
            }
        )
        fetcher, clock = make_fetcher(site, min_interval=0)
        fetcher.fetch(URL)
        assert clock.sleeps == [7.0]

    def test_gives_up_after_the_retry_limit(self):
        site = Site({"/robots.txt": httpx.Response(404), "/editais": httpx.Response(503)})
        fetcher, _ = make_fetcher(site, min_interval=0, max_retries=3)
        with pytest.raises(FetchHTTPError) as error:
            fetcher.fetch(URL)
        assert error.value.status_code == 503
        assert site.paths().count("/editais") == 4  # 1 + 3 retries

    def test_timeouts_are_retried_then_reported_without_the_url_details(self):
        calls = []

        def slow(request):
            if request.url.path == "/robots.txt":
                return httpx.Response(404)
            calls.append(1)
            raise httpx.ReadTimeout("lento")

        fetcher, _ = make_fetcher(slow, min_interval=0, max_retries=2)
        with pytest.raises(FetchError, match="Falha de rede"):
            fetcher.fetch(URL)
        assert len(calls) == 3

    def test_total_deadline_stops_slow_retry_chains(self):
        """429 com Retry-After longo em sequência não prende a coleta por minutos (ADR-029)."""
        site = Site(
            {
                "/robots.txt": httpx.Response(404),
                "/editais": httpx.Response(429, headers={"retry-after": "60"}),
            }
        )
        fetcher, clock = make_fetcher(site, min_interval=0, max_seconds=90)
        with pytest.raises(FetchError, match="Prazo de 90 s"):
            fetcher.fetch(URL)
        assert sum(clock.sleeps) <= 90
        assert site.paths().count("/editais") == 2

    def test_stats_separate_network_from_waiting(self):
        site = Site(
            {
                "/robots.txt": httpx.Response(404),
                "/editais": [httpx.Response(503), page("ok")],
            }
        )
        fetcher, _ = make_fetcher(site, min_interval=0)
        fetcher.fetch(URL)
        stats = fetcher.stats
        assert (stats.requests, stats.attempts, stats.retries) == (1, 3, 1)  # robots + 503 + 200
        assert stats.wait_seconds == 2.0
        assert "1 retry" in stats.summary()


class TestBlocked:
    @pytest.mark.parametrize("status", [401, 403])
    def test_login_or_forbidden_is_never_circumvented(self, status):
        site = Site({"/robots.txt": httpx.Response(404), "/editais": httpx.Response(status)})
        fetcher, _ = make_fetcher(site)
        with pytest.raises(FetchBlocked):
            fetcher.fetch(URL)
        assert site.paths().count("/editais") == 1


class TestConditionalCache:
    def routes(self, *responses):
        return Site({"/robots.txt": httpx.Response(404), "/editais": list(responses)})

    def test_304_reuses_the_stored_text(self):
        site = self.routes(
            page("conteúdo", etag='"v1"', **{"last-modified": "Wed, 01 Oct 2026 10:00:00 GMT"}),
            httpx.Response(304),
        )
        fetcher, _ = make_fetcher(site, min_interval=0)
        first = fetcher.fetch(URL)
        second = fetcher.fetch(URL)
        sent = site.requests[-1].headers
        assert sent["if-none-match"] == '"v1"'
        assert sent["if-modified-since"] == "Wed, 01 Oct 2026 10:00:00 GMT"
        assert second.from_cache and not second.changed
        assert second.text == "conteúdo"
        assert second.document.pk == first.document.pk
        assert RawDocument.objects.count() == 1

    def test_changed_content_updates_the_document_and_the_hash(self):
        site = self.routes(page("v1", etag='"1"'), page("v2", etag='"2"'))
        fetcher, _ = make_fetcher(site, min_interval=0)
        first = fetcher.fetch(URL)
        second = fetcher.fetch(URL)
        assert second.changed and not second.from_cache
        assert second.document.content_hash != first.document.content_hash
        assert RawDocument.objects.get().text == "v2"

    def test_same_content_without_validators_is_reported_as_unchanged(self):
        site = self.routes(page("igual"), page("igual"))
        fetcher, _ = make_fetcher(site, min_interval=0)
        assert fetcher.fetch(URL).changed
        assert not fetcher.fetch(URL).changed

    def test_a_purged_document_is_downloaded_again_without_validators(self):
        site = self.routes(page("v1", etag='"1"'), page("v1", etag='"1"'))
        fetcher, _ = make_fetcher(site, min_interval=0)
        fetcher.fetch(URL)
        document = RawDocument.objects.get()
        document.purge_text()
        document.save()
        fetcher.fetch(URL)
        assert "if-none-match" not in site.requests[-1].headers
        assert RawDocument.objects.get().text == "v1"
