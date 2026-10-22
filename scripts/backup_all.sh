#!/usr/bin/env bash
# Sauvegarde complete : config ClickHouse, DDL, donnees, projet, infra.
set -euo pipefail

STAMP="$(date +%Y%m%d-%H%M)"
DEST="${1:-/mnt/disks/data/backups/brixhub-$STAMP}"
REPO="/mnt/disks/data/search_app/brixhub"
CH="clickhouse-client"

if command -v zstd >/dev/null 2>&1; then COMP="zstd"; EXT="zst"; else COMP="gzip"; EXT="gz"; fi
echo "$COMP" > /tmp/.bx_comp

mkdir -p "$DEST"/{clickhouse/ddl,clickhouse/data,clickhouse/config,project,infra}
echo "$COMP" > "$DEST/COMPRESSOR"

echo "== 1/6 config ClickHouse"
for f in /etc/clickhouse-server/config.xml /etc/clickhouse-server/users.xml; do
  [ -f "$f" ] && cp -a "$f" "$DEST/clickhouse/config/" || true
done
for d in config.d users.d; do
  [ -d "/etc/clickhouse-server/$d" ] && cp -a "/etc/clickhouse-server/$d" "$DEST/clickhouse/config/" || true
done
[ -d /etc/clickhouse-client ] && cp -a /etc/clickhouse-client "$DEST/clickhouse/config/" || true
cp -a /etc/hosts "$DEST/clickhouse/config/hosts" || true
cp -a /etc/fstab "$DEST/clickhouse/config/fstab" || true

echo "== 2/6 DDL de toutes les bases"
: > "$DEST/clickhouse/ddl/schema.sql"
DBS="$($CH -q "SELECT name FROM system.databases WHERE name NOT IN ('system','INFORMATION_SCHEMA','information_schema')")"
for db in $DBS; do
  printf '\n-- ===== base %s =====\n' "$db" >> "$DEST/clickhouse/ddl/schema.sql"
  printf '%s;\n' "$($CH -q "SHOW CREATE DATABASE \`$db\`")" >> "$DEST/clickhouse/ddl/schema.sql"
  for t in $($CH -q "SELECT name FROM system.tables WHERE database='$db' AND engine NOT IN ('View','MaterializedView')"); do
    printf '%s;\n' "$($CH -q "SHOW CREATE TABLE \`$db\`.\`$t\`")" >> "$DEST/clickhouse/ddl/schema.sql"
  done
  for v in $($CH -q "SELECT name FROM system.tables WHERE database='$db' AND engine IN ('View','MaterializedView')"); do
    printf '%s;\n' "$($CH -q "SHOW CREATE TABLE \`$db\`.\`$v\`")" >> "$DEST/clickhouse/ddl/schema.sql"
  done
done

echo "== 3/6 donnees (peut prendre du temps)"
: > "$DEST/clickhouse/data/tables.txt"
for db in $DBS; do
  mkdir -p "$DEST/clickhouse/data/$db"
  for t in $($CH -q "SELECT name FROM system.tables WHERE database='$db' AND engine NOT IN ('View','MaterializedView')"); do
    printf '%s.%s\n' "$db" "$t" >> "$DEST/clickhouse/data/tables.txt"
    if [ "$COMP" = "zstd" ]; then
      $CH -q "SELECT * FROM \`$db\`.\`$t\` FORMAT Native" | zstd -q -3 -o "$DEST/clickhouse/data/$db/$t.native.$EXT"
    else
      $CH -q "SELECT * FROM \`$db\`.\`$t\` FORMAT Native" | gzip -3 > "$DEST/clickhouse/data/$db/$t.native.$EXT"
    fi
    printf '  %-45s %s\n' "$db.$t" "$(du -h "$DEST/clickhouse/data/$db/$t.native.$EXT" | cut -f1)"
  done
done

echo "== 4/6 projet"
tar -C "$(dirname "$REPO")" \
    --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='node_modules' \
    -czf "$DEST/project/brixhub-src.tar.gz" "$(basename "$REPO")"

echo "== 5/6 infra"
cp -a /etc/systemd/system/clickhouse-server.service "$DEST/infra/" 2>/dev/null || true
systemctl list-unit-files --type=service --no-pager > "$DEST/infra/services.txt" 2>/dev/null || true
crontab -l > "$DEST/infra/crontab.txt" 2>/dev/null || true
docker ps --format '{{.Names}}\t{{.Image}}\t{{.Ports}}' > "$DEST/infra/docker-ps.txt" 2>/dev/null || true
docker compose -f "$REPO/docker-compose.yml" config > "$DEST/infra/compose-resolved.yml" 2>/dev/null || true
iptables-save > "$DEST/infra/iptables.rules" 2>/dev/null || true

echo "== 6/6 manifeste"
( cd "$DEST" && find . -type f ! -name 'MANIFEST.sha256' -print0 | sort -z | xargs -0 sha256sum ) > "$DEST/MANIFEST.sha256"
{
  echo "BrixHub backup $STAMP"
  echo "compresseur: $COMP"
  echo "taille projet+infra: $(du -sh "$DEST/project" "$DEST/infra" | awk '{print $1}' | paste -sd' ')"
  echo "taille donnees: $(du -sh "$DEST/clickhouse" | cut -f1)"
  echo "taille totale: $(du -sh "$DEST" | cut -f1)"
} > "$DEST/SUMMARY.txt"
cat "$DEST/SUMMARY.txt"
echo
echo "Sauvegarde prete : $DEST"
