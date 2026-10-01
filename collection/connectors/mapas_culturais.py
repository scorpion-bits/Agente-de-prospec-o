"""Mapas Culturais — editais culturais (incl. PNAB) de várias instâncias (E09, ADR-032).

Conector `api` sobre `GET <instância>/api/opportunity/find` (API pública do software livre Mapas
Culturais), sempre pelo `PoliteFetcher`. **Uma `Source`, várias instâncias** em `Source.config`:

    {"instances": [{"slug": "nacional", "name": "Mapa da Cultura (MinC)",
                    "base_url": "https://mapa.cultura.gov.br", "scope": "national",
                    "uf": "", "municipality_name": ""}, ...],
     "keywords": ["jogo", "game", "audiovisual", ...],  # prefixos sem acento/maiúscula
     "exclude_patterns": ["..."],     # regex no título/resumo: descarta
     "page_size": 50, "max_pages_per_instance": 4,
     "include_closed": false}         # true = também as de prazo já vencido

O formato do JSON vem da documentação e de memória, **não** foi conferido contra uma instância real
(E01 pendente; o ambiente do Claude não alcança nenhuma): `normalize` é tolerante (datas como texto
`2026-10-01 23:59:59.000000`, ISO ou objeto `{"date", "timezone"}`; `type`, `terms` e
`ownerEntity` opcionais), a fixture é sintética, e resposta que não é lista é erro explícito. A
instância que falhar (bloqueio, HTTP, formato) não derruba as outras: os erros saem juntos no fim
(status `partial`). Cada oportunidade vira uma `Opportunity` com o link da própria instância; as
datas de inscrição só entram quando a instância as informa (ADR-004), e o status vem delas. Sem IA.
Chave de dedupe `mc:<host>|<id>`, estável entre execuções. Cada afirmação vira `Evidence(observed)`.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable
from datetime import date, datetime, time
from urllib.parse import urlencode, urlsplit
from zoneinfo import ZoneInfo

from django.utils import timezone

from collection.base import EvidenceDraft, OpportunityCandidate, RawItem, RunContext
from collection.fetcher import FetchError
from collection.registry import register
from core.models import Opportunity

SLUG = "mapas-culturais"
SELECT = "id,name,shortDescription,registrationFrom,registrationTo,singleUrl,type,terms,ownerEntity"
# Instâncias padrão: endereços de memória, **não conferidos** (P20); a fonte nasce desabilitada.
DEFAULT_INSTANCES = (
    {
        "slug": "nacional",
        "name": "Mapa da Cultura (MinC)",
        "base_url": "https://mapa.cultura.gov.br",
        "scope": "national",
    },
    {
        "slug": "sp",
        "name": "Mapa Cultural do Estado de São Paulo",
        "base_url": "https://mapacultural.sp.gov.br",
        "scope": "state",
        "uf": "SP",
    },
)
# Prefixos (sem acento, minúsculas) que ligam a oportunidade ao que a Scorpion Bits faz.
DEFAULT_KEYWORDS = (
    "jogo",
    "game",
    "audiovisual",
    "tecnologia",
    "cultura digital",
    "digital",
    "educa",
    "oficina",
    "software",
    "program",
    "inova",
    "robotica",
)
DEFAULT_EXCLUDES = ()
DEFAULT_PAGE_SIZE = 50
DEFAULT_MAX_PAGES = 4
LOCAL_TZ = ZoneInfo("America/Sao_Paulo")
CATEGORY_WORDS = {
    Opportunity.Category.GAMES: ("jogo", "game"),
    Opportunity.Category.EDUCATION: ("educa", "oficina", "curso", "formacao"),
    Opportunity.Category.CULTURE: ("cultur", "audiovisual", "pnab", "aldir"),
    Opportunity.Category.TECHNOLOGY: ("tecnologia", "digital", "software", "program"),
}
TAG_RE = re.compile(r"<[^>]+>")


class MapasCulturaisError(ValueError):
    pass


def fold(value) -> str:
    """Minúsculas sem acento e com espaços normalizados (comparação de palavras-chave)."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(TAG_RE.sub(" ", text).lower().split())


