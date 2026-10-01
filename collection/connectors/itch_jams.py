"""itch.io — game jams futuras e em andamento como `Opportunity(kind=game_jam)` (E06, ADR-029).

Conector sobre a página pública de listagem (`/jams/upcoming`, `/jams/in-progress`), sempre pelo
`PoliteFetcher` (robots.txt, rate limit). O itch.io não tem API de jams. A estrutura do HTML vem de
memória/documentação de terceiros e **não** foi conferida contra a página real (E01 pendente: o
ambiente do Claude não alcança itch.io): o parser é tolerante a campos ausentes, a fixture em
`tests/fixtures/itch_jams/` é sintética e a falta de qualquer jam reconhecível vira erro explícito
(«Resposta inesperada»), nunca coleta silenciosamente vazia. Configure a `Source` (`itch-jams`):

    {"listing_urls": ["https://itch.io/jams/upcoming", "https://itch.io/jams/in-progress"],
     "max_listing_pages": 3,        # páginas (`?page=N`) por listagem
     "min_duration_hours": 48,      # jam com início e fim lidos e mais curta que isso é descartada
     "min_joined": 20,              # inscritos para valer sozinha...
     "keywords": ["brasil", ...]}   # ...ou palavra de interesse no título (minúsculas)

Datas: o itch.io publica `YYYY-MM-DD HH:MM:SS` (supomos UTC). Só lemos o que for inequívoco:
com duas datas na célula são início e fim; com uma, a listagem decide (em breve = início; em
andamento = fim);
nada além disso é chutado (ADR-004). Sem IA: tudo é regra. Cada afirmação vira `Evidence(observed)`.
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit

from django.utils import timezone

from collection.base import EvidenceDraft, OpportunityCandidate, RawItem, RunContext
from collection.registry import register
from core.models import Opportunity

SLUG = "itch-jams"
BASE_URL = "https://itch.io"
DEFAULT_LISTINGS = (f"{BASE_URL}/jams/upcoming", f"{BASE_URL}/jams/in-progress")
LISTING_STATUS = {"upcoming": Opportunity.Status.UPCOMING, "in-progress": Opportunity.Status.OPEN}
DEFAULT_MAX_LISTING_PAGES = 3
DEFAULT_MIN_DURATION_HOURS = 48
DEFAULT_MIN_JOINED = 20
# Palavras (minúsculas) que fazem uma jam pequena valer a pena: Brasil, educação, Godot.
DEFAULT_KEYWORDS = (
    "brasil",
    "brazil",
    "brasileira",
    "educação",
    "educacao",
    "educational",
    "education",
    "escola",
    "school",
    "godot",
    "pt-br",
)

CELL_START = re.compile(r'<(?:div|li|article)\b[^>]*class="[^"]*\bjam_cell\b[^"]*"', re.I)
JAM_LINK = re.compile(
    r'<a\b[^>]*href="((?:https?://itch\.io)?/jam/[^"?#/]+)[^"]*"[^>]*>(.*?)</a>', re.I | re.S
)
DATE_ATTR = re.compile(r'title="(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"')
JOINED = re.compile(r"([\d][\d.,]*)\s*(?:joined|participants?|inscritos?)", re.I)
HOST = re.compile(r"hosted by\s*(?:<[^>]+>\s*)*([^<]+)", re.I)
TAG_RE = re.compile(r"<[^>]+>")


class ItchError(ValueError):
    pass


def text_of(fragment: str) -> str:
    return " ".join(html.unescape(TAG_RE.sub(" ", fragment or "")).split())


def clean_jam_url(url: str) -> str:
    """`https://itch.io/jam/<slug>` sem querystring; vazio se não for página de jam do itch.io."""
    parts = urlsplit(urljoin(BASE_URL, str(url or "").strip()))
    pieces = [p for p in parts.path.split("/") if p]
    if parts.hostname != "itch.io" or len(pieces) != 2 or pieces[0] != "jam":
        return ""
    return f"{BASE_URL}/jam/{pieces[1]}"


def parse_stamp(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    except ValueError:
        return None


def parse_joined(value: str) -> int | None:
    digits = re.sub(r"[.,\s]", "", value or "")
    return int(digits) if digits.isdigit() else None


def parse_listing(page_html: str, *, base_url: str = BASE_URL) -> list[dict]:
    """Células de jam da listagem → dicts (`url`, `title`, `host`, `dates`, `joined`)."""
    starts = [m.start() for m in CELL_START.finditer(page_html)]
    jams = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(page_html)
        cell = page_html[start:end]
        links = [
            (clean_jam_url(urljoin(base_url, m.group(1))), text_of(m.group(2)))
            for m in JAM_LINK.finditer(cell)
        ]
        links = [(url, title) for url, title in links if url]
        if not links:
            continue
        url = links[0][0]
        title = next((t for u, t in links if u == url and t), "")
        host = HOST.search(cell)
        joined = JOINED.search(text_of(cell))
        jams.append(
            {
                "url": url,
                "title": title,
                "host": text_of(host.group(1)) if host else "",
                "dates": DATE_ATTR.findall(cell),
                "joined": parse_joined(joined.group(1)) if joined else None,
            }
        )
    return jams


def categories_for(title: str) -> list[str]:
    result = [Opportunity.Category.GAMES]
    if any(word in title.lower() for word in ("educa", "escola", "school")):
        result.append(Opportunity.Category.EDUCATION)
    return result


@register(slug=SLUG)
class ItchJamsConnector:
    kind = "html_watch"

    def __init__(self, source, *, now: Callable[[], datetime] = timezone.now):
        self.source = source
        self.slug = source.slug
        self.config = source.config or {}
        self.listings = tuple(self.config.get("listing_urls") or DEFAULT_LISTINGS)
        self.max_pages = int(self.config.get("max_listing_pages", DEFAULT_MAX_LISTING_PAGES))
        self.min_hours = float(self.config.get("min_duration_hours", DEFAULT_MIN_DURATION_HOURS))
        self.min_joined = int(self.config.get("min_joined", DEFAULT_MIN_JOINED))
        self.keywords = tuple(k.lower() for k in self.config.get("keywords") or DEFAULT_KEYWORDS)
        self._now = now

    @staticmethod
    def listing_kind(url: str) -> str:
        path = urlsplit(url).path.rstrip("/")
        return "in-progress" if path.endswith("in-progress") else "upcoming"

    def fetch(self, ctx: RunContext) -> Iterable[RawItem]:
        seen: set[str] = set()
        for listing in self.listings:
            for number in range(1, self.max_pages + 1):
                url = listing if number == 1 else f"{listing}?page={number}"
                result = ctx.fetcher.fetch(url, source=ctx.source)
                cells = parse_listing(result.text)
                if not cells and number == 1 and result.text.strip():
                    raise ItchError(f"Resposta inesperada da listagem ({urlsplit(listing).path}).")
                fresh = 0
                for position, cell in enumerate(cells, 1):
                    if cell["url"] in seen:
                        continue
                    seen.add(cell["url"])
                    fresh += 1
                    yield RawItem(
                        data={**cell, "listing": self.listing_kind(listing)},
                        source_url=cell["url"],
                        raw_document=result.document,
                        label=f"{self.listing_kind(listing)} p{number} item {position}",
                    )
                if not fresh:  # página vazia ou repetida: a listagem acabou
                    break

    def read_dates(self, data: dict) -> tuple[datetime | None, datetime | None]:
        stamps = [parse_stamp(s) for s in data.get("dates") or []]
        if len(stamps) == 2 and all(stamps):
            start, end = stamps
            return (start, end) if start <= end else (None, None)
        if len(stamps) == 1 and stamps[0]:
            return (stamps[0], None) if data.get("listing") == "upcoming" else (None, stamps[0])
        return None, None

    def accepts(self, title: str, joined: int | None, start, end) -> bool:
        """Filtro mínimo (E06): não curtíssima **e** (inscritos suficientes ou palavra-chave)."""
        if start and end and (end - start).total_seconds() < self.min_hours * 3600:
            return False
        if end and end < self._now():
            return False  # já terminou
        lowered = title.lower()
        return (joined or 0) >= self.min_joined or any(k in lowered for k in self.keywords)

    def normalize(self, item: RawItem) -> OpportunityCandidate | None:
        data = item.data
        title = " ".join(str(data.get("title", "")).split())
        url = clean_jam_url(data.get("url", ""))
        if not title or not url:
            return None
        start, end = self.read_dates(data)
        joined = data.get("joined")
        if not self.accepts(title, joined, start, end):
            return None

        host = " ".join(str(data.get("host", "")).split())
        status = LISTING_STATUS.get(data.get("listing"), Opportunity.Status.UNKNOWN)
        fields = {
            "kind": Opportunity.Kind.GAME_JAM,
            "official_url": url,
            "organizer_name": host[:200],
            "modality": Opportunity.Modality.ONLINE,
            "scope": Opportunity.Scope.INTERNATIONAL,
            "categories": categories_for(title),
            "status": status,
            "opens_at": start,
            "deadline_at": end,
            "description": f"Game jam no itch.io; {joined} inscritos na coleta." if joined else "",
        }
        claims = {
            "title": title,
            "organizer_name": host,
            "modality": fields["modality"],
            "opens_at": start.isoformat() if start else "",
            "deadline_at": end.isoformat() if end else "",
            "participants": joined,
            "status": data.get("listing", ""),
        }
        evidence = [
            EvidenceDraft(field=name, value=value, source_url=url, source_name="itch.io")
            for name, value in claims.items()
            if value not in ("", None)
        ]
        return OpportunityCandidate(title=title[:300], fields=fields, evidence=evidence)
