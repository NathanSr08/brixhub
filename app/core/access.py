"""Regles d'acces : blocage d'IP / cle / utilisateur et perimetre par route."""
from __future__ import annotations

import time
from datetime import datetime

from fastapi import HTTPException

from app.core.security import hash_api_key
from app.db.clickhouse import get_ch

CACHE_TTL = 5
EXEMPTS = ("/static/", "/admin", "/favicon.ico", "/robots.txt")

_cache = {"rules": None, "ts": 0.0}


def invalidate() -> None:
    _cache["ts"] = 0.0
    _cache["rules"] = None


def _regles() -> dict:
    if _cache["rules"] is not None and (time.monotonic() - _cache["ts"]) < CACHE_TTL:
        return _cache["rules"]
    trouvees = {}
    try:
        lignes = get_ch().query(
            "SELECT scope, ident, is_blocked, allow_routes, deny_routes, note, expires_at "
            "FROM sports_db.access_rules FINAL").result_rows
        for l in lignes:
            trouvees[(str(l[0]), str(l[1]))] = {
                "bloque": int(l[2] or 0),
                "autorise": str(l[3] or ""),
                "refuse": str(l[4] or ""),
                "note": str(l[5] or ""),
                "expire": l[6],
            }
    except Exception:
        pass
    _cache["rules"] = trouvees
    _cache["ts"] = time.monotonic()
    return trouvees


def _motifs(brut: str) -> list:
    return [m.strip() for m in str(brut or "").split(",") if m.strip()]


def _correspond(motif: str, chemin: str) -> bool:
    if motif.endswith("*"):
        return chemin.startswith(motif[:-1])
    return chemin == motif or chemin.startswith(motif.rstrip("/") + "/")


def _perimee(regle: dict) -> bool:
    e = regle.get("expire")
    return bool(e) and e < datetime.utcnow()


def _exempt(chemin: str) -> bool:
    return any(chemin == e or chemin.startswith(e) for e in EXEMPTS)


def ip_client(request) -> str:
    return (request.headers.get("x-real-ip")
            or (request.client.host if request.client else "") or "")


def cle_api(request) -> str | None:
    entete = request.headers.get("authorization") or ""
    if not entete.lower().startswith("bearer "):
        return None
    brut = entete[7:].strip()
    if not brut:
        return None
    try:
        h = hash_api_key(brut)
        lignes = get_ch().query(
            "SELECT key_id FROM sports_db.api_keys FINAL "
            "WHERE key_hash = %(h)s AND is_active = 1 LIMIT 1", {"h": h}).result_rows
        return str(lignes[0][0]) if lignes else None
    except Exception:
        return None


async def utilisateur(request) -> str | None:
    sid = request.headers.get("x-auth-session") or request.cookies.get("auth_session")
    if not sid:
        return None
    try:
        from app.db.clickhouse import get_redis
        brut = await get_redis().get("auth_session:%s" % sid)
        if not brut:
            return None
        return brut.decode() if isinstance(brut, bytes) else str(brut)
    except Exception:
        return None


def _applicables(ip: str, cle: str | None, user: str | None) -> list:
    regles = _regles()
    trouvees = []
    for portee, ident in (("key", cle), ("user", user), ("ip", ip)):
        if not ident:
            continue
        r = regles.get((portee, ident))
        if r and not _perimee(r):
            trouvees.append((portee, ident, r))
    return trouvees


async def check(request, chemin: str | None = None) -> None:
    """Leve 403 si l'identifiant est bloque ou si la route est hors perimetre."""
    chemin = chemin or request.url.path
    if _exempt(chemin):
        return
    trouvees = _applicables(ip_client(request), cle_api(request), await utilisateur(request))
    if not trouvees:
        return

    for portee, ident, r in trouvees:
        if r["bloque"]:
            raise HTTPException(status_code=403, detail="%s_BLOCKED" % portee.upper())

    for portee, ident, r in trouvees:
        autorise, refuse = _motifs(r["autorise"]), _motifs(r["refuse"])
        if refuse and any(_correspond(m, chemin) for m in refuse):
            raise HTTPException(status_code=403, detail="ROUTE_DENIED_%s" % portee.upper())
        if autorise and not any(_correspond(m, chemin) for m in autorise):
            raise HTTPException(status_code=403, detail="ROUTE_NOT_ALLOWED_%s" % portee.upper())