def clean_text(value) -> str:
    return " ".join(TAG_RE.sub(" ", str(value or "")).split())


def parse_moment(value) -> datetime | None:
    """Data/hora de inscrição como veio da instância; só texto/objeto inequívocos (senão `None`).
    Sem fuso informado vale o de Brasília; só o dia (sem hora) vira 00:00 local."""
    zone = LOCAL_TZ
    if isinstance(value, dict):
        try:
            zone = ZoneInfo(str(value.get("timezone") or LOCAL_TZ.key))
        except (ValueError, OSError):
            zone = LOCAL_TZ
        value = value.get("date")
    text = str(value or "").strip()
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            moment = datetime.combine(date.fromisoformat(text[:10]), time.min)
        except ValueError:
            return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=zone)
    return moment.astimezone(timezone.get_current_timezone())


def term_names(data: dict) -> list[str]:
    """Áreas/tags da oportunidade (`terms` é um dicionário de listas, ex. `{"area": [...]}`)."""
    terms = data.get("terms")
    if not isinstance(terms, dict):
        return []
    names = []
    for values in terms.values():
        for term in values if isinstance(values, list) else [values]:
            if isinstance(term, str) and term.strip():
                names.append(term.strip())
    return list(dict.fromkeys(names))


def type_name(data: dict) -> str:
    kind = data.get("type")
    if isinstance(kind, dict):
        return clean_text(kind.get("name"))
    return clean_text(kind) if isinstance(kind, str) else ""


def owner_name(data: dict) -> str:
    owner = data.get("ownerEntity")
    return clean_text(owner.get("name")) if isinstance(owner, dict) else ""


def categories_for(text: str) -> list[str]:
    folded = fold(text)
    found = [c for c, words in CATEGORY_WORDS.items() if any(w in folded for w in words)]
    return found or [Opportunity.Category.CULTURE]


def status_for(opens: datetime | None, deadline: datetime | None, now: datetime) -> str:
    if deadline is not None and deadline < now:
        return Opportunity.Status.CLOSED
    if opens is not None and opens > now:
        return Opportunity.Status.UPCOMING
    if opens is not None or deadline is not None:
        return Opportunity.Status.OPEN
    return Opportunity.Status.UNKNOWN


