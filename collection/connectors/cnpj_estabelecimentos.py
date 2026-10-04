"""Receita Federal — dados abertos do CNPJ: empresas ativas da região por CNAE (E25).

Conector `dataset` **de arquivo local** (os arquivos `EstabelecimentosN.zip` têm ~1 GB cada: baixe
à mão, o fetcher não os lê). Configure a `Source` (`cnpj-estabelecimentos`):

    {"path": "data/cnpj", "groups": ["marketing", "courses", "publishing", "events"],
     "max_km": 150}  # ou {"municipalities": ["Araraquara/SP"]}

`path` pode ser um arquivo (`.zip` ou `.csv`), uma pasta (todos os `Estabelecimentos*`) ou um glob.
O código de município da Receita é o do **Tom/SRF**, não o do IBGE: a tabela `Municipios` (mesmo
site, `code;NOME`) fica em `municipios_path` (padrão `data/cnpj/Municipios.csv`) e casa por nome.
O arquivo é lido em **streaming**, linha a linha, sem cabeçalho (layout de 30 colunas por posição,
`;`, ISO-8859-1); linha curta ou com CNPJ inválido é descartada sem erro.

Filtros: situação cadastral ativa (`02`), município no escopo, CNAE principal de um dos `groups`
de `data/seeds/cnae_services.csv` (dado, não código) e **nome fantasia presente**: sem ele só há a
razão social, que no MEI é nome de pessoa física (LGPD). Minimização: **não** guardamos e-mail,
telefone, endereço de rua nem sócios; só CNPJ, nome fantasia, CNAE, município/UF e data de início.
Layout e códigos não foram conferidos contra um arquivo real (E01): ajuste `COL` se mudar.
"""

from __future__ import annotations

import csv
import glob
import io
import zipfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from functools import cache
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from collection.base import EvidenceDraft, OrganizationCandidate, RawItem, RunContext
from collection.connectors.inep_schools import pretty_name, scope_keys
from collection.registry import register
from core.services.normalize import is_valid_cnpj, name_key, normalize_cnpj

SLUG = "cnpj-estabelecimentos"
DEFAULT_PATH = "data/cnpj"
DEFAULT_MUNICIPIOS = "data/cnpj/Municipios.csv"
DEFAULT_GROUPS = ("marketing", "courses", "publishing", "events")
CNAE_MAP_PATH = "data/seeds/cnae_services.csv"
ACTIVE = "02"
COLUMN_COUNT = 30

# posição (layout «Estabelecimentos» da Receita, 30 colunas sem cabeçalho)
COL = {
    "basic": 0,
    "order": 1,
    "check": 2,
    "fantasy_name": 4,
    "status": 5,
    "start_date": 10,
    "cnae_main": 11,
    "uf": 19,
    "municipality_code": 20,
}


class CnpjError(ValueError):
    pass


@cache
def cnae_map() -> dict[str, dict]:
    """CNAE (7 dígitos) → grupo, segmento e serviços sugeridos (`data/seeds/cnae_services.csv`)."""
    path = Path(settings.BASE_DIR) / CNAE_MAP_PATH
    with path.open(encoding="utf-8", newline="") as handle:
        return {
            row["cnae"]: {
                "group": row["group"],
                "segment": row["segment"],
                "services": row["services"].split("|"),
            }
            for row in csv.DictReader(handle)
        }


def _resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else Path(settings.BASE_DIR) / path


def find_files(path_text: str) -> list[Path]:
    """Arquivo único, pasta (`Estabelecimentos*`) ou glob → lista ordenada de arquivos."""
    path = _resolve(path_text)
    if path.is_dir():
        files = [
            p
            for p in sorted(path.iterdir())
            if p.is_file() and "estabele" in p.name.lower() and p.suffix.lower() in {".zip", ".csv"}
        ]
    elif path.is_file():
        files = [path]
    else:
        files = [Path(p) for p in sorted(glob.glob(str(path)))]
    if not files:
        raise CnpjError(
            f"Nenhum arquivo `Estabelecimentos` em {path_text!r}. Baixe os dados abertos do CNPJ "
            "(Receita Federal) e salve os .zip nessa pasta."
        )
    return files


@contextmanager
def _open_lines(path: Path) -> Iterator[Iterator[str]]:
    """Linhas de texto (Latin-1) do CSV ou de cada membro do `.zip`, sem carregar tudo."""
    if path.suffix.lower() != ".zip":
        with path.open("r", encoding="latin-1", newline="") as handle:
            yield iter(handle)
        return
    with zipfile.ZipFile(path) as archive:

        def lines():
            for member in archive.namelist():
                if member.endswith("/"):
                    continue
                with archive.open(member) as raw:
                    yield from io.TextIOWrapper(raw, encoding="latin-1", newline="")

        yield lines()


