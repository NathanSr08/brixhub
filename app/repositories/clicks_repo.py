"""Repository des clics sur les fiches resultats."""
from app.db.clickhouse import get_ch
from app.repositories.ch_admin import esc_lit

TABLE = "sports_db.profile_clicks"

COLS = ("toString(click_id) AS click_id, toString(ts) AS ts, actor_type, actor_id, "
        "actor_label, session_ref, ip, profile_ref, nom, prenom, date_naissance, "
        "ville, code_postal, mail, tel, source, criteria, rang, nb_resultats")

_KEYS = ["click_id", "ts", "actor_type", "actor_id", "actor_label", "session_ref", "ip",
         "profile_ref", "nom", "prenom", "date_naissance", "ville", "code_postal",
         "mail", "tel", "source", "criteria", "rang", "nb_resultats"]

COLUMN_NAMES = ["click_id", "actor_type", "actor_id", "actor_label", "session_ref", "ip",
                "profile_ref", "nom", "prenom", "date_naissance", "ville", "code_postal",
                "mail", "tel", "source", "criteria", "rang", "nb_resultats"]


def _row(r) -> dict:
    d = dict(zip(_KEYS, r))
    d["ts"] = str(d["ts"])
    d["rang"] = int(d["rang"])
    d["nb_resultats"] = int(d["nb_resultats"])
    d["actor_id"] = str(d["actor_id"])
    return d


def _where(f: dict) -> tuple[str, dict]:
    c, p = [], {}
    if f.get("q"):
        c.append("""(positionCaseInsensitive(nom, %(q)s) > 0
                  OR positionCaseInsensitive(prenom, %(q)s) > 0
                  OR positionCaseInsensitive(ville, %(q)s) > 0
                  OR positionCaseInsensitive(mail, %(q)s) > 0
                  OR positionCaseInsensitive(tel, %(q)s) > 0
                  OR positionCaseInsensitive(ip, %(q)s) > 0
                  OR positionCaseInsensitive(actor_id, %(q)s) > 0
                  OR positionCaseInsensitive(actor_label, %(q)s) > 0
                  OR positionCaseInsensitive(profile_ref, %(q)s) > 0)""")
        p["q"] = f["q"].strip()
    if f.get("actor_type") and f["actor_type"] != "all":
        c.append("actor_type = %(at)s"); p["at"] = f["actor_type"]
    if f.get("actor_id"):
        c.append("actor_id = %(aid)s"); p["aid"] = f["actor_id"]
    if f.get("ip"):
        c.append("ip = %(ip)s"); p["ip"] = f["ip"]
    if f.get("profile_ref"):
        c.append("profile_ref = %(pr)s"); p["pr"] = f["profile_ref"]
    if f.get("from_ts"):
        c.append("ts >= %(fts)s"); p["fts"] = str(f["from_ts"]).replace("T", " ")
    if f.get("to_ts"):
        c.append("ts <= %(tts)s"); p["tts"] = str(f["to_ts"]).replace("T", " ")
    if f.get("exclude_admin", True):
        c.append("actor_type != 'admin'")
    return (" AND ".join(c) if c else "1"), p


def where_literal(f: dict) -> str:
    c = []
    if f.get("q"):
        q = esc_lit(f["q"].strip())
        c.append("(positionCaseInsensitive(nom, {0}) > 0 OR positionCaseInsensitive(prenom, {0}) > 0 "
                 "OR positionCaseInsensitive(ville, {0}) > 0 OR positionCaseInsensitive(mail, {0}) > 0 "
                 "OR positionCaseInsensitive(tel, {0}) > 0 OR positionCaseInsensitive(ip, {0}) > 0 "
                 "OR positionCaseInsensitive(actor_id, {0}) > 0 OR positionCaseInsensitive(actor_label, {0}) > 0 "
                 "OR positionCaseInsensitive(profile_ref, {0}) > 0)".format(q))
    if f.get("actor_type") and f["actor_type"] != "all":
        c.append("actor_type = " + esc_lit(f["actor_type"]))
    if f.get("actor_id"):
        c.append("actor_id = " + esc_lit(f["actor_id"]))
    if f.get("ip"):
        c.append("ip = " + esc_lit(f["ip"]))
    if f.get("profile_ref"):
        c.append("profile_ref = " + esc_lit(f["profile_ref"]))
    if f.get("from_ts"):
        c.append("ts >= " + esc_lit(str(f["from_ts"]).replace("T", " ")))
    if f.get("to_ts"):
        c.append("ts <= " + esc_lit(str(f["to_ts"]).replace("T", " ")))
    if f.get("exclude_admin", True):
        c.append("actor_type != 'admin'")
    return " AND ".join(c) if c else "1"


def insert_click(row: list) -> None:
    get_ch().insert(TABLE, data=[row], column_names=COLUMN_NAMES)


def list_clicks(f: dict, limit: int = 100, offset: int = 0) -> list[dict]:
    where, p = _where(f)
    p["lim"], p["off"] = limit, offset
    res = get_ch().query(
        f"SELECT {COLS} FROM {TABLE} WHERE {where} "
        f"ORDER BY ts DESC LIMIT %(lim)s OFFSET %(off)s", parameters=p)
    return [_row(r) for r in res.result_rows]