@register(slug=SLUG)
class MapasCulturaisConnector:
    kind = "api"

    def __init__(self, source):
        self.source = source
        self.slug = source.slug
        config = source.config or {}
        instances = config.get("instances") or DEFAULT_INSTANCES
        self.instances = []
        for instance in instances:
            base = str(instance.get("base_url") or "").rstrip("/")
            if not urlsplit(base).netloc:
                raise MapasCulturaisError(f"Instância sem `base_url` válida: {instance!r}.")
            self.instances.append({**instance, "base_url": base})
        self.keywords = tuple(fold(k) for k in config.get("keywords") or DEFAULT_KEYWORDS)
        patterns = config.get("exclude_patterns")
        patterns = DEFAULT_EXCLUDES if patterns is None else patterns
        try:
            self.excludes = [re.compile(p, re.I) for p in patterns]
        except re.error as exc:
            raise MapasCulturaisError(f"Regex inválida em `exclude_patterns`: {exc}") from exc
        self.page_size = int(config.get("page_size", DEFAULT_PAGE_SIZE))
        self.max_pages = int(config.get("max_pages_per_instance", DEFAULT_MAX_PAGES))
        self.include_closed = bool(config.get("include_closed", False))

    # --- requisições --------------------------------------------------------------------------
    def page_url(self, instance: dict, page: int, today: date) -> str:
        params = [
            ("@select", SELECT),
            ("@order", "registrationTo ASC"),
            ("@limit", self.page_size),
            ("@page", page),
        ]
        if not self.include_closed:
            params.append(("registrationTo", f"GTE({today.isoformat()})"))
        return f"{instance['base_url']}/api/opportunity/find?{urlencode(params)}"

    def fetch_instance(self, ctx: RunContext, instance: dict) -> Iterable[RawItem]:
        host = urlsplit(instance["base_url"]).netloc
        for page in range(1, self.max_pages + 1):
            url = self.page_url(instance, page, ctx.today)
            result = ctx.fetcher.fetch(url, source=ctx.source)
            try:
                rows = json.loads(result.text)
            except ValueError as exc:
                raise MapasCulturaisError(f"{host}: resposta não é JSON (página {page}).") from exc
            if not isinstance(rows, list):
                raise MapasCulturaisError(f"{host}: resposta inesperada (esperava uma lista).")
            for position, row in enumerate(rows, 1):
                if not isinstance(row, dict):
                    continue
                yield RawItem(
                    data={**row, "_instance": instance},
                    source_url=str(row.get("singleUrl") or url),
                    raw_document=result.document,
                    label=f"{instance.get('slug') or host} p{page} #{position}",
                )
            if len(rows) < self.page_size:
                return

    def fetch(self, ctx: RunContext) -> Iterable[RawItem]:
        errors = []
        for instance in self.instances:
            try:
                yield from self.fetch_instance(ctx, instance)
            except (FetchError, MapasCulturaisError) as exc:
                errors.append(f"{instance.get('slug') or instance['base_url']}: {exc}")
        if errors:
            raise MapasCulturaisError("; ".join(errors))

    # --- normalização -------------------------------------------------------------------------
    def relevant(self, text: str) -> bool:
        return any(k in fold(text) for k in self.keywords)

    def normalize(self, item: RawItem) -> OpportunityCandidate | None:
        data = item.data
        instance = data.get("_instance") or {}
        title = clean_text(data.get("name"))
        link = str(data.get("singleUrl") or "").strip()
        ident = data.get("id")
        host = urlsplit(str(instance.get("base_url") or link)).netloc
        if not title or not link or ident in (None, "") or not host:
            return None
        summary = clean_text(data.get("shortDescription"))
        areas = term_names(data)
        kind_label = type_name(data)
        text = " ".join([title, summary, *areas])
        if not self.relevant(text) or any(p.search(text) for p in self.excludes):
            return None

        opens = parse_moment(data.get("registrationFrom"))
        deadline = parse_moment(data.get("registrationTo"))
        status = status_for(opens, deadline, timezone.now())
        if status == Opportunity.Status.CLOSED and not self.include_closed:
            return None
        organizer = owner_name(data) or str(instance.get("name") or "")
        scope = str(instance.get("scope") or "")
        city = str(instance.get("municipality_name") or "")
        fields = {
            "kind": Opportunity.Kind.EDITAL,
            "official_url": link,
            "organizer_name": organizer[:200],
            "categories": categories_for(text),
            "status": status,
            "opens_at": opens,
            "deadline_at": deadline,
            "description": summary,
            "uf": str(instance.get("uf") or "")[:2].upper(),
            "municipality_name": city,
            **({"scope": scope} if scope in Opportunity.Scope.values else {}),
        }
        claims = {
            "title": title,
            "organizer_name": organizer,
            "instance": str(instance.get("name") or host),
            "opportunity_type": kind_label,
            "areas": areas,
            "opens_at": opens.isoformat() if opens else "",
            "deadline_at": deadline.isoformat() if deadline else "",
        }
        evidence = [
            EvidenceDraft(
                field=name,
                value=value,
                source_url=link,
                source_name=str(instance.get("name") or host),
                excerpt=summary[:300],
            )
            for name, value in claims.items()
            if value not in ("", None, [], {})
        ]
        return OpportunityCandidate(
            title=title[:300],
            fields=fields,
            canonical_key=f"mc:{host}|{ident}",
            evidence=evidence,
        )
