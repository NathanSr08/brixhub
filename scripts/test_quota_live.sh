#!/usr/bin/env bash
# Non-regression : le quota invite doit suivre la base a chaud, sans purge.
set -u
cd "$(dirname "$0")/.." || exit 1
set -a; . ./.env 2>/dev/null; set +a
BASE="${BASE:-https://brixhub.uned.live}"
HDR="X-Admin-Token: ${ADMIN_TOKEN:?ADMIN_TOKEN manquant}"
CT="Content-Type: application/json"
RID=$(docker ps -qf name=redis | head -1)
[ -n "$RID" ] || { echo "conteneur redis introuvable"; exit 2; }

wipe(){ docker exec -i "$RID" redis-cli --scan --pattern '*quota*' \
        | while read -r k; do docker exec -i "$RID" redis-cli DEL "$k" >/dev/null; done; }
setv(){ curl -s -X PATCH "$BASE/admin/api/settings" -H "$HDR" -H "$CT" \
        -d "{\"values\":{\"guest_daily_quota\":\"$1\"}}" >/dev/null; }

CUR=$(curl -s "$BASE/admin/api/settings" -H "$HDR" \
      | grep -oE '"guest_daily_quota":"[0-9]+"' | head -1 | grep -oE '[0-9]+')
J=$(mktemp)
probe(){ curl -s -o /dev/null -w "%{http_code}" -b "$J" -c "$J" \
         "$BASE/api/search?nom=Martin&prenom=Paul"; sleep 0.4; }
cleanup(){ rm -f "$J"; [ -n "${CUR:-}" ] && { setv "$CUR"; wipe; echo "quota restaure a $CUR"; }; }
trap cleanup EXIT

fail=0
run(){
  local q="$1"
  local ok="$2"
  local n=$((ok+2))
  local out="" codes
  wipe; setv "$q"
  for i in $(seq 1 "$n"); do out+="$(probe) "; done
  codes=($out)
  echo "quota=$q -> $out (attendu: ${ok}x200 puis 429)"
  for i in $(seq 0 $((ok-1))); do [ "${codes[$i]}" = "200" ] || fail=1; done
  [ "${codes[$ok]}" = "429" ] || fail=1
}
run 2 2
run 5 5
[ $fail -eq 0 ] && echo "OK : le quota suit la base" || echo "ECHEC"
exit $fail