def count_clicks(f: dict) -> int:
    where, p = _where(f)
    res = get_ch().query(f"SELECT count() FROM {TABLE} WHERE {where}", parameters=p)
    return int(res.result_rows[0][0]) if res.result_rows else 0


def clicks_for_actor(actor_type: str, actor_id: str, limit: int = 30) -> list[dict]:
    res = get_ch().query(
        f"SELECT {COLS} FROM {TABLE} WHERE actor_type = %(at)s AND actor_id = %(aid)s "
        f"ORDER BY ts DESC LIMIT %(l)s",
        parameters={"at": actor_type, "aid": actor_id, "l": limit})
    return [_row(r) for r in res.result_rows]


def stats(hours: int = 720) -> dict:
    ch = get_ch()
    r = ch.query(f"""
        SELECT count(), uniqExact(profile_ref), uniqExact(actor_id), uniqExact(ip),
               countIf(actor_type='user'), countIf(actor_type='guest'), countIf(actor_type='api')
        FROM {TABLE} WHERE ts >= now() - INTERVAL %(h)s HOUR
    """, parameters={"h": hours}).result_rows[0]
    out = {"total": int(r[0]), "profils_uniques": int(r[1]), "acteurs_uniques": int(r[2]),
           "ips_uniques": int(r[3]), "par_users": int(r[4]),
           "par_guests": int(r[5]), "par_api": int(r[6])}

    top = ch.query(f"""
        SELECT profile_ref, any(nom) AS nom, any(prenom) AS prenom, any(ville) AS ville,
               any(source) AS source, count() AS n
        FROM {TABLE} WHERE ts >= now() - INTERVAL %(h)s HOUR
        GROUP BY profile_ref ORDER BY n DESC LIMIT 20
    """, parameters={"h": hours})
    out["top_profils"] = [{"profile_ref": str(x[0]), "nom": str(x[1]), "prenom": str(x[2]),
                           "ville": str(x[3]), "source": str(x[4]), "clicks": int(x[5])}
                          for x in top.result_rows]

    act = ch.query(f"""
        SELECT actor_type, actor_id, any(actor_label) AS label, count() AS n
        FROM {TABLE} WHERE ts >= now() - INTERVAL %(h)s HOUR
        GROUP BY actor_type, actor_id ORDER BY n DESC LIMIT 20
    """, parameters={"h": hours})
    out["top_acteurs"] = [{"actor_type": str(x[0]), "actor_id": str(x[1]),
                           "actor_label": str(x[2]), "clicks": int(x[3])}
                          for x in act.result_rows]

    jours = ch.query(f"""
        SELECT toDate(ts) AS d, count() FROM {TABLE}
        WHERE ts >= now() - INTERVAL %(h)s HOUR GROUP BY d ORDER BY d DESC LIMIT 60
    """, parameters={"h": hours})
    out["par_jour"] = [{"jour": str(x[0]), "clicks": int(x[1])} for x in jours.result_rows]
    return out


def profile_summary(profile_ref: str, hours: int = 2160) -> dict:
    ch = get_ch()
    p = {"pr": profile_ref, "h": hours}
    fiche = ch.query(f"""
        SELECT any(nom), any(prenom), any(date_naissance), any(ville), any(code_postal),
               any(mail), any(tel), any(source)
        FROM {TABLE} WHERE profile_ref = %(pr)s
    """, parameters=p).result_rows[0]
    agg = ch.query(f"""
        SELECT count(), uniqExact(ip), uniqExact(actor_id), min(ts), max(ts),
               countIf(actor_type='user'), countIf(actor_type='guest'), countIf(actor_type='api')
        FROM {TABLE} WHERE profile_ref = %(pr)s AND ts >= now() - INTERVAL %(h)s HOUR
    """, parameters=p).result_rows[0]

    act = ch.query(f"""
        SELECT actor_type, actor_id, any(actor_label) AS label, count() AS n, max(ts) AS last
        FROM {TABLE} WHERE profile_ref = %(pr)s
        GROUP BY actor_type, actor_id ORDER BY n DESC LIMIT 100
    """, parameters=p)
    crit = ch.query(f"""
        SELECT criteria, count() AS n FROM {TABLE}
        WHERE profile_ref = %(pr)s AND criteria != ''
        GROUP BY criteria ORDER BY n DESC LIMIT 20
    """, parameters=p)

    return {
        "profile_ref": profile_ref,
        "fiche": {"nom": str(fiche[0]), "prenom": str(fiche[1]),
                  "date_naissance": str(fiche[2]), "ville": str(fiche[3]),
                  "code_postal": str(fiche[4]), "mail": str(fiche[5]),
                  "tel": str(fiche[6]), "source": str(fiche[7])},
        "total_clicks": int(agg[0]), "ips_uniques": int(agg[1]), "acteurs_uniques": int(agg[2]),
        "premier": str(agg[3]), "dernier": str(agg[4]),
        "par_users": int(agg[5]), "par_guests": int(agg[6]), "par_api": int(agg[7]),
        "acteurs": [{"actor_type": str(x[0]), "actor_id": str(x[1]), "actor_label": str(x[2]),
                     "clicks": int(x[3]), "dernier": str(x[4])} for x in act.result_rows],
        "criteres": [{"criteria": str(x[0]), "n": int(x[1])} for x in crit.result_rows],
    }
