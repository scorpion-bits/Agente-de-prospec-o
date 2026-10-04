"""PNCP — contratações públicas com propostas abertas (E27, ADR-041).

Conector `api` sobre `GET /api/consulta/v1/contratacoes/proposta` do Portal Nacional de
Contratações Públicas, sempre pelo `PoliteFetcher`. Uma consulta por (UF × modalidade); cada
contratação relevante vira uma `Opportunity(kind=procurement)` (`credenciamento` →
`call_for_partners`). O formato do JSON e os parâmetros vêm do manual das APIs de consulta e de
memória e **não** foram conferidos contra a resposta real (E01 pendente: o ambiente do Claude não
alcança o PNCP): `normalize` é tolerante a campos ausentes, a fixture é sintética, e resposta sem
`data` é erro explícito, nunca coleta vazia silenciosa. Configure a `Source` (`pncp`):

    {"ufs": ["SP"],
     "modalities": [{"code": 6, "name": "Pregão eletrônico"}, ...],   # códigos do PNCP
     "keywords": ["curso", "oficina", "jogo", ...],   # prefixos sem acento/maiúscula
     "exclude_patterns": ["ar condicionado", ...],    # regex no objeto: descarta falso positivo
     "horizon_days": 90,    # propostas que encerram até hoje + N dias
     "page_size": 50, "max_pages_per_query": 4,
     "include_closed": false}

Só entra o que o PNCP informa (ADR-004): datas de proposta (sem fuso valem Brasília), valor
estimado (valor zero ou ausente = sigiloso/desconhecido, fica em branco), `cota exclusiva ME/EPP`
só quando o **texto** diz isso (nunca `False` por ausência). Habilitação, atestados de capacidade e
requisitos ficam para a E11 ler o edital (sem `extraction_version`). Falha de uma consulta
(bloqueio, HTTP, formato) não derruba as outras: os erros saem juntos no fim (status `partial`).
HTTP 204 (o PNCP responde assim quando não há resultado) é lista vazia. Sem IA. Chave de dedupe
`pncp:<numeroControlePNCP>`; cada afirmação vira `Evidence(observed)` com o link do edital.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from django.utils import timezone

from collection.base import EvidenceDraft, OpportunityCandidate, RawItem, RunContext
from collection.fetcher import FetchError, FetchHTTPError
from collection.registry import register
from core.models import Opportunity

SLUG = "pncp"
API_URL = "https://pncp.gov.br/api/consulta/v1/contratacoes/proposta"
EDITAL_URL = "https://pncp.gov.br/app/editais/{cnpj}/{year}/{sequence}"
CREDENCIAMENTO = 12
# Códigos de modalidade do PNCP (manual das APIs; de memória, **não** conferidos — P29).
DEFAULT_MODALITIES = (
    {"code": 4, "name": "Concorrência eletrônica"},
    {"code": 6, "name": "Pregão eletrônico"},
    {"code": 8, "name": "Dispensa de licitação"},
    {"code": CREDENCIAMENTO, "name": "Credenciamento"},
)
DEFAULT_UFS = ("SP",)
# Prefixos (sem acento, minúsculas) no início de palavra que ligam a contratação ao que a Scorpion
# Bits faz: cursos e oficinas, software/web, jogos, robótica.
DEFAULT_KEYWORDS = (
    "curso",
    "oficina",
    "capacitacao",
    "treinamento",
    "ministra",
    "jogo",
    "game",
    "gamifica",
    "software",
    "aplicativo",
    "website",
    "site institucional",
    "desenvolvimento de sistema",
    "desenvolvimento de plataforma",
    "plataforma digital",
    "programacao",
    "robotica",
)
# Falsos positivos conhecidos (regex sem acento/maiúscula): «jogos» esportivos, cursos de formação
# militar/saúde e «oficina» mecânica.
DEFAULT_EXCLUDES = (
    r"jogos\s+(abertos|regionais|escolares|olimpicos|paraolimpicos)",
    r"oficina\s+(mecanica|de\s+manutencao)",
    r"\bveiculo",
    r"\bmedicament",
    r"\bobra[s]?\b",
)
DEFAULT_HORIZON_DAYS = 90
DEFAULT_PAGE_SIZE = 50
DEFAULT_MAX_PAGES = 4
LOCAL_TZ = ZoneInfo("America/Sao_Paulo")
CONTROL_RE = re.compile(r"^(\d{14})-\d+-(\d+)/(\d{4})$")
EXCLUSIVE_RE = re.compile(
    r"(exclusiv\w*|reservad\w*)\s+(a|de|para|as?|aos?)?\s*"
    r"(me\b|epp\b|mei\b|micro\s*empresa|empresas?\s+de\s+pequeno\s+porte|"
    r"microempreendedor)",
    re.I,
)
SCOPE_BY_SPHERE = {"F": "national", "E": "state", "D": "state", "M": "municipal"}
CATEGORY_WORDS = {
    Opportunity.Category.GAMES: ("jogo", "game", "gamifica"),
    Opportunity.Category.EDUCATION: ("curso", "oficina", "capacitacao", "treinamento", "ministra"),
    Opportunity.Category.TECHNOLOGY: (
        "software",
        "aplicativo",
        "website",
        "site ",
        "sistema",
        "plataforma",
        "programacao",
        "robotica",
    ),
}
TAG_RE = re.compile(r"<[^>]+>")


class PncpError(ValueError):
    pass


def fold(value) -> str:
    """Minúsculas sem acento e com espaços normalizados (comparação de palavras-chave)."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(TAG_RE.sub(" ", text).lower().split())


