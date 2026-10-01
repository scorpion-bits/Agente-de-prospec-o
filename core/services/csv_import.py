"""Leitura de CSVs de importação (sementes e dados privados) com erros que dizem a linha."""

import csv
from pathlib import Path

from django.core.management.base import CommandError


def read_rows(path: Path, required: tuple[str, ...]):
    """Lista de `(número da linha, dict)`; colunas sem valor viram `""` e espaços são aparados."""
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            missing = [col for col in required if col not in (reader.fieldnames or [])]
            if missing:
                raise CommandError(f"{path}: faltam as colunas {', '.join(missing)}.")
            return [
                (number, {k: (v or "").strip() for k, v in row.items() if k})
                for number, row in enumerate(reader, start=2)
                if any((v or "").strip() for v in row.values())
            ]
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise CommandError(f"Não foi possível ler {path}: {exc}") from exc


def choice_value(choices, value: str, field: str, line: int, *, blank_ok: bool = False) -> str:
    """Valida `value` contra `TextChoices`; aceita o valor ou o rótulo (sem diferenciar caixa)."""
    if not value and blank_ok:
        return ""
    for key, label in choices.choices:
        if value.casefold() in (key.casefold(), str(label).casefold()):
            return key
    valid = ", ".join(choices.values)
    raise CommandError(f"Linha {line}: {field} {value!r} inválido (use: {valid}).")
