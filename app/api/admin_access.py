"""Gestion des regles d'acces depuis l'admin."""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.api.admin import require_admin_auth
from app.core import access
from app.db.clickhouse import get_ch
from app.repositories import audit_repo

router = APIRouter(prefix="/admin", tags=["admin-access"])
TABLE = "sports_db.access_rules"
COLS = ["scope", "ident", "is_blocked", "allow_routes", "deny_routes", "note", "expires_at", "updated_at"]


class ReglePayload(BaseModel):
    scope: str
    ident: str
    is_blocked: int = 0
    allow_routes: str = ""
    deny_routes: str = ""
    note: str = ""
    expires_at: str | None = None


class TestPayload(BaseModel):
    ip: str | None = None
    key_id: str | None = None
    user_id: str | None = None
    path: str = "/"


def _ip(request: Request) -> str:
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "")


def _lister():
    lignes = get_ch().query(
        "SELECT scope, ident, is_blocked, allow_routes, deny_routes, note, expires_at, updated_at "
        "FROM %s FINAL ORDER BY scope, ident" % TABLE).result_rows
    out = []
    for l in lignes:
        d = dict(zip(COLS, l))
        for k in ("expires_at", "updated_at"):
            d[k] = d[k].isoformat(sep=" ", timespec="seconds") if d.get(k) else None
        out.append(d)
    return out


def _enregistrer(p: ReglePayload):
    exp = None
    if p.expires_at:
        try:
            exp = datetime.fromisoformat(p.expires_at.replace("T", " ")[:19])
        except Exception:
            raise HTTPException(status_code=400, detail="EXPIRES_AT_INVALIDE")
    if p.scope not in ("ip", "key", "user"):
        raise HTTPException(status_code=400, detail="SCOPE_INVALIDE")
    get_ch().insert(TABLE, [[p.scope, p.ident, int(p.is_blocked), p.allow_routes,
                             p.deny_routes, p.note, exp, datetime.utcnow()]],
                    column_names=COLS)


@router.get("/api/access-rules", dependencies=[Depends(require_admin_auth)])
async def liste_regles():
    return {"items": await run_in_threadpool(_lister)}


@router.post("/api/access-rules", dependencies=[Depends(require_admin_auth)])
async def enregistrer_regle(payload: ReglePayload, request: Request):
    await run_in_threadpool(_enregistrer, payload)
    access.invalidate()
    audit_repo.log_admin_action("admin", "access_rule_set", payload.scope, payload.ident,
                                _ip(request), json.dumps(payload.dict())[:500])
    return {"status": "ok"}


@router.delete("/api/access-rules/{scope}/{ident}", dependencies=[Depends(require_admin_auth)])
async def supprimer_regle(scope: str, ident: str, request: Request):
    sql = ("ALTER TABLE {t} DELETE WHERE scope = %(s)s AND ident = %(i)s "
           "SETTINGS mutations_sync=1").format(t=TABLE)
    await run_in_threadpool(get_ch().command, sql, {"s": scope, "i": ident})
    access.invalidate()
    audit_repo.log_admin_action("admin", "access_rule_del", scope, ident, _ip(request))
    return {"status": "ok"}


@router.post("/api/access-rules/test", dependencies=[Depends(require_admin_auth)])
async def tester_regle(payload: TestPayload):
    regles = await run_in_threadpool(access._regles)
    trouvees = []
    for portee, ident in (("key", payload.key_id), ("user", payload.user_id), ("ip", payload.ip)):
        if not ident:
            continue
        r = regles.get((portee, ident))
        if r and not access._perimee(r):
            trouvees.append((portee, ident, r))
    verdict, raison = "AUTORISE", ""
    for portee, ident, r in trouvees:
        if r["bloque"]:
            verdict, raison = "BLOQUE", "%s_BLOCKED" % portee.upper(); break
    if verdict == "AUTORISE":
        for portee, ident, r in trouvees:
            autorise, refuse = access._motifs(r["autorise"]), access._motifs(r["refuse"])
            if refuse and any(access._correspond(m, payload.path) for m in refuse):
                verdict, raison = "BLOQUE", "ROUTE_DENIED_%s" % portee.upper(); break
            if autorise and not any(access._correspond(m, payload.path) for m in autorise):
                verdict, raison = "BLOQUE", "ROUTE_NOT_ALLOWED_%s" % portee.upper(); break
    return {"verdict": verdict, "raison": raison, "regles_appliquees": [p for p, _, _ in trouvees]}

@router.get("/api/access-rules/choices", dependencies=[Depends(require_admin_auth)])
async def choix_regles():
    """Valeurs reelles pour les listes : IP, cles, utilisateurs, delais."""
    def _build():
        ips, cles, users = [], [], []
        try:
            ips = [str(r[0]) for r in get_ch().query(
                "SELECT ip, count() c FROM auth_db.api_logs "
                "WHERE ip != '' AND timestamp > now() - INTERVAL 7 DAY "
                "GROUP BY ip ORDER BY c DESC LIMIT 60").result_rows]
        except Exception:
            pass
        try:
            cles = [{"id": str(r[0]), "label": "%s (%s)" % (r[1] or "", r[2] or "")}
                    for r in get_ch().query(
                        "SELECT key_id, label, preview FROM sports_db.api_keys FINAL "
                        "WHERE is_active = 1 ORDER BY label").result_rows]
        except Exception:
            pass
        try:
            users = [{"id": str(r[0]), "label": "%s" % (r[1] or r[0])}
                     for r in get_ch().query(
                         "SELECT user_id, email FROM sports_db.users FINAL ORDER BY email").result_rows]
        except Exception:
            pass
        return {"ips": ips, "keys": cles, "users": users,
                "expirations": ["jamais", "1 heure", "24 heures", "7 jours", "30 jours"]}
    return await run_in_threadpool(_build)


@router.get("/api/access-rules/routes", dependencies=[Depends(require_admin_auth)])
async def routes_disponibles(request: Request):
    """Liste les vraies routes de l'app, groupees web / API / doc."""
    exclure = ("/admin", "/static", "/openapi", "/docs", "/redoc", "/favicon")
    pages = ("/", "/cgu", "/rgpd", "/reset-password", "/maintenance")
    web, api, doc = [], [], []

    for r in request.app.routes:
        chemin = getattr(r, "path", None)
        if not chemin or chemin.startswith(exclure) or chemin in pages:
            continue
        if chemin.startswith("/api/"):
            web.append(chemin)
        elif chemin.startswith("/v1/"):
            api.append(chemin)
        elif chemin == "/api-docs":
            doc.append(chemin)

    web, api = sorted(set(web)), sorted(set(api))
    paires = {}
    for chemin in web:
        jumeau = "/v1/" + chemin[len("/api/"):]
        if jumeau in api:
            paires[chemin] = jumeau
            paires[jumeau] = chemin

    groupes = [g for g in (
        {"nom": "Application web  (le visiteur sur le site)", "routes": web},
        {"nom": "API publique  (cle API, /v1)", "routes": api},
        {"nom": "Documentation", "routes": sorted(set(doc))},
    ) if g["routes"]]
    return {"groupes": groupes, "paires": paires}
