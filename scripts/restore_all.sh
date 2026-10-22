#!/usr/bin/env bash
# Restaure une sauvegarde produite par backup_all.sh sur une machine vierge.
set -euo pipefail

SRC="${1:?usage: restore_all.sh <dossier_backup>}"
REPO="/mnt/disks/data/search_app/brixhub"
CH="clickhouse-client"
COMP="$(cat "$SRC/COMPRESSOR" 2>/dev/null || echo zstd)"
case "$COMP" in zstd) DEC="zstd -dc"; EXT="zst";; *) DEC="gzip -dc"; EXT="gz";; esac

echo "== 1/6 config ClickHouse"
mkdir -p /etc/clickhouse-server
cp -a "$SRC/clickhouse/config/config.xml" /etc/clickhouse-server/ 2>/dev/null || true
for d in config.d users.d; do
  [ -d "$SRC/clickhouse/config/$d" ] && cp -a "$SRC/clickhouse/config/$d/." "/etc/clickhouse-server/$d/" || true
done
[ -d "$SRC/clickhouse/config/clickhouse-client" ] && cp -a "$SRC/clickhouse/config/clickhouse-client" /etc/ || true
grep -q 'host.docker.internal' /etc/hosts || echo '127.0.0.1 host.docker.internal' >> /etc/hosts

echo "== 2/6 service ClickHouse"
systemctl enable --now clickhouse-server
for i in $(seq 1 60); do $CH -q "SELECT 1" >/dev/null 2>&1 && break; sleep 2; done
$CH -q "SELECT version()"

echo "== 3/6 schema"
$CH --multiquery < "$SRC/clickhouse/ddl/schema.sql"

echo "== 4/6 donnees"
while read -r tbl; do
  [ -z "$tbl" ] && continue
  db="${tbl%%.*}"; t="${tbl##*.}"
  printf '  %s.%s ' "$db" "$t"
  $DEC "$SRC/clickhouse/data/$db/$t.native.$EXT" | $CH -q "INSERT INTO \`$db\`.\`$t\` FORMAT Native"
  echo "ok"
done < "$SRC/clickhouse/data/tables.txt"

echo "== 5/6 projet"
mkdir -p "$(dirname "$REPO")"
tar -xzf "$SRC/project/brixhub-src.tar.gz" -C "$(dirname "$REPO")"

echo "== 6/6 conteneurs"
cd "$REPO" && docker compose up -d

echo
echo "== verification"
$CH -q "SELECT database, formatReadableSize(sum(bytes_on_disk)) FROM system.parts WHERE active GROUP BY database"
docker compose ps
