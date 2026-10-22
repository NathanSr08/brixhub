cd /mnt/disks/data/search_app/brixhub || exit 1
mkdir -p scripts
cp /root/brixhub-tools/backup_all.sh /root/brixhub-tools/restore_all.sh /root/brixhub-tools/verify_backup.sh scripts/ 2>/dev/null || true

cat > scripts/deploy.sh <<'EOF'
#!/usr/bin/env bash
# ============================================================================
#  BrixHub - deploiement complet depuis un backup
#  usage : bash scripts/deploy.sh /chemin/brixhub-YYYYMMDD-HHMM.tar.zst [--fresh]
#  env   : BX_DATA_DIR (defaut /mnt/disks/data)  BX_SKIP_CH_INSTALL=1
# ============================================================================
set -euo pipefail

ARCHIVE="${1:-}"
FRESH="${2:-}"
DATA_DIR="${BX_DATA_DIR:-/mnt/disks/data}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CH="clickhouse-client"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

log()  { printf '\n\033[1;34m== %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m  ! %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m  x %s\033[0m\n' "$*" >&2; exit 1; }

[ -n "$ARCHIVE" ] || die "usage: bash scripts/deploy.sh <backup.tar.zst|dossier> [--fresh]"
[ -e "$ARCHIVE" ] || die "introuvable: $ARCHIVE"

# ---------------------------------------------------------------- prerequis
log "1/8 prerequis"
for c in docker tar; do command -v "$c" >/dev/null || die "$c manquant"; done
docker compose version >/dev/null 2>&1 || die "docker compose v2 manquant"
command -v zstd >/dev/null || { apt-get update -qq && apt-get install -y -qq zstd; }
echo "  docker $(docker --version | awk '{print $3}') | zstd ok"

# ---------------------------------------------------------------- extraction
log "2/8 extraction de la sauvegarde"
case "$ARCHIVE" in
  *.tar.zst) tar -C "$WORK" -xf "$ARCHIVE" ;;
  *.tar.gz)  tar -C "$WORK" -xzf "$ARCHIVE" ;;
  *)         [ -d "$ARCHIVE" ] || die "format non reconnu"; cp -a "$ARCHIVE" "$WORK/bk" ;;
esac
BK="$(find "$WORK" -maxdepth 2 -name COMPRESSOR -printf '%h\n' | head -1)"
[ -n "$BK" ] || die "sauvegarde invalide (pas de fichier COMPRESSOR)"
echo "  backup: $BK"
if [ -f "$ARCHIVE.sha256" ] || [ -f "$BK/MANIFEST.sha256" ]; then
  ( cd "$BK" && sha256sum -c MANIFEST.sha256 --quiet ) && echo "  checksums OK"
fi
COMP="$(cat "$BK/COMPRESSOR")"
case "$COMP" in zstd) DEC="zstd -dc"; EXT="zst";; *) DEC="gzip -dc"; EXT="gz";; esac

# ---------------------------------------------------------------- clickhouse
log "3/8 ClickHouse"
if ! command -v "$CH" >/dev/null; then
  [ "${BX_SKIP_CH_INSTALL:-0}" = "1" ] && die "clickhouse-client absent et install desactivee"
  echo "  installation du depot officiel..."
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq apt-transport-https ca-certificates curl gnupg
  curl -fsSL 'https://packages.clickhouse.com/rpm/lts/repodata/repomd.xml.key' \
    | gpg --dearmor -o /usr/share/keyrings/clickhouse-keyring.gpg
  echo "deb [signed-by=/usr/share/keyrings/clickhouse-keyring.gpg] https://packages.clickhouse.com/deb stable main" \
    > /etc/apt/sources.list.d/clickhouse.list
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq clickhouse-server clickhouse-client
fi
"$CH" --version

systemctl stop clickhouse-server 2>/dev/null || true

mkdir -p /etc/clickhouse-server/config.d /etc/clickhouse-server/users.d
[ -d /etc/clickhouse-server/config.d ] && cp -a /etc/clickhouse-server/config.d "/etc/clickhouse-server/config.d.pre-deploy.$(date +%s)" 2>/dev/null || true
for f in config.xml users.xml; do
  [ -f "$BK/clickhouse/config/$f" ] && cp -a "$BK/clickhouse/config/$f" /etc/clickhouse-server/ || true
done
for d in config.d users.d; do
  [ -d "$BK/clickhouse/config/$d" ] && cp -a "$BK/clickhouse/config/$d/." "/etc/clickhouse-server/$d/" || true
done

