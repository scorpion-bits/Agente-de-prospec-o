"""Devpost — hackathons abertos e futuros como `Opportunity(kind=hackathon)` (E05, ADR-028).

Conector `api`: lê o JSON público que o próprio site usa (`/api/hackathons`, sem autenticação),
sempre pelo `PoliteFetcher`. Configure a `Source` (`devpost`) se quiser mudar o padrão:

    {"max_api_pages": 5,                       # páginas da listagem por execução
     "statuses": ["open", "upcoming"],
     "keywords": ["gaming", "education", ...], # temas/título que interessam (minúsculas)
     "allow_in_person": false}                 # presencial só no Brasil; online sempre vale

O formato do JSON vem da documentação de terceiros e de memória, **não** foi conferido contra a
resposta real (E01 pendente): `normalize` é tolerante a campos ausentes e a fixture em
`tests/fixtures/devpost/` marca o que é suposto. A API só dá o período como texto ("Sep 01 - Oct 30,
2026"): datas que não forem lidas sem ambiguidade ficam em branco, nunca chutadas (ADR-004).

Sem IA: tudo é mapeamento e regra. Cada afirmação vira `Evidence(observed)` com a URL do hackathon.
"""

from __future__ import annotations

import html
import json
import re
from collections.abc import Iterable
from datetime import date, datetime, time
from urllib.parse import urlencode, urlsplit

from django.utils import timezone

from collection.base import EvidenceDraft, OpportunityCandidate, RawItem, RunContext
from collection.registry import register
from core.models import Opportunity

SLUG = "devpost"
LISTING_URL = "https://devpost.com/api/hackathons"
DEFAULT_STATUSES = ("open", "upcoming")
DEFAULT_MAX_API_PAGES = 5
# Temas do Devpost (minúsculas) que interessam: jogos, educação, impacto social e temas abertos.
DEFAULT_KEYWORDS = (
    "gaming",
    "game",
    "education",
    "social good",
    "open ended",
    "community",
    "beginner friendly",
)
BRAZIL_MARKERS = ("brazil", "brasil")
MONTHS = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1
    )
}
STATUS_MAP = {
    "open": Opportunity.Status.OPEN,
    "upcoming": Opportunity.Status.UPCOMING,
    "ended": Opportunity.Status.CLOSED,
}
TAG_RE = re.compile(r"<[^>]+>")
DATE_PART = re.compile(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2})(?:,\s*(\d{4}))?")
TRACKING_PARAMS = {"ref_feature", "ref_medium", "utm_source", "utm_medium", "utm_campaign"}


class DevpostError(ValueError):
    pass


def strip_html(value) -> str:
    return " ".join(html.unescape(TAG_RE.sub("", str(value or ""))).split())


def parse_period(text: str) -> tuple[date | None, date | None]:
    """ "Sep 01 - Oct 30, 2026" → (início, fim). O ano é o da data final; só uma data → só o fim.

    Qualquer formato que não leia limpo devolve `(None, None)`: sem data inventada.
    """
    parts = [p.strip() for p in re.split(r"\s[-–—]\s", strip_html(text)) if p.strip()]
    if not 1 <= len(parts) <= 2:
        return None, None
    parsed = []
    for part in parts:
        match = DATE_PART.fullmatch(part)
        month = MONTHS.get(match.group(1).lower()) if match else None
        if not match or month is None:
            return None, None
        year = int(match.group(3)) if match.group(3) else None
        parsed.append((month, int(match.group(2)), year))
    end_month, end_day, end_year = parsed[-1]
    if end_year is None:
        return None, None
    try:
        end = date(end_year, end_month, end_day)
        if len(parsed) == 1:
            return None, end
        start_month, start_day, start_year = parsed[0]
        start = date(
            start_year or (end_year if start_month <= end_month else end_year - 1),
            start_month,
            start_day,
        )
    except ValueError:
        return None, None
    return (start, end) if start <= end else (None, None)


def local_datetime(day: date | None, *, end_of_day: bool) -> datetime | None:
    """Só o dia é conhecido: abertura 00:00, prazo 23:59, fuso local (como em `Opportunity`)."""
    if day is None:
        return None
    return timezone.make_aware(datetime.combine(day, time(23, 59) if end_of_day else time.min))


def clean_url(url: str) -> str:
    """URL do hackathon sem querystring de rastreio e com esquema https."""
    parts = urlsplit(str(url or "").strip())
    if not parts.netloc or not parts.netloc.endswith("devpost.com"):
        return ""
    query = "&".join(
        piece
        for piece in parts.query.split("&")
        if piece and piece.split("=")[0] not in TRACKING_PARAMS
    )
    return f"https://{parts.netloc}{parts.path}" + (f"?{query}" if query else "")


def theme_names(data: dict) -> list[str]:
    names = []
    for theme in data.get("themes") or []:
        name = theme.get("name") if isinstance(theme, dict) else theme
        if name and str(name).strip():
            names.append(str(name).strip())
    return names


def location_text(data: dict) -> str:
    place = data.get("displayed_location")
    if isinstance(place, dict):
        return str(place.get("location") or "").strip()
    return str(place or "").strip()