def clean_text(value) -> str:
    return " ".join(TAG_RE.sub(" ", str(value or "")).split())


def parse_moment(value) -> datetime | None:
    """Data/hora de proposta como veio do PNCP (ISO sem fuso = Brasília); ilegível = `None`."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=LOCAL_TZ)
    return moment.astimezone(timezone.get_current_timezone())


def parse_amount(value) -> Decimal | None:
    """Valor estimado em R$; ausente, zero, negativo ou fora do limite do campo = `None`."""
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None
    return amount if Decimal(0) < amount < Decimal(10) ** 12 else None


def edital_url(control_number: str, origin_link: str = "") -> str:
    """Link da página do edital no PNCP (montado do número de controle), senão o do sistema de
    origem se for http(s); senão vazio."""
    match = CONTROL_RE.match(control_number)
    if match:
        cnpj, sequence, year = match.groups()
        return EDITAL_URL.format(cnpj=cnpj, year=year, sequence=int(sequence))
    link = origin_link.strip()
    return link if link.startswith(("http://", "https://")) else ""


def status_for(opens: datetime | None, deadline: datetime | None, now: datetime) -> str:
    if deadline is not None and deadline < now:
        return Opportunity.Status.CLOSED
    if opens is not None and opens > now:
        return Opportunity.Status.UPCOMING
    if opens is not None or deadline is not None:
        return Opportunity.Status.OPEN
    return Opportunity.Status.UNKNOWN


def categories_for(text: str) -> list[str]:
    folded = fold(text)
    return [c for c, words in CATEGORY_WORDS.items() if any(w in folded for w in words)]


@register(slug=SLUG)
class PncpConnector:
    kind = "api"

    def __init__(self, source):
        self.source = source
        self.slug = source.slug
        config = source.config or {}
        self.api_url = str(config.get("api_url") or API_URL)
        self.ufs = tuple(str(u).upper() for u in config.get("ufs") or DEFAULT_UFS)
        self.modalities = tuple(config.get("modalities") or DEFAULT_MODALITIES)
        if not self.ufs or not all(len(u) == 2 for u in self.ufs):
            raise PncpError(f"`ufs` inválidas: {self.ufs!r}.")
        if not all(str(m.get("code", "")).isdigit() for m in self.modalities):
            raise PncpError("Cada modalidade precisa de `code` numérico.")
        self.keywords = tuple(fold(k) for k in config.get("keywords") or DEFAULT_KEYWORDS)
        patterns = config.get("exclude_patterns")
        patterns = DEFAULT_EXCLUDES if patterns is None else patterns
        try:
            self.excludes = [re.compile(p, re.I) for p in patterns]
        except re.error as exc:
            raise PncpError(f"Regex inválida em `exclude_patterns`: {exc}") from exc
        self.horizon_days = int(config.get("horizon_days", DEFAULT_HORIZON_DAYS))
        self.page_size = int(config.get("page_size", DEFAULT_PAGE_SIZE))
        self.max_pages = int(config.get("max_pages_per_query", DEFAULT_MAX_PAGES))
        self.include_closed = bool(config.get("include_closed", False))

    # --- requisições --------------------------------------------------------------------------
    def page_url(self, uf: str, modality: dict, page: int, today: date) -> str:
        until = today + timedelta(days=self.horizon_days)
        params = [
            ("dataFinal", until.strftime("%Y%m%d")),
            ("codigoModalidadeContratacao", int(modality["code"])),
            ("uf", uf),
            ("pagina", page),
            ("tamanhoPagina", self.page_size),
        ]
        return f"{self.api_url}?{urlencode(params)}"

    def fetch_query(self, ctx: RunContext, uf: str, modality: dict) -> Iterable[RawItem]:
        label = f"{uf}/{modality.get('name') or modality['code']}"
        for page in range(1, self.max_pages + 1):
            url = self.page_url(uf, modality, page, ctx.today)
            try:
                result = ctx.fetcher.fetch(url, source=ctx.source)
            except FetchHTTPError as exc:
                if exc.status_code == 204:  # sem resultado
                    return
                raise
            try:
                payload = json.loads(result.text)
                rows = payload["data"]
                if not isinstance(rows, list):
                    raise TypeError("data")
            except (ValueError, KeyError, TypeError) as exc:
                raise PncpError(f"{label}: resposta inesperada (sem `data`).") from exc
            for position, row in enumerate(rows, 1):
                if isinstance(row, dict):
                    yield RawItem(
                        data={**row, "_modality": modality},
                        source_url=edital_url(
                            str(row.get("numeroControlePNCP") or ""),
                            str(row.get("linkSistemaOrigem") or ""),
                        )
                        or url,
                        raw_document=result.document,
                        label=f"{label} p{page} #{position}",
                    )
            pages = payload.get("totalPaginas")
            if len(rows) < self.page_size or (isinstance(pages, int) and page >= pages):
                return

    def fetch(self, ctx: RunContext) -> Iterable[RawItem]:
        errors = []
        for uf in self.ufs:
            for modality in self.modalities:
                try:
                    yield from self.fetch_query(ctx, uf, modality)
                except (FetchError, PncpError) as exc:
                    errors.append(f"{uf}/{modality.get('name') or modality['code']}: {exc}")
        if errors:
            raise PncpError("; ".join(errors))

    # --- normalização -------------------------------------------------------------------------
    def relevant(self, text: str) -> bool:
        folded = fold(text)
        return any(re.search(rf"\b{re.escape(k)}", folded) for k in self.keywords)

    def normalize(self, item: RawItem) -> OpportunityCandidate | None:
        data = item.data
        control = str(data.get("numeroControlePNCP") or "").strip()
        subject = clean_text(data.get("objetoCompra"))
        complement = clean_text(data.get("informacaoComplementar"))
        link = edital_url(control, str(data.get("linkSistemaOrigem") or ""))
        if not control or not subject or not link:
            return None
        text = f"{subject} {complement}"
        if not self.relevant(subject) or any(p.search(fold(text)) for p in self.excludes):
            return None

        opens = parse_moment(data.get("dataAberturaProposta"))
        deadline = parse_moment(data.get("dataEncerramentoProposta"))
        status = status_for(opens, deadline, timezone.now())
        if status == Opportunity.Status.CLOSED and not self.include_closed:
            return None

        organ = data.get("orgaoEntidade") if isinstance(data.get("orgaoEntidade"), dict) else {}
        unit = data.get("unidadeOrgao") if isinstance(data.get("unidadeOrgao"), dict) else {}
        organizer = clean_text(organ.get("razaoSocial"))
        modality = data.get("_modality") or {}
        modality_name = clean_text(data.get("modalidadeNome")) or str(modality.get("name") or "")
        is_call = data.get("modalidadeId") == CREDENCIAMENTO or modality.get("code") == (
            CREDENCIAMENTO
        )
        amount = parse_amount(data.get("valorTotalEstimado"))
        sphere = SCOPE_BY_SPHERE.get(str(organ.get("esferaId") or "").upper(), "")
        uf = str(unit.get("ufSigla") or "")[:2].upper()
        city = clean_text(unit.get("municipioNome"))
        title = f"{subject[:250]} — {organizer}"[:300] if organizer else subject[:300]
        exclusive = True if EXCLUSIVE_RE.search(fold(text)) else None
        fields = {
            "kind": (
                Opportunity.Kind.CALL_FOR_PARTNERS if is_call else Opportunity.Kind.PROCUREMENT
            ),
            "official_url": link,
            "organizer_name": organizer[:200],
            "categories": categories_for(subject),
            "status": status,
            "opens_at": opens,
            "deadline_at": deadline,
            "description": subject,
            "uf": uf,
            "municipality_name": city,
            "prize_amount_brl": amount,
            "prize_text": f"Valor estimado: R$ {amount:,.2f}" if amount else "",
            "exclusive_small_business": exclusive,
            "benefits": [Opportunity.Benefit.CONTRACT],
            **({"scope": sphere} if sphere else {}),
        }
        claims = {
            "title": subject,
            "organizer_name": organizer,
            "procurement_modality": modality_name,
            "estimated_value_brl": str(amount) if amount else "",
            "opens_at": opens.isoformat() if opens else "",
            "deadline_at": deadline.isoformat() if deadline else "",
            "municipality_name": city,
            "exclusive_small_business": "sim" if exclusive else "",
            "pncp_control_number": control,
        }
        evidence = [
            EvidenceDraft(
                field=name,
                value=value,
                source_url=link,
                source_name="PNCP",
                excerpt=(complement or subject)[:300],
            )
            for name, value in claims.items()
            if value not in ("", None)
        ]
        return OpportunityCandidate(
            title=title,
            fields=fields,
            canonical_key=f"pncp:{control}",
            evidence=evidence,
        )
