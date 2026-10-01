"""Querido Diário — ocorrências em diários oficiais municipais como candidatas (E08, ADR-031).

Conector `api` sobre a API pública (`/gazettes`, Open Knowledge Brasil), sempre pelo
`PoliteFetcher`.
Cada consulta (termos combinados) é feita para **todos** os municípios de uma vez (`territory_ids`
repetido); cada trecho devolvido vira uma `Opportunity` candidata (`status=unknown`, sem
`extraction_version`: a E11 lê o PDF). O formato do JSON vem da documentação e de memória e **não**
foi conferido contra a resposta real (E01 pendente: o ambiente do Claude não alcança a API):
`normalize` é tolerante a campos ausentes, a fixture é sintética e resposta sem `gazettes` é erro
explícito, nunca coleta vazia silenciosa. Configure a `Source` (`querido-diario`):

    {"municipalities": [{"ibge_code": "3503208", "name": "Araraquara"}, ...],  # códigos IBGE
     "queries": [{"name": "oficina-jogos", "query": "oficina + (jogos | games)"}, ...],
     "exclude_patterns": ["jogos abertos", "..."],  # regex no trecho: descarta falso positivo
     "initial_days": 60,       # janela da 1ª execução (sem execução anterior bem-sucedida)
     "overlap_days": 1,        # recua a janela incremental para não perder diário publicado tarde
     "coverage_days": 30,      # janela da sondagem de cobertura por município
     "page_size": 50, "max_pages_per_query": 3, "excerpt_size": 500, "excerpts_per_gazette": 3}

Janela incremental: `published_since` = dia da última execução **não simulada e concluída** da fonte
menos `overlap_days` (ou `initial_days` na primeira); repetir o mesmo trecho é inofensivo porque a
chave é `qd:<ibge>|<data>|<hash do trecho>` (município, data, trecho). Município sem diário na
janela de cobertura é registrado no erro da execução («use `html_watch`»), sem derrubar os demais.
Tipo da candidata por regra no trecho (chamamento/credenciamento → `call_for_partners`; licitação →
`procurement`; senão `edital`). Sem IA. Cada afirmação vira `Evidence(observed)` com o PDF.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from collections.abc import Iterable
from datetime import date, datetime, time, timedelta
from urllib.parse import urlencode

from django.utils import timezone

from collection.base import EvidenceDraft, OpportunityCandidate, RawItem, RunContext
from collection.models import CollectionRun
from collection.registry import register
from core.models import Opportunity

SLUG = "querido-diario"
API_URL = "https://api.queridodiario.ok.org.br/gazettes"
DEFAULT_MUNICIPALITIES = (
    {"ibge_code": "3503208", "name": "Araraquara"},
    {"ibge_code": "3548906", "name": "São Carlos"},
    {"ibge_code": "3543402", "name": "Ribeirão Preto"},
    {"ibge_code": "3506003", "name": "Bauru"},
    {"ibge_code": "3529302", "name": "Matão"},
    {"ibge_code": "3501707", "name": "Américo Brasiliense"},
)
# Sintaxe da API (simple query string): `+` = E, `|` = OU, aspas = frase exata, `-` = exclui.
DEFAULT_QUERIES = (
    {"name": "oficina-jogos", "query": 'oficina + (jogos | games | "jogos digitais")'},
    {"name": "curso-programacao", "query": 'curso + (programação | "desenvolvimento de jogos")'},
    {"name": "chamamento-cultura", "query": '"chamamento público" + cultura'},
    {"name": "credenciamento-oficineiros", "query": "credenciamento + oficineiros"},
    {"name": "edital-pnab", "query": 'edital + (PNAB | "Aldir Blanc")'},
    {"name": "game-jam-hackathon", "query": '"game jam" | hackathon'},
    {"name": "gamificacao", "query": "gamificação"},
    {"name": "robotica-escola", "query": "robótica + escola"},
)
# Falsos positivos conhecidos: «jogos» no sentido esportivo (regex, sem diferenciar maiúsculas).
DEFAULT_EXCLUDES = (
    r"jogos\s+(abertos|regionais|escolares|olímpicos|olimpicos|paraolímpicos|paralímpicos)",
    r"jogos\s+(de\s+)?(azar|de\s+loteria)",
    r"\bcampeonato\b",
    r"\bfutebol\b",
)
DEFAULT_INITIAL_DAYS = 60
DEFAULT_OVERLAP_DAYS = 1
DEFAULT_COVERAGE_DAYS = 30
DEFAULT_PAGE_SIZE = 50
DEFAULT_MAX_PAGES = 3
DEFAULT_EXCERPT_SIZE = 500
DEFAULT_EXCERPTS = 3
TAG_RE = re.compile(r"<[^>]+>")
CALL_RE = re.compile(r"chamamento|credenciamento|chamada\s+p[úu]blica|oficineiro", re.I)
PROCUREMENT_RE = re.compile(r"licita[çc][ãa]o|preg[ãa]o|dispensa|tomada\s+de\s+pre[çc]os", re.I)
CATEGORY_WORDS = {
    Opportunity.Category.GAMES: ("jogo", "game", "gamifica"),
    Opportunity.Category.EDUCATION: ("curso", "oficina", "escola", "educa", "rob[óo]tica"),
    Opportunity.Category.CULTURE: ("cultur", "pnab", "aldir blanc"),
    Opportunity.Category.TECHNOLOGY: ("programa[çc][ãa]o", "tecnologia", "software", "hackathon"),
}


class QueridoDiarioError(ValueError):
    pass


def clean_text(value) -> str:
    """Trecho sem marcação (a API destaca termos com `<em>`) e com espaços normalizados."""
    return " ".join(html.unescape(TAG_RE.sub(" ", str(value or ""))).split())


def parse_day(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def excerpt_hash(text: str) -> str:
    """Hash estável do trecho (sem maiúsculas/espaços) para a chave de dedupe."""
    return hashlib.sha1(clean_text(text).lower().encode("utf-8")).hexdigest()[:12]


def canonical_key(ibge_code: str, day: date, excerpt: str) -> str:
    return f"qd:{ibge_code}|{day.isoformat()}|{excerpt_hash(excerpt)}"


def kind_for(excerpt: str) -> str:
    if CALL_RE.search(excerpt):
        return Opportunity.Kind.CALL_FOR_PARTNERS
    if PROCUREMENT_RE.search(excerpt):
        return Opportunity.Kind.PROCUREMENT
    return Opportunity.Kind.EDITAL


def categories_for(excerpt: str) -> list[str]:
    lowered = excerpt.lower()
    return [
        category
        for category, words in CATEGORY_WORDS.items()
        if any(re.search(word, lowered) for word in words)
    ]


@register(slug=SLUG)
class QueridoDiarioConnector:
    kind = "api"

    def __init__(self, source):
        self.source = source
        self.slug = source.slug
        config = source.config or {}
        self.api_url = str(config.get("api_url") or API_URL)
        municipalities = config.get("municipalities") or DEFAULT_MUNICIPALITIES
        self.municipalities = {str(m["ibge_code"]): str(m.get("name", "")) for m in municipalities}
        self.queries = tuple(config.get("queries") or DEFAULT_QUERIES)
        patterns = config.get("exclude_patterns")
        patterns = DEFAULT_EXCLUDES if patterns is None else patterns
        try:
            self.excludes = [re.compile(p, re.I) for p in patterns]
        except re.error as exc:
            raise QueridoDiarioError(f"Regex inválida em `exclude_patterns`: {exc}") from exc
        self.initial_days = int(config.get("initial_days", DEFAULT_INITIAL_DAYS))
        self.overlap_days = int(config.get("overlap_days", DEFAULT_OVERLAP_DAYS))
        self.coverage_days = int(config.get("coverage_days", DEFAULT_COVERAGE_DAYS))
        self.page_size = int(config.get("page_size", DEFAULT_PAGE_SIZE))
        self.max_pages = int(config.get("max_pages_per_query", DEFAULT_MAX_PAGES))
        self.excerpt_size = int(config.get("excerpt_size", DEFAULT_EXCERPT_SIZE))
        self.excerpts = int(config.get("excerpts_per_gazette", DEFAULT_EXCERPTS))

    # --- janela incremental -------------------------------------------------------------------
    def window_start(self, today: date) -> date:
        """Dia da última execução concluída (não simulada) menos a sobreposição; senão a janela
        inicial. Execução parcial/com erro não avança a janela: o que faltou é tentado de novo."""
        last = (
            CollectionRun.objects.filter(
                source=self.source, dry_run=False, status=CollectionRun.Status.OK
            )
            .order_by("-started_at")
            .first()
        )
        if last is None:
            return today - timedelta(days=self.initial_days)
        started = timezone.localtime(last.started_at).date()
        return min(started - timedelta(days=self.overlap_days), today)

    # --- requisições --------------------------------------------------------------------------
    def url_for(self, params: list[tuple[str, object]]) -> str:
        return f"{self.api_url}?{urlencode(params)}"

    def territory_params(self, codes: Iterable[str]) -> list[tuple[str, object]]:
        return [("territory_ids", code) for code in codes]

    def get_json(self, ctx: RunContext, params) -> dict:
        result = ctx.fetcher.fetch(self.url_for(params), source=ctx.source)
        try:
            payload = json.loads(result.text)
            if not isinstance(payload["gazettes"], list):
                raise TypeError("gazettes")
        except (ValueError, KeyError, TypeError) as exc:
            raise QueridoDiarioError("Resposta inesperada da API (sem `gazettes`).") from exc
        payload["_document"] = result.document
        return payload

    def uncovered(self, ctx: RunContext) -> list[str]:
        """Municípios sem nenhum diário na janela de cobertura (sem cobertura ou coleta parada)."""
        since = ctx.today - timedelta(days=self.coverage_days)
        missing = []
        for code, name in self.municipalities.items():
            params = [
                *self.territory_params([code]),
                ("published_since", since.isoformat()),
                ("size", 1),
            ]
            if not self.get_json(ctx, params)["gazettes"]:
                missing.append(f"{name or code} ({code})")
        return missing

    def query_params(self, query: str, since: date, offset: int) -> list[tuple[str, object]]:
        return [
            *self.territory_params(self.municipalities),
            ("querystring", query),
            ("published_since", since.isoformat()),
            ("excerpt_size", self.excerpt_size),
            ("number_of_excerpts", self.excerpts),
            ("sort_by", "descending_date"),
            ("size", self.page_size),
            ("offset", offset),
        ]

    def fetch(self, ctx: RunContext) -> Iterable[RawItem]:
        since = self.window_start(ctx.today)
        seen: set[str] = set()
        for spec in self.queries:
            name, query = str(spec.get("name", "")), str(spec["query"])
            for page in range(self.max_pages):
                payload = self.get_json(ctx, self.query_params(query, since, page * self.page_size))
                gazettes = payload["gazettes"]
                for gazette in gazettes:
                    if not isinstance(gazette, dict):
                        continue
                    for number, excerpt in enumerate(gazette.get("excerpts") or [], 1):
                        item = {**gazette, "excerpt": clean_text(excerpt), "query_name": name}
                        item.pop("excerpts", None)
                        key = f"{gazette.get('territory_id')}|{gazette.get('date')}|"
                        key += excerpt_hash(item["excerpt"])
                        if not item["excerpt"] or key in seen:
                            continue
                        seen.add(key)
                        yield RawItem(
                            data=item,
                            source_url=str(gazette.get("url") or ""),
                            raw_document=payload["_document"],
                            label=f"{name} p{page + 1} {gazette.get('territory_id')}#{number}",
                        )
                total = payload.get("total_gazettes")
                done = isinstance(total, int) and page * self.page_size + len(gazettes) >= total
                if done or len(gazettes) < self.page_size:
                    break
        missing = self.uncovered(ctx)
        if missing:
            raise QueridoDiarioError(
                "Sem diário na API nos últimos "
                f"{self.coverage_days} dias: {', '.join(missing)}. Sem cobertura? Monitore a "
                "página do município com `html_watch`."
            )

    # --- normalização -------------------------------------------------------------------------
    def normalize(self, item: RawItem) -> OpportunityCandidate | None:
        data = item.data
        code = str(data.get("territory_id") or "")
        excerpt = clean_text(data.get("excerpt"))
        day = parse_day(data.get("date"))
        pdf = str(data.get("url") or "").strip()
        if code not in self.municipalities or not excerpt or day is None or not pdf:
            return None
        if any(p.search(excerpt) for p in self.excludes):
            return None
        city = clean_text(data.get("territory_name")) or self.municipalities[code]
        uf = str(data.get("state_code") or "SP")[:2].upper()
        published = timezone.make_aware(datetime.combine(day, time.min))
        edition = clean_text(data.get("edition"))
        title = f"Diário Oficial de {city} em {day:%d/%m/%Y}: {excerpt}"[:300]
        fields = {
            "kind": kind_for(excerpt),
            "official_url": pdf,
            "organizer_name": f"Prefeitura de {city}",
            "municipality_name": city,
            "uf": uf,
            "scope": Opportunity.Scope.MUNICIPAL,
            "categories": categories_for(excerpt),
            "status": Opportunity.Status.UNKNOWN,
            "description": excerpt,
        }
        claims = {
            "title": title,
            "municipality_name": city,
            "published_at": published.isoformat(),
            "edition": edition,
            "gazette_url": pdf,
            "matched_query": data.get("query_name", ""),
        }
        evidence = [
            EvidenceDraft(
                field=name,
                value=value,
                source_url=pdf,
                source_name="Querido Diário",
                excerpt=excerpt,
            )
            for name, value in claims.items()
            if value not in ("", None)
        ]
        return OpportunityCandidate(
            title=title,
            fields=fields,
            canonical_key=canonical_key(code, day, excerpt),
            evidence=evidence,
        )