mkdir -p "$DATA_DIR/clickhouse_data" "$DATA_DIR/clickhouse_logs"
chown -R clickhouse:clickhouse "$DATA_DIR/clickhouse_data" "$DATA_DIR/clickhouse_logs" 2>/dev/null || true
# reecriture des chemins vers BX_DATA_DIR
grep -rl 'clickhouse_data\|clickhouse_logs' /etc/clickhouse-server/ 2>/dev/null | while read -r f; do
  sed -i "s#/mnt/disks/data/clickhouse_data#$DATA_DIR/clickhouse_data#g; s#/mnt/disks/data/clickhouse_logs#$DATA_DIR/clickhouse_logs#g" "$f"
done
grep -q 'host.docker.internal' /etc/hosts || echo '127.0.0.1 host.docker.internal' >> /etc/hosts

systemctl enable --now clickhouse-server
for i in $(seq 1 60); do "$CH" -q "SELECT 1" >/dev/null 2>&1 && break; sleep 2; done
"$CH" -q "SELECT 'clickhouse pret', version()"

# ---------------------------------------------------------------- schema
log "4/8 schema"
sed -E 's/^CREATE DATABASE /CREATE DATABASE IF NOT EXISTS /;
        s/^CREATE TABLE /CREATE TABLE IF NOT EXISTS /;
        s/^CREATE VIEW /CREATE VIEW IF NOT EXISTS /;
        s/^CREATE MATERIALIZED VIEW /CREATE MATERIALIZED VIEW IF NOT EXISTS /' \
    "$BK/clickhouse/ddl/schema.sql" > "$WORK/schema.sql"
"$CH" --multiquery < "$WORK/schema.sql"
"$CH" -q "SELECT database, count() AS tables FROM system.tables
          WHERE database NOT IN ('system','INFORMATION_SCHEMA','information_schema')
          GROUP BY database"

# ---------------------------------------------------------------- donnees
log "5/8 donnees"
if [ "$FRESH" = "--fresh" ]; then
  while read -r t; do
    [ -z "$t" ] && continue
    "$CH" -q "TRUNCATE TABLE \`${t%%.*}\`.\`${t##*.}\`" && echo "  vide: $t"
  done < "$BK/clickhouse/data/tables.txt"
fi
while read -r t; do
  [ -z "$t" ] && continue
  db="${t%%.*}"; tb="${t##*.}"; f="$BK/clickhouse/data/$db/$tb.native.$EXT"
  [ -f "$f" ] || { warn "fichier absent: $t"; continue; }
  printf '  %-42s ' "$t"
  $DEC "$f" | "$CH" -q "INSERT INTO \`$db\`.\`$tb\` FORMAT Native"
  printf '%s lignes\n' "$("$CH" -q "SELECT count() FROM \`$db\`.\`$tb\`")"
done < "$BK/clickhouse/data/tables.txt"

# ---------------------------------------------------------------- projet
log "6/8 projet"
if [ ! -f "$REPO_DIR/.env" ]; then
  if [ -f "$WORK/envfile" ]; then cp "$WORK/envfile" "$REPO_DIR/.env"; else
    tar -xzf "$BK/project/brixhub-src.tar.gz" -C "$WORK" 2>/dev/null || true
    SRC="$(find "$WORK" -maxdepth 2 -name '.env' | head -1)"
    [ -n "$SRC" ] && cp "$SRC" "$REPO_DIR/.env" && echo "  .env restaure" || warn ".env absent du backup"
  fi
else
  echo "  .env deja present, conserve"
fi
[ -f "$REPO_DIR/.env" ] && chmod 600 "$REPO_DIR/.env" || true

# ---------------------------------------------------------------- stack
log "7/8 conteneurs"
cd "$REPO_DIR"
docker compose build
docker compose up -d
sleep 8
docker compose ps

# ---------------------------------------------------------------- controle
log "8/8 controle"
"$CH" -q "SELECT database, formatReadableSize(sum(bytes_on_disk)) AS taille, sum(rows) AS lignes
          FROM system.parts WHERE active
          GROUP BY database ORDER BY sum(bytes_on_disk) DESC"
for i in $(seq 1 30); do
  code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/ 2>/dev/null || echo 000)"
  [ "$code" != "000" ] && break
  sleep 2
done
echo "  app locale -> $code"
cat <<TXT

Termine. A verifier ensuite :
  - DNS du domaine vers cette IP
  - certificat TLS / reverse proxy
  - secrets dans $REPO_DIR/.env (ADMIN_TOKEN, etc.)
  - ports ClickHouse 8123/9000 a restreindre
TXT
EOF
chmod +x scripts/deploy.sh
bash -n scripts/deploy.sh && echo "syntaxe deploy.sh OK"