def load_municipality_names(path_text: str) -> dict[str, str]:
    """Código Tom → nome normalizado. A tabela `Municipios` não traz a UF (vem de cada linha)."""
    path = _resolve(path_text)
    try:
        text = path.read_bytes().decode("latin-1")
    except OSError as exc:
        raise CnpjError(
            f"Não foi possível ler {path.name}: {exc.strerror}. Baixe a tabela `Municipios` da "
            "Receita Federal e salve nesse caminho."
        ) from exc
    names = {}
    for row in csv.reader(io.StringIO(text, newline=""), delimiter=";"):
        if len(row) >= 2 and row[0].strip():
            names[row[0].strip().strip('"').lstrip("0")] = name_key(row[1])
    if not names:
        raise CnpjError(f"{path.name} está vazio ou não tem o formato `código;NOME`.")
    return names


def parse_rows(lines: Iterable[str]) -> Iterator[list[str]]:
    reader = csv.reader(lines, delimiter=";", quotechar='"')
    for row in reader:
        if len(row) >= COLUMN_COUNT:
            yield [cell.strip() for cell in row]


def cnpj_of(row: list[str]) -> str:
    return normalize_cnpj(row[COL["basic"]] + row[COL["order"]] + row[COL["check"]])


def parse_date(text: str) -> str:
    """`AAAAMMDD` → ISO; `0`, vazio ou inválido → vazio (nada inventado)."""
    if len(text) == 8 and text.isdigit() and text != "00000000":
        year, month, day = text[:4], text[4:6], text[6:]
        if "01" <= month <= "12" and "01" <= day <= "31" and year >= "1900":
            return f"{year}-{month}-{day}"
    return ""


@register(slug=SLUG)
class CnpjEstablishmentsConnector:
    kind = "dataset"

    def __init__(self, source):
        self.source = source
        self.slug = source.slug
        self.config = source.config or {}
        self.path = self.config.get("path") or DEFAULT_PATH
        self.municipios_path = self.config.get("municipios_path") or DEFAULT_MUNICIPIOS
        groups = set(self.config.get("groups") or DEFAULT_GROUPS)
        known = {entry["group"] for entry in cnae_map().values()}
        if groups - known:
            raise ImproperlyConfigured(
                f"Grupos de CNAE desconhecidos: {sorted(groups - known)} (há: {sorted(known)})."
            )
        self.cnaes = {cnae: e for cnae, e in cnae_map().items() if e["group"] in groups}
        self.source_url = self.config.get("source_url") or source.base_url
        if not self.source_url:
            raise ImproperlyConfigured("Defina `base_url` (página dos dados abertos do CNPJ).")

    def fetch(self, ctx: RunContext) -> Iterable[RawItem]:
        files = find_files(self.path)
        scope = scope_keys(self.config)
        tom_names = load_municipality_names(self.municipios_path)
        wanted_codes = {code for code, key in tom_names.items() if any(key == k for k, _ in scope)}
        wanted_uf = {uf for _, uf in scope}
        for file in files:
            with _open_lines(file) as lines:
                for number, row in enumerate(parse_rows(lines), start=1):
                    if row[COL["status"]] != ACTIVE:
                        continue
                    cnae = row[COL["cnae_main"]]
                    code = row[COL["municipality_code"]].lstrip("0")
                    uf = row[COL["uf"]].upper()
                    if cnae not in self.cnaes or code not in wanted_codes or uf not in wanted_uf:
                        continue
                    if (tom_names[code], uf) not in scope:
                        continue
                    cnpj = cnpj_of(row)
                    if not row[COL["fantasy_name"]] or not is_valid_cnpj(cnpj):
                        continue
                    yield RawItem(
                        data={
                            "cnpj": cnpj,
                            "name": row[COL["fantasy_name"]],
                            "cnae": cnae,
                            "uf": uf,
                            "municipality": tom_names[code],
                            "start_date": parse_date(row[COL["start_date"]]),
                        },
                        source_url=self.source_url,
                        label=f"{file.name} linha {number}",
                    )

    def normalize(self, item: RawItem) -> OrganizationCandidate | None:
        data = item.data
        entry = self.cnaes[data["cnae"]]
        name = pretty_name(data["name"])
        municipality = _municipality_label(data["municipality"])
        fields = {
            "kind": "company",
            "cnpj": data["cnpj"],
            "cnae_main": data["cnae"],
            "segment": entry["segment"],
            "municipality_name": municipality,
            "uf": data["uf"],
        }
        claims = {
            "name": name,
            "cnpj": data["cnpj"],
            "cnae_main": data["cnae"],
            "registration_status": "Ativa",
            "activity_start_date": data["start_date"],
            "municipality_name": municipality,
            "uf": data["uf"],
        }
        evidence = [
            EvidenceDraft(
                field=field,
                value=value,
                source_url=item.source_url,
                source_name="Receita Federal — dados abertos do CNPJ",
            )
            for field, value in claims.items()
            if value not in ("", None)
        ]
        evidence.append(
            EvidenceDraft(
                field="service_hint",
                value=entry["services"],
                kind="inferred",
                method="rule:cnae_services",
                source_url=item.source_url,
                source_name="Receita Federal — dados abertos do CNPJ",
                excerpt=f"CNAE principal {data['cnae']} ({entry['segment']})",
            )
        )
        return OrganizationCandidate(name=name, fields=fields, evidence=evidence)


def _municipality_label(key: str) -> str:
    """Nome normalizado (sem acento) → título; o vínculo com o IBGE é resolvido pelo modelo."""
    return pretty_name(key.upper())