def is_online(data: dict) -> bool:
    place = data.get("displayed_location")
    icon = place.get("icon", "") if isinstance(place, dict) else ""
    return icon == "globe" or location_text(data).lower() in {"online", "worldwide"}


def is_brazil(data: dict) -> bool:
    return any(marker in location_text(data).lower() for marker in BRAZIL_MARKERS)


def relevant_by_theme(data: dict, keywords) -> bool:
    haystack = [name.lower() for name in theme_names(data)] + [str(data.get("title", "")).lower()]
    return any(keyword in text for keyword in keywords for text in haystack)


def categories_for(themes: list[str]) -> list[str]:
    lowered = " ".join(themes).lower()
    result = []
    if "gam" in lowered:
        result.append(Opportunity.Category.GAMES)
    if "education" in lowered:
        result.append(Opportunity.Category.EDUCATION)
    return result or [Opportunity.Category.TECHNOLOGY]


@register(slug=SLUG)
class DevpostConnector:
    kind = "api"

    def __init__(self, source):
        self.source = source
        self.slug = source.slug
        self.config = source.config or {}
        self.statuses = tuple(self.config.get("statuses") or DEFAULT_STATUSES)
        self.max_pages = int(self.config.get("max_api_pages", DEFAULT_MAX_API_PAGES))
        self.keywords = tuple(k.lower() for k in self.config.get("keywords") or DEFAULT_KEYWORDS)
        self.allow_in_person = bool(self.config.get("allow_in_person", False))
        self.listing_url = self.config.get("url") or LISTING_URL

    def page_url(self, page: int) -> str:
        query = [("status[]", s) for s in self.statuses] + [("page", page)]
        return f"{self.listing_url}?{urlencode(query)}"

    def fetch(self, ctx: RunContext) -> Iterable[RawItem]:
        seen_urls: set[str] = set()
        for page in range(1, self.max_pages + 1):
            url = self.page_url(page)
            result = ctx.fetcher.fetch(url, source=ctx.source)
            try:
                payload = json.loads(result.text)
                hackathons = payload["hackathons"]
            except (ValueError, KeyError, TypeError) as exc:
                raise DevpostError(f"Resposta inesperada da listagem (página {page}).") from exc
            if not isinstance(hackathons, list) or not hackathons:
                return
            fresh = 0
            for position, data in enumerate(hackathons, 1):
                if not isinstance(data, dict):
                    continue
                link = clean_url(data.get("url", ""))
                if link in seen_urls:
                    continue
                seen_urls.add(link)
                fresh += 1
                yield RawItem(
                    data=data,
                    source_url=link or url,
                    raw_document=result.document,
                    label=f"página {page}, item {position}",
                )
            if not fresh:  # página repetida: a listagem acabou
                return

    def accepts(self, data: dict) -> bool:
        """Filtro de relevância: tema/título de interesse **e** (online ou Brasil)."""
        if data.get("invite_only"):
            return False
        if not relevant_by_theme(data, self.keywords):
            return False
        return is_online(data) or is_brazil(data) or self.allow_in_person

    def normalize(self, item: RawItem) -> OpportunityCandidate | None:
        data = item.data
        title = " ".join(str(data.get("title", "")).split())
        url = clean_url(data.get("url", ""))
        if not title or not url or not self.accepts(data):
            return None

        themes = theme_names(data)
        start, end = parse_period(data.get("submission_period_dates", ""))
        online = is_online(data)
        prize = strip_html(data.get("prize_amount", ""))
        if prize in {"0", "$0"}:
            prize = ""
        organizer = " ".join(str(data.get("organization_name", "")).split())
        status = STATUS_MAP.get(str(data.get("open_state", "")), Opportunity.Status.UNKNOWN)

        fields = {
            "kind": Opportunity.Kind.HACKATHON,
            "official_url": url,
            "organizer_name": organizer[:200],
            "modality": Opportunity.Modality.ONLINE if online else Opportunity.Modality.IN_PERSON,
            "scope": Opportunity.Scope.INTERNATIONAL if online else Opportunity.Scope.NATIONAL,
            "categories": categories_for(themes),
            "status": status,
            "opens_at": local_datetime(start, end_of_day=False),
            "deadline_at": local_datetime(end, end_of_day=True),
            "prize_text": prize[:300],
            "benefits": [Opportunity.Benefit.PRIZE] if prize else [],
            "description": (f"Temas: {', '.join(themes)}." if themes else ""),
        }
        claims = {
            "title": title,
            "organizer_name": organizer,
            "modality": fields["modality"],
            "location": location_text(data),
            "themes": themes,
            "submission_period": strip_html(data.get("submission_period_dates", "")),
            "opens_at": start.isoformat() if start else "",
            "deadline_at": end.isoformat() if end else "",
            "prize_text": prize,
            "status": data.get("open_state", ""),
        }
        evidence = [
            EvidenceDraft(field=name, value=value, source_url=url, source_name="Devpost")
            for name, value in claims.items()
            if value not in ("", None, [])
        ]
        return OpportunityCandidate(title=title[:300], fields=fields, evidence=evidence)
