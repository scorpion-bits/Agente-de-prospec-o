#!/usr/bin/env bash
# Restaura um backup .dump.age em um banco ALVO (use o radar-dev para testar, nunca o prod às cegas).
# Uso: scripts/restore_backup.sh ARQUIVO.dump.age ARQUIVO_CHAVE_PRIVADA TARGET_DATABASE_URL
# O schema alvo é recriado (DROP SCHEMA ... CASCADE): por isso a confirmação RESTORE_CONFIRM=sim.
set -euo pipefail

FILE="${1:?Informe o arquivo .dump.age}"
KEY="${2:?Informe o arquivo da chave privada age}"
TARGET="${3:?Informe a URL do banco alvo}"
SCHEMA="${DB_SCHEMA:-radar}"

if [ "${RESTORE_CONFIRM:-}" != "sim" ]; then
  echo "Isto apaga o schema '$SCHEMA' no banco alvo. Rode de novo com RESTORE_CONFIRM=sim." >&2
  exit 1
fi

psql "$TARGET" -v ON_ERROR_STOP=1 -c "DROP SCHEMA IF EXISTS \"$SCHEMA\" CASCADE;"
age -d -i "$KEY" "$FILE" | pg_restore --dbname="$TARGET" --no-owner --no-privileges --exit-on-error
echo "Restaurado em '$SCHEMA'. Confira: make migrate (nada pendente) e o admin."
