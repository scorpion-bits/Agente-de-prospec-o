"""PoliteFetcher: baixa páginas respeitando robots.txt, rate limit e cache condicional.

Regras (docs/architecture/connectors.md e legal-and-compliance.md):
1. User-Agent identificado, com o contato do `.env`.
2. robots.txt respeitado (cache de 24 h por origem). `Disallow` → não baixa. robots.txt com 401/403
   ou fora do ar → fallback conservador: **nada** é baixado daquele site.
3. Rate limit por domínio (padrão: 1 requisição a cada 5 s).
4. Cache condicional: `ETag`/`If-Modified-Since` ficam em `RawDocument`; 304 reaproveita o texto.
5. Retries com backoff só para 429/5xx/timeouts (máx. 3). Outros 4xx: não insiste.
6. Limites: tamanho do download e número de páginas por execução. Só texto (sem binários).
7. Não contorna login, captcha, paywall ou bloqueio: 401/403 levanta `FetchBlocked`.
8. Sem navegador headless.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from django.conf import settings
from django.utils import timezone

from collection.models import RawDocument

DEFAULT_MIN_INTERVAL = 5.0
DEFAULT_MAX_BYTES = 20 * 1024 * 1024
ROBOTS_TTL = 24 * 3600
ROBOTS_MAX_BYTES = 512 * 1024
MAX_REDIRECTS = 5
MAX_RETRY_AFTER = 60.0
ROBOTS_PRODUCT_TOKEN = "RadarScorpionBits"
TEXT_TYPES = {
    "application/json",
    "application/xml",
    "application/xhtml+xml",
    "application/x-ndjson",
    "application/javascript",
    "application/csv",
}


class FetchError(Exception):
    """Falha ao baixar uma página."""


class RobotsDisallowed(FetchError):
    """O robots.txt (ou a falta dele) não permite baixar a URL."""


class FetchBlocked(FetchError):
    """O site recusou o acesso (401/403): não insistimos nem contornamos."""


class FetchHTTPError(FetchError):
    def __init__(self, url, status_code):
        super().__init__(f"HTTP {status_code} em {urlsplit(url).netloc}")
        self.status_code = status_code


class FetchTooLarge(FetchError):
    pass


class UnsupportedContent(FetchError):
    """Conteúdo que não é texto: binários não são armazenados (ADR-010)."""


class PageBudgetExceeded(FetchError):
    """O limite de páginas por execução foi atingido."""


@dataclass
class FetchResult:
    url: str
    status_code: int
    text: str
    content_type: str
    document: RawDocument | None
    from_cache: bool = False  # 304: o texto veio do `RawDocument` guardado
    changed: bool = True  # o conteúdo difere do que estava guardado


def is_text_content_type(content_type: str) -> bool:
    main = content_type.split(";")[0].strip().lower()
    return (
        not main
        or main.startswith("text/")
        or main in TEXT_TYPES
        or main.endswith(("+json", "+xml"))
    )


class PoliteFetcher:
    def __init__(
        self,
        *,
        user_agent: str | None = None,
        client: httpx.Client | None = None,
        min_interval: float = DEFAULT_MIN_INTERVAL,
        max_retries: int = 3,
        max_bytes: int = DEFAULT_MAX_BYTES,
        max_requests: int | None = None,
        timeout: float = 20.0,
        backoff_base: float = 2.0,
        sleep=time.sleep,
        monotonic=time.monotonic,
    ):
        self.user_agent = user_agent or settings.USER_AGENT
        self.client = client or httpx.Client(timeout=timeout, follow_redirects=False)
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.max_bytes = max_bytes
        self.max_requests = max_requests
        self.backoff_base = backoff_base
        self._sleep = sleep
        self._monotonic = monotonic
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, tuple[float, RobotFileParser | None]] = {}
        self.requests = 0

    def close(self):
        self.client.close()

    # --- robots.txt ----------------------------------------------------------------------
    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        cached = self._robots.get(origin)
        if cached is None or self._monotonic() - cached[0] > ROBOTS_TTL:
            cached = (self._monotonic(), self._load_robots(origin))
            self._robots[origin] = cached
        parser = cached[1]
        return parser is not None and parser.can_fetch(ROBOTS_PRODUCT_TOKEN, url)

    def _load_robots(self, origin: str) -> RobotFileParser | None:
        """Parser do robots.txt; `None` = bloquear tudo (fallback conservador)."""
        parser = RobotFileParser()
        try:
            response = self._send(f"{origin}/robots.txt", {}, max_bytes=ROBOTS_MAX_BYTES)
        except FetchError:
            return None  # fora do ar ou grande demais: na dúvida, não baixa
        status = response.status_code
        if status in (401, 403):
            return None
        if 400 <= status < 500 or status in (301, 302, 303, 307, 308):
            parser.parse([])  # sem robots.txt: sem restrições (RFC 9309)
            return parser
        if status != 200:
            return None
        parser.parse(response.text.splitlines())
        return parser

    # --- HTTP ----------------------------------------------------------------------------
    def _wait_turn(self, domain: str):
        last = self._last_request.get(domain)
        if last is not None:
            wait = self.min_interval - (self._monotonic() - last)
            if wait > 0:
                self._sleep(wait)

    def _send(self, url: str, headers: dict, *, max_bytes: int) -> _Response:
        """Uma requisição com rate limit, retries e limite de tamanho (sem redirecionar)."""
        domain = urlsplit(url).netloc
        headers = {"User-Agent": self.user_agent, "Accept": "*/*", **headers}
        for attempt in range(self.max_retries + 1):
            self._wait_turn(domain)
            retry_after = None
            try:
                with self.client.stream("GET", url, headers=headers) as response:
                    self._last_request[domain] = self._monotonic()
                    retryable = response.status_code == 429 or response.status_code >= 500
                    if retryable and attempt < self.max_retries:
                        retry_after = _retry_after(response)
                    else:
                        return self._read(response, max_bytes)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                self._last_request[domain] = self._monotonic()
                if attempt == self.max_retries:
                    raise FetchError(f"Falha de rede em {domain}: {type(exc).__name__}") from exc
            self._sleep(retry_after or self.backoff_base ** (attempt + 1))
        raise AssertionError("inalcançável")  # pragma: no cover

    def _read(self, response: httpx.Response, max_bytes: int) -> _Response:
        declared = response.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > max_bytes:
            raise FetchTooLarge(f"Conteúdo declarado com {declared} bytes (limite {max_bytes}).")
        body = bytearray()
        for chunk in response.iter_bytes():
            body.extend(chunk)
            if len(body) > max_bytes:
                raise FetchTooLarge(f"Conteúdo passou do limite de {max_bytes} bytes.")
        return _Response(
            status_code=response.status_code,
            headers=response.headers,
            body=bytes(body),
            encoding=response.encoding or "utf-8",
        )

    # --- API pública ---------------------------------------------------------------------
    def fetch(self, url: str, *, source=None, max_bytes: int | None = None) -> FetchResult:
        """Baixa `url` (texto) e guarda em `RawDocument`. Levanta `FetchError` e subclasses."""
        if self.max_requests is not None and self.requests >= self.max_requests:
            raise PageBudgetExceeded(f"Limite de {self.max_requests} páginas por execução.")
        self.requests += 1
        limit = max_bytes or self.max_bytes
        document = RawDocument.objects.filter(url=url).first()

        for _hop in range(MAX_REDIRECTS + 1):
            if not self.allowed(url):
                raise RobotsDisallowed(f"robots.txt não permite {urlsplit(url).netloc}.")
            headers = {}
            if document is not None and document.has_text and url == document.url:
                if document.etag:
                    headers["If-None-Match"] = document.etag
                if document.last_modified:
                    headers["If-Modified-Since"] = document.last_modified
            response = self._send(url, headers, max_bytes=limit)
            status = response.status_code
            if status in (301, 302, 303, 307, 308) and response.headers.get("location"):
                url = urljoin(url, response.headers["location"])
                document = RawDocument.objects.filter(url=url).first()
                continue
            break
        else:
            raise FetchError("Redirecionamentos demais.")

        if status == 304 and document is not None and document.has_text:
            document.fetched_at = timezone.now()
            document.save(update_fields=["fetched_at"])
            return FetchResult(
                url, 200, document.text, document.content_type, document, True, changed=False
            )
        if status in (401, 403):
            raise FetchBlocked(f"{urlsplit(url).netloc} recusou o acesso (HTTP {status}).")
        if status != 200:
            raise FetchHTTPError(url, status)
        return self._store(url, response, source, document)

    def _store(self, url, response, source, document) -> FetchResult:
        content_type = response.headers.get("content-type", "")
        if not is_text_content_type(content_type):
            raise UnsupportedContent(f"Tipo {content_type.split(';')[0]!r} não é texto.")
        text = response.body.decode(response.encoding, errors="replace")
        digest = hashlib.sha256(response.body).hexdigest()
        changed = document is None or document.content_hash != digest or not document.has_text
        document = document or RawDocument(url=url)
        document.source = source or document.source
        document.status_code = 200
        document.content_type = content_type[:120]
        document.etag = response.headers.get("etag", "")[:255]
        document.last_modified = response.headers.get("last-modified", "")[:120]
        document.content_hash = digest
        document.fetched_at = timezone.now()
        document.expires_at = document.fetched_at + timedelta(
            days=settings.RAW_DOCUMENT_RETENTION_DAYS
        )
        document.set_text(text)
        document.save()
        return FetchResult(url, 200, text, content_type, document, False, changed)


@dataclass
class _Response:
    status_code: int
    headers: httpx.Headers
    body: bytes
    encoding: str

    @property
    def text(self):
        return self.body.decode(self.encoding, errors="replace")


def _retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after", "")
    if value.isdigit():
        return min(float(value), MAX_RETRY_AFTER)
    return None
