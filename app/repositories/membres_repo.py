from app.db.clickhouse import get_ch

TABLE = "sports_db.membres"

def list_sources() -> list[str]:
    res = get_ch().query(
        f"SELECT DISTINCT source FROM {TABLE} WHERE source != '' ORDER BY source")
    return [r[0] for r in res.result_rows]

def total_rows() -> int:
    res = get_ch().query(f"SELECT count() FROM {TABLE}")
    return res.result_rows[0][0] if res.result_rows else 0

def count_by_source() -> list[dict]:
    res = get_ch().query(f"""
        SELECT if(source = '', 'Inconnue', source) AS src, count() AS cnt
        FROM {TABLE} GROUP BY src ORDER BY cnt DESC
    """)
    return [{"source": r[0], "count": r[1]} for r in res.result_rows]

def search(where_clause: str, params: dict, limit: int) -> list[tuple]:
    res = get_ch().query(f"""
        SELECT nom, prenom, date_naissance, annee_naissance, mois_naissance,
               jour_naissance, mail, code_postal, ville, adresse,
               numero_tel, iban, bic, source
        FROM {TABLE}
        {where_clause}
        ORDER BY nom, prenom
        LIMIT %(limit)s
    """, parameters={**params, "limit": limit})
    return res.result_rows

def raw_query(query: str, params: dict) -> list[tuple]:
    return get_ch().query(query, parameters=params).result_rows
