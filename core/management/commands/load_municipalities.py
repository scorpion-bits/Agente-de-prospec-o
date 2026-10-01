"""Carrega a tabela de municípios (código IBGE, UF, coordenada da sede). Idempotente.

Fonte padrão: `data/seeds/municipios.csv` (5.570 municípios; dado público, ver ADR-022). Colunas:
codigo_ibge, nome, uf, latitude, longitude, capital. Rodar de novo atualiza as linhas existentes
(é dado de referência, sem edição manual) e não apaga as que sumiram do arquivo.

Depois da carga confere a base (`HOME_MUNICIPALITY_IBGE`) e os polos (`PRIORITY_HUBS_IBGE`).
Para ligar organizações e oportunidades já cadastradas aos municípios: `resolve_municipalities`.
"""

import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import UF_BY_IBGE_CODE, Municipality
from core.services.normalize import name_key

DEFAULT_FILE = Path("data/seeds/municipios.csv")
REQUIRED = ("codigo_ibge", "nome", "latitude", "longitude")
# Caixa do território brasileiro (com folga): barra coordenada trocada ou fora do país.
LAT_RANGE, LON_RANGE = (-34.0, 6.0), (-75.0, -32.0)


class Command(BaseCommand):
    help = "Carrega os municípios do IBGE de um CSV (padrão: data/seeds/municipios.csv)."

    def add_arguments(self, parser):
        parser.add_argument("file", nargs="?", type=Path, default=DEFAULT_FILE)

    def handle(self, *args, file, **options):
        rows = self._read(file)
        parsed = [self._values(line, row) for line, row in rows]
        existing = set(Municipality.objects.values_list("ibge_code", flat=True))
        objects = []
        for values in parsed:
            municipality = Municipality(**values)
            municipality.region = Municipality.REGION_BY_DIGIT[str(values["ibge_code"])[0]]
            municipality.name_key = name_key(values["name"])  # `bulk_create` não chama `save()`
            objects.append(municipality)
        with transaction.atomic():
            Municipality.objects.bulk_create(
                objects,
                batch_size=1000,
                update_conflicts=True,
                unique_fields=["ibge_code"],
                update_fields=["name", "name_key", "uf", "region", "lat", "lon", "is_capital"],
            )
            self._check_home_and_hubs()
        created = len({v["ibge_code"] for v in parsed} - existing)
        updated = len({v["ibge_code"] for v in parsed} & existing)
        self.stdout.write(
            f"Municípios: {created} criado(s), {updated} atualizado(s) "
            f"(total {Municipality.objects.count()})."
        )

    def _read(self, file):
        try:
            with file.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
                if missing:
                    raise CommandError(f"{file}: faltam as colunas {', '.join(missing)}.")
                return [(n, row) for n, row in enumerate(reader, start=2)]
        except (OSError, UnicodeDecodeError, csv.Error) as exc:
            raise CommandError(f"Não foi possível ler {file}: {exc}") from exc

    def _values(self, line, row):
        try:
            code = int(row["codigo_ibge"])
            lat, lon = float(row["latitude"]), float(row["longitude"])
        except ValueError as exc:
            raise CommandError(f"Linha {line}: código ou coordenada inválidos.") from exc
        uf = (row.get("uf") or UF_BY_IBGE_CODE.get(code // 100000, "")).strip().upper()
        if not (1_000_000 <= code <= 9_999_999) or not uf or not row["nome"].strip():
            raise CommandError(f"Linha {line}: código IBGE, nome ou UF inválidos.")
        if not (LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1]):
            raise CommandError(f"Linha {line}: coordenada fora do Brasil ({lat}, {lon}).")
        return {
            "ibge_code": code,
            "name": row["nome"].strip(),
            "uf": uf,
            "lat": lat,
            "lon": lon,
            "is_capital": (row.get("capital") or "").strip() in ("1", "true", "sim", "yes"),
        }

    def _check_home_and_hubs(self):
        wanted = {settings.HOME_MUNICIPALITY_IBGE, *settings.PRIORITY_HUBS_IBGE}
        found = set(
            Municipality.objects.filter(ibge_code__in=wanted).values_list("ibge_code", flat=True)
        )
        if missing := wanted - found:
            raise CommandError(
                f"Base/polos fora da carga (confira HOME_MUNICIPALITY_IBGE e PRIORITY_HUBS_IBGE): "
                f"{', '.join(map(str, sorted(missing)))}."
            )
