"""Operations d'administration ClickHouse : purge, partitions, optimise."""
from app.db.clickhouse import get_ch

TARGETS = {
    "audit": "auth_db.api_logs",
    "clicks": "sports_db.profile_clicks",
    "admin_actions": "auth_db.admin_actions",
}


def esc_lit(v) -> str:
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("\\", "\\\\").replace("'", "''") + "'"


def resolve_targets(names) -> list[str]:
    out = []
    for n in (names or []):
        t = TARGETS.get(n, n)
        if t not in out:
            out.append(t)
    return out


def table_info(table: str) -> dict:
    ch = get_ch()
    d, t = table.split(".")
    parts = ch.query("""
        SELECT count(), sum(rows), formatReadableSize(sum(bytes_on_disk))
        FROM system.parts WHERE active AND database = %(d)s AND table = %(t)s
    """, parameters={"d": d, "t": t}).result_rows[0]
    total = ch.query(f"SELECT count() FROM {table}").result_rows[0][0]
    return {"table": table, "lignes": int(total),
            "taille": str(parts[2] or "0 B")}


def partitions(table: str) -> list[dict]:
    ch = get_ch()
    d, t = table.split(".")
    res = ch.query("""
        SELECT partition, sum(rows) AS n, formatReadableSize(sum(bytes_on_disk)) AS size
        FROM system.parts WHERE active AND database = %(d)s AND table = %(t)s
        GROUP BY partition ORDER BY partition DESC
    """, parameters={"d": d, "t": t})
    return [{"partition": str(r[0]), "lignes": int(r[1]), "taille": str(r[2])}
            for r in res.result_rows]


def count_where(table: str, condition: str) -> int:
    cond = (condition or "").strip() or "1"
    res = get_ch().query(f"SELECT count() FROM {table} WHERE {cond}")
    return int(res.result_rows[0][0]) if res.result_rows else 0


def drop_partitions(table: str, parts: list[str]) -> int:
    n = 0
    for p in parts:
        get_ch().command(f"ALTER TABLE {table} DROP PARTITION {esc_lit(p)}")
        n += 1
    return n


def truncate(table: str) -> None:
    get_ch().command(f"TRUNCATE TABLE {table}")


def purge_where(table: str, condition: str) -> None:
    cond = (condition or "").strip() or "1"
    get_ch().command(f"ALTER TABLE {table} DELETE WHERE {cond} SETTINGS mutations_sync = 1")


def optimize(table: str) -> None:
    get_ch().command(f"OPTIMIZE TABLE {table} FINAL")


def pending_mutations(table: str) -> int:
    res = get_ch().query(
        "SELECT count() FROM system.mutations WHERE database = %(d)s AND table = %(t)s AND is_done = 0",
        parameters={"d": table.split(".")[0], "t": table.split(".")[1]})
    return int(res.result_rows[0][0]) if res.result_rows else 0
