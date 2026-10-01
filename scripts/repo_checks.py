"""Verificações baratas do repositório (rodam em `make check` e no CI).

1. Limites de tamanho de CLAUDE.md e STATUS.md (ADR-008, docs/operations/claude-md-maintenance.md).
2. Dados sensíveis em arquivos versionados (ADR-014: o repositório é público).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# arquivo -> (alerta, limite rígido) em linhas
LINE_LIMITS = {
    "CLAUDE.md": (120, 150),
    "docs/plan/STATUS.md": (100, 120),
}

SENSITIVE_PATTERNS = {
    "CNPJ": re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"),
    "CPF": re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"),
    "e-mail pessoal": re.compile(
        r"[\w.+-]+@(?:gmail|hotmail|outlook|yahoo|icloud)\.[a-z.]+", re.IGNORECASE
    ),
    "chave de API": re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{35})\b"),
}
SKIP_FILES = {"uv.lock"}
TEXT_SUFFIXES = {".md", ".py", ".toml", ".yml", ".yaml", ".json", ".csv", ".txt", ".example", ""}


def tracked_files(root: Path) -> list[Path]:
    """Arquivos versionados (ou a serem versionados), respeitando o .gitignore."""
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [root / line for line in out.splitlines() if line]


def check_line_limits(root: Path) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    for name, (warn, hard) in LINE_LIMITS.items():
        path = root / name
        if not path.exists():
            continue
        n = len(path.read_text(encoding="utf-8").splitlines())
        if n > hard:
            errors.append(f"{name}: {n} linhas (limite {hard}). Siga claude-md-maintenance.md.")
        elif n > warn:
            warnings.append(f"{name}: {n} linhas (alerta a partir de {warn}, limite {hard}).")
    return errors, warnings


def scan_sensitive(files: list[Path], root: Path) -> list[str]:
    findings = []
    for path in files:
        if path.name in SKIP_FILES or path.suffix not in TEXT_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in SENSITIVE_PATTERNS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"{path.relative_to(root)}:{line}: possível {label} (ADR-014)")
    return findings


def main() -> int:
    errors, warnings = check_line_limits(ROOT)
    errors += scan_sensitive(tracked_files(ROOT), ROOT)
    for w in warnings:
        print(f"AVISO  {w}")
    for e in errors:
        print(f"ERRO   {e}")
    if not errors:
        print("repo_checks: OK")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
