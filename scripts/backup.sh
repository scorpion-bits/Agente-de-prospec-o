#!/usr/bin/env bash
# Backup do schema do app: pg_dump (formato custom, já comprimido) criptografado com age.
# Uso: scripts/backup.sh [pasta-de-saida]   (padrão: data/backups)
# Precisa de DATABASE_URL e BACKUP_AGE_PUBLIC_KEY no ambiente (ou no .env, lido se existir).
# Só a chave PÚBLICA fica aqui; a privada fica com o titular (ADR-014: o repositório é público).
set -euo pipefail

cd "$(dirname "$0")/.."
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

: "${DATABASE_URL:?Defina DATABASE_URL}"
: "${BACKUP_AGE_PUBLIC_KEY:?Defina BACKUP_AGE_PUBLIC_KEY (chave pública age, começa com age1)}"
SCHEMA="${DB_SCHEMA:-radar}"
OUT="${1:-data/backups}"
mkdir -p "$OUT"
FILE="$OUT/radar-$(date -u +%Y%m%dT%H%M%SZ).dump.age"

# Nada de dump em claro no disco: o pg_dump vai direto para o age.
pg_dump --dbname="$DATABASE_URL" --schema="$SCHEMA" --format=custom --no-owner --no-privileges \
  | age -r "$BACKUP_AGE_PUBLIC_KEY" -o "$FILE"

test -s "$FILE" || { echo "Backup vazio: $FILE" >&2; rm -f "$FILE"; exit 1; }
echo "Backup criado: $FILE ($(wc -c <"$FILE") bytes)"
