#!/usr/bin/env bash
# Verifie l'integrite d'une sauvegarde (checksums + lisibilite des archives).
set -euo pipefail
SRC="${1:?usage: verify_backup.sh <dossier_backup>}"
cd "$SRC"
echo "== checksums"
sha256sum -c MANIFEST.sha256 --quiet && echo "checksums OK"
echo "== lisibilite des flux compresses"
COMP="$(cat COMPRESSOR 2>/dev/null || echo zstd)"
while read -r tbl; do
  [ -z "$tbl" ] && continue
  db="${tbl%%.*}"; t="${tbl##*.}"
  f="clickhouse/data/$db/$t.native.$([ "$COMP" = zstd ] && echo zst || echo gz)"
  [ -f "$f" ] && printf '  %-45s %s\n' "$tbl" "$([ "$COMP" = zstd ] && zstd -t "$f" 2>&1 && echo OK || echo KO)"
done < clickhouse/data/tables.txt
echo "== projet"
tar -tzf project/brixhub-src.tar.gz >/dev/null && echo "archive projet OK"
