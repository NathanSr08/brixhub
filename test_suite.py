import sys, time, json, urllib.request, urllib.error, asyncio
from app.core.config import get_settings
from app.services.key_service import KeyService
from app.db.clickhouse import init_clients, close_clients

BASE_URL = "http://127.0.0.1:80"
ADMIN_TOKEN = get_settings().admin_token

def http_req(url, method="GET", headers=None, data=None):
    headers = headers or {}
    body = json.dumps(data).encode("utf-8") if data is not None else None
    if data is not None and "Content-Type" not in headers:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            b = r.read().decode("utf-8")
            try: p = json.loads(b)
            except Exception: p = b
            return r.status, p, dict(r.headers)
    except urllib.error.HTTPError as e:
        b = e.read().decode("utf-8")
        try: p = json.loads(b)
        except Exception: p = b
        return e.code, p, dict(e.headers)
    except Exception as e:
        return 0, str(e), {}

def check(name, ok, code, expected, body, url="", m="GET"): 
    tag = "\033[92m[ PASS ]\033[0m" if ok else "\033[91m[ FAIL ]\033[0m"
    print(f"{tag} {name} (Status: {code})")
    if not ok:
        print(f"\n--- ERREUR DIAGNOSTIC ---\nRequete: {m} {url}\nStatus recu: {code} (attendu: {expected})\nReponse: {body}\n------------------------\n")
        sys.exit(1)

print("\n=== LANCEMENT DE LA SUITE DE TESTS BRIXHUB ===\n")

# 1. Attente serveur
for _ in range(15):
    c, _, _ = http_req(f"{BASE_URL}/api/stats")
    if c == 200: break
    time.sleep(1)
else:
    print("[FAIL] Serveur injoignable sur le port 80")
    sys.exit(1)

# 2. Legacy
c, d, _ = http_req(f"{BASE_URL}/")
check("Front Web (index.html)", c == 200, c, 200, d, "/")

c, d, _ = http_req(f"{BASE_URL}/api/stats")
check("Legacy /api/stats", c == 200 and "total" in d, c, 200, d, "/api/stats")

c, d, _ = http_req(f"{BASE_URL}/api/sources")
check("Legacy /api/sources", c == 200 and isinstance(d, list), c, 200, d, "/api/sources")

c, d, _ = http_req(f"{BASE_URL}/api/search?nom=DUPONT&limit=2")
check("Legacy /api/search", c == 200 and isinstance(d, list), c, 200, d, "/api/search")

# 3. Securite v1
c, d, _ = http_req(f"{BASE_URL}/v1/search?nom=DUPONT")
check("Securite v1: Rejet sans header", c == 401, c, 401, d, "/v1/search")

c, d, _ = http_req(f"{BASE_URL}/v1/search?nom=DUPONT", headers={"Authorization": "Bearer faux"})
check("Securite v1: Rejet fausse cle", c == 401, c, 401, d, "/v1/search")

# 4. Creation cle interne
async def gen_key():
    await init_clients()
    res = await KeyService().create("Runner", "ci@test.local", "pro")
    await close_clients()
    return res

key_info = asyncio.run(gen_key())
raw_k = key_info["key"]
check("Gestion Cles: Creation directe", bool(raw_k), 200, 200, key_info)
hdr_auth = {"Authorization": f"Bearer {raw_k}"}

# 5. Recherche v1 & Quota
c, d, h = http_req(f"{BASE_URL}/v1/search?nom=DUPONT&limit=5", headers=hdr_auth)
check("v1: Recherche Bearer token", c == 200 and isinstance(d, list), c, 200, d, "/v1/search")
q_lim = h.get("x-ratelimit-limit") or h.get("X-RateLimit-Limit")
check("v1: Headers Quota Redis", bool(q_lim), c, 200, h, "/v1/search")

# 6. Admin v1: POST /v1/keys
adm_hdr = {"X-Admin-Token": ADMIN_TOKEN}
c, sub_d, _ = http_req(f"{BASE_URL}/v1/keys", method="POST", headers=adm_hdr, data={"label": "Sub", "owner_email": "s@t.fr", "plan": "free"})
check("Admin v1: POST /v1/keys", c == 200, c, 200, sub_d, "/v1/keys", "POST")

sub_k = sub_d["key"]
sub_id = sub_d["key_id"]

# 7. /v1/keys/me
c, d, _ = http_req(f"{BASE_URL}/v1/keys/me", headers={"Authorization": f"Bearer {sub_k}"})
check("v1: /v1/keys/me", c == 200 and "requetes_aujourdhui" in d, c, 200, d, "/v1/keys/me")

# 8. DELETE /v1/keys/{id}
c, d, _ = http_req(f"{BASE_URL}/v1/keys/{sub_id}", method="DELETE", headers=adm_hdr)
check("Admin v1: DELETE /v1/keys/{id}", c == 200, c, 200, d, f"/v1/keys/{sub_id}", "DELETE")

time.sleep(1)

# 9. Verification post-revocation
c, d, _ = http_req(f"{BASE_URL}/v1/search?nom=DUPONT", headers={"Authorization": f"Bearer {sub_k}"})
check("Securite v1: Rejet apres revocation", c == 401, c, 401, d, "/v1/search")

print("\n=========================================")
print("  TOUS LES 14 TESTS SONT VALIDES !")
print("=========================================\n")
