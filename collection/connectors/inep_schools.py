"""INEP — Catálogo de Escolas: escolas **privadas e ativas** da região de atuação (E17).

Conector `dataset`: lê a exportação CSV do Catálogo de Escolas (ou os microdados do Censo Escolar).
Configure a `Source` (`inep-escolas`) com **um** destes:

    {"path": "data/inep/catalogo_escolas.csv"}   # arquivo baixado à mão (não usa a rede)
    {"url": "https://..."}                        # baixado pelo PoliteFetcher (exige `robots_ok`)

e o escopo geográfico (padrão: municípios até `GEO_REGIONAL_KM` da base + polos prioritários):

    {"max_km": 150} ou {"municipalities": ["Araraquara/SP", "Bauru/SP"]}

O layout do INEP muda por ano: as colunas são mapeadas **por nome** (sem acento/caixa;
`COLUMNS`), nunca por posição. Falta de coluna obrigatória → erro claro, nada é importado. O
layout real ainda não foi conferido contra um arquivo baixado (E01): se o nome de uma coluna
mudou, ajuste `COLUMNS`.

Cada escola vira `Organization(kind=school, inep_code=...)` com `Evidence(observed)` (nome, código,
dependência, situação, endereço, telefone institucional, etapas, porte) apontando para a fonte.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from collection.base import EvidenceDraft, OrganizationCandidate, RawItem, RunContext
from collection.registry import register
from core.models import Municipality
from core.services.geography import haversine_km
from core.services.normalize import name_key

SLUG = "inep-escolas"
DEFAULT_PATH = "data/inep/catalogo_escolas.csv"

# campo interno -> nomes aceitos do cabeçalho (comparados com `name_key`: sem acento, minúsculo).
COLUMNS = {
    "inep_code": ("codigo inep", "co_entidade", "codigo da escola"),
    "name": ("escola", "no_entidade", "nome da escola"),
    "uf": ("uf", "sg_uf"),
    "municipality": ("municipio", "no_municipio"),
    "dependency": ("dependencia administrativa", "tp_dependencia"),
    "status": (
        "restricao de atendimento",
        "situacao de funcionamento",
        "tp_situacao_funcionamento",
    ),
    "address": ("endereco", "ds_endereco"),
    "phone": ("telefone", "nu_telefone"),
    "stages": (
        "etapas e modalidade de ensino oferecidas",
        "etapas e modalidades de ensino oferecidas",
    ),
    "size": ("porte da escola",),
    "lat": ("latitude", "nu_latitude"),
    "lon": ("longitude", "nu_longitude"),
}
REQUIRED = ("inep_code", "name", "uf", "municipality", "dependency")
PRIVATE_VALUES = {"privada", "4"}
LOWERCASE_WORDS = {"de", "da", "do", "das", "dos", "e", "em", "a", "o"}


class InepError(ValueError):
    pass


def map_headers(headers: Iterable[str]) -> dict[str, str]:
    """campo interno → nome real da coluna. Levanta `InepError` se faltar coluna obrigatória."""
    by_key = {name_key(h): h for h in headers if h}
    mapping = {}
    for field, aliases in COLUMNS.items():
        for alias in aliases:
            if name_key(alias) in by_key:
                mapping[field] = by_key[name_key(alias)]
                break
    missing = [f for f in REQUIRED if f not in mapping]
    if missing:
        raise InepError(
            "Colunas obrigatórias não encontradas: "
            + ", ".join(f"{f} (aceitas: {', '.join(COLUMNS[f])})" for f in missing)
            + ". O layout do INEP mudou? Ajuste COLUMNS em inep_schools.py."
        )
    return mapping


def is_private(value: str) -> bool:
    return name_key(value) in PRIVATE_VALUES


def is_active(value: str | None) -> bool:
    """Sem coluna de situação não dá para saber: aceita. Com ela, só "em atividade" (ou 1).

    A exportação do Catálogo traz a coluna «Restrição de Atendimento»; só «Escola em funcionamento
    e sem restrição de atendimento» interessa (exclusivas de AEE, de atividade complementar ou de
    alunos com deficiência ficam de fora).
    """
    if not value:
        return True
    key = name_key(value)
    return key == "1" or "em atividade" in key or "em funcionamento" in key


def pretty_name(name: str) -> str:
    """O INEP usa CAIXA ALTA; converte para título, mantendo siglas curtas e conectivos."""
    name = " ".join(name.split())
    if not name.isupper():
        return name
    words = []
    for index, word in enumerate(name.lower().split()):
        words.append(word if index and word in LOWERCASE_WORDS else word.capitalize())
    return " ".join(words)


def split_stages(text: str) -> list[str]:
    return [part.strip() for part in text.replace("|", ",").split(",") if part.strip()]


def scope_keys(config: dict, home: Municipality | None = None) -> set[tuple[str, str]]:
    """Conjunto `(nome normalizado, UF)` dos municípios no escopo da coleta."""
    if config.get("municipalities"):
        keys = set()
        for entry in config["municipalities"]:
            place, _, uf = str(entry).partition("/")
            keys.add((name_key(place), uf.strip().upper()))
        return keys
    home = home or Municipality.objects.filter(ibge_code=settings.HOME_MUNICIPALITY_IBGE).first()
    if home is None:
        raise InepError("Município-base não carregado: rode `make seed` (load_municipalities).")
    max_km = float(config.get("max_km", settings.GEO_REGIONAL_KM))
    hubs = {str(code) for code in settings.PRIORITY_HUBS_IBGE}
    return {
        (m.name_key, m.uf)
        for m in Municipality.objects.all()
        if str(m.ibge_code) in hubs or haversine_km(home.lat, home.lon, m.lat, m.lon) <= max_km
    }


def _decode(path: Path) -> str:
    """Lê o arquivo como UTF-8 (com BOM) e, se não for, como Latin-1 (padrão antigo do INEP)."""
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _reader(text: str) -> csv.DictReader:
    """`DictReader` com o delimitador (`;` ou `,`) deduzido do cabeçalho."""
    first_line = text.split("\n", 1)[0]
    delimiter = ";" if first_line.count(";") >= first_line.count(",") else ","
    return csv.DictReader(io.StringIO(text, newline=""), delimiter=delimiter)


@register(slug=SLUG)
class InepSchoolsConnector:
    kind = "dataset"

    def __init__(self, source):
        self.source = source
        self.slug = source.slug
        self.config = source.config or {}
        self.url = self.config.get("url", "")
        path = self.config.get("path") or ("" if self.url else DEFAULT_PATH)
        self.path = Path(path) if path else None
        if self.path is not None and not self.path.is_absolute():
            self.path = Path(settings.BASE_DIR) / self.path
        # Origem citada nas evidências: a página oficial do catálogo, não o arquivo local.
        self.source_url = self.config.get("source_url") or self.url or source.base_url
        if not self.source_url:
            raise ImproperlyConfigured("Defina `base_url` (página oficial do INEP) na fonte.")

    def _load(self, ctx: RunContext) -> tuple[str, object]:
        if self.url:
            if ctx.fetcher is None:
                raise InepError(
                    "Fonte com `url` exige o PoliteFetcher (marque `coleta permitida`)."
                )
            result = ctx.fetcher.fetch(self.url, source=self.source)
            return result.text, result.document
        try:
            return _decode(self.path), None
        except OSError as exc:
            raise InepError(
                f"Não foi possível ler {self.path.name}: {exc.strerror}. "
                "Baixe o Catálogo de Escolas do INEP e salve nesse caminho."
            ) from exc

    def fetch(self, ctx: RunContext) -> Iterable[RawItem]:
        text, document = self._load(ctx)
        reader = _reader(text)
        mapping = map_headers(reader.fieldnames or [])
        keys = scope_keys(self.config)
        for number, row in enumerate(reader, start=2):
            data = {field: (row.get(column) or "").strip() for field, column in mapping.items()}
            if (name_key(data["municipality"]), data["uf"].upper()) not in keys:
                continue
            if not is_private(data["dependency"]) or not is_active(data.get("status")):
                continue
            yield RawItem(
                data=data,
                source_url=self.source_url,
                raw_document=document,
                label=f"linha {number}",
            )

    def normalize(self, item: RawItem) -> OrganizationCandidate | None:
        data = item.data
        code = data["inep_code"].strip()
        if not code:
            raise InepError("sem código INEP.")
        code = code.zfill(8)
        name = pretty_name(data["name"])
        if not name:
            raise InepError("sem nome da escola.")
        uf = data["uf"].upper()
        fields = {
            "kind": "school",
            "inep_code": code,
            "municipality_name": data["municipality"],
            "uf": uf,
            "address": data.get("address", ""),
        }
        for axis in ("lat", "lon"):
            value = data.get(axis, "").replace(",", ".")
            try:
                fields[axis] = float(value) if value else None
            except ValueError:
                fields[axis] = None
        fields = {k: v for k, v in fields.items() if v not in ("", None)}

        stages = split_stages(data.get("stages", ""))
        claims = {
            "name": name,
            "inep_code": code,
            "administrative_dependency": "Privada",
            "municipality_name": data["municipality"],
            "uf": uf,
            "address": data.get("address", ""),
            "phone": data.get("phone", ""),
            "education_stages": stages,
            "school_size": data.get("size", ""),
        }
        if data.get("status"):
            claims["operating_status"] = data["status"]
        evidence = [
            EvidenceDraft(
                field=field,
                value=value,
                source_url=item.source_url,
                source_name="INEP — Catálogo de Escolas",
            )
            for field, value in claims.items()
            if value not in ("", None, [])
        ]
        return OrganizationCandidate(name=name, fields=fields, evidence=evidence)
