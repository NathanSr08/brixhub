"""
BrixHub - Verification du schema ClickHouse + creation des tables d'audit.

Ne touche PAS aux tables existantes conformes (users, api_keys, api_usage,
search_log, membres) : elles sont seulement verifiees et rapportees.
Cree uniquement ce qui manque. Idempotent.

Usage :  docker exec web_search_app python -m app.db.bootstrap
"""
from app.db.clickhouse import get_ch

AUDIT_TABLES = {
    "auth_db.api_logs": """
        CREATE TABLE IF NOT EXISTS auth_db.api_logs
        (
            id UUID DEFAULT generateUUIDv4(),
            timestamp DateTime64(3) DEFAULT now64(3),
            actor_type LowCardinality(String) DEFAULT 'guest',
            actor_id String DEFAULT '', actor_label String DEFAULT '', session_ref String DEFAULT '',
            ip String DEFAULT '', user_id String DEFAULT 'guest', user_email String DEFAULT 'anonymous',
            endpoint String DEFAULT '', path String DEFAULT '', route String DEFAULT '',
            method LowCardinality(String) DEFAULT 'GET', query_params String DEFAULT '',
            status_code UInt16 DEFAULT 200, execution_time_ms Float32 DEFAULT 0, latency_ms UInt32 DEFAULT 0,
            user_agent String DEFAULT '', ua_hash String DEFAULT '', referer String DEFAULT '',
            request_id String DEFAULT '', error String DEFAULT '',
            tag LowCardinality(String) DEFAULT 'web', meta String DEFAULT '',
            INDEX idx_ip ip TYPE bloom_filter(0.01) GRANULARITY 4,
            INDEX idx_actor actor_id TYPE bloom_filter(0.01) GRANULARITY 4,
            INDEX idx_path path TYPE bloom_filter(0.01) GRANULARITY 4,
            INDEX idx_rid request_id TYPE bloom_filter(0.01) GRANULARITY 4
        )
        ENGINE = MergeTree
        PARTITION BY toYYYYMM(timestamp)
        ORDER BY (timestamp, id)
        TTL toDateTime(timestamp) + INTERVAL 180 DAY
        SETTINGS index_granularity = 8192
    """,
    "auth_db.admin_actions": """
        CREATE TABLE IF NOT EXISTS auth_db.admin_actions
        (
            ts DateTime DEFAULT now(), admin_ref String, action LowCardinality(String),
            target_type LowCardinality(String), target_id String, ip String, details String
        )
        ENGINE = MergeTree ORDER BY ts TTL ts + INTERVAL 365 DAY
    """,
}

AUDIT_COLUMNS = [
    ("auth_db.api_logs", "actor_type", "LowCardinality(String) DEFAULT 'guest'"),
    ("auth_db.api_logs", "actor_id", "String DEFAULT ''"),
    ("auth_db.api_logs", "actor_label", "String DEFAULT ''"),
    ("auth_db.api_logs", "session_ref", "String DEFAULT ''"),
    ("auth_db.api_logs", "path", "String DEFAULT ''"),
    ("auth_db.api_logs", "route", "String DEFAULT ''"),
    ("auth_db.api_logs", "latency_ms", "UInt32 DEFAULT 0"),
    ("auth_db.api_logs", "ua_hash", "String DEFAULT ''"),
    ("auth_db.api_logs", "referer", "String DEFAULT ''"),
    ("auth_db.api_logs", "request_id", "String DEFAULT ''"),
    ("auth_db.api_logs", "error", "String DEFAULT ''"),
    ("auth_db.api_logs", "tag", "LowCardinality(String) DEFAULT 'web'"),
    ("auth_db.api_logs", "meta", "String DEFAULT ''"),
]

REQUIRED = {
    "sports_db.users": ["user_id", "email", "password_hash", "is_active", "plan",
                        "api_key_id", "created_at"],
    "sports_db.api_keys": ["key_id", "key_hash", "preview", "label", "owner_email",
                           "plan", "is_active", "created_at"],
    "sports_db.api_usage": ["key_id", "ts", "endpoint", "status", "latency_ms", "client_ip"],
    "sports_db.search_log": ["ts", "client_ip", "key_id", "criteria", "nb_results"],
    "sports_db.membres": ["nom", "prenom", "numero_tel", "mail", "ville", "source"],
}


def _cols(ch, table: str) -> dict:
    d, t = table.split(".")
    rows = ch.query(
        "SELECT name, type FROM system.columns WHERE database=%(d)s AND table=%(t)s ORDER BY position",
        parameters={"d": d, "t": t}).result_rows
    return {r[0]: r[1] for r in rows}


def report() -> None:
    ch = get_ch()
    print("\n=== TABLES PRESENTES ===")
    for r in ch.query(
        "SELECT database, name, engine, total_rows FROM system.tables "
        "WHERE database IN ('sports_db','auth_db') ORDER BY database, name").result_rows:
        print(f"  {r[0]}.{r[1]:<22} [{r[2]}] {r[3]} lignes")

    print("\n=== TABLES APPLICATIVES (attendues) ===")
    for table, cols in REQUIRED.items():
        got = _cols(ch, table)
        if not got:
            print(f"  {table} : ABSENTE")
            continue
        miss = [c for c in cols if c not in got]
        print(f"  {table} : OK ({len(got)} colonnes)" if not miss
              else f"  {table} : COLONNES MANQUANTES -> {miss}")

    print("\n=== TABLES D'AUDIT ===")
    for table in AUDIT_TABLES:
        got = _cols(ch, table)
        print(f"  {table} : ABSENTE" if not got else f"  {table} : presente ({len(got)} colonnes)")


def ensure_pricing_defaults() -> None:
    """Cree les reglages et plans par defaut s'ils manquent."""
    try:
        from app.repositories import pricing_repo
        pricing_repo.ensure_defaults()
        print("[BOOTSTRAP] reglages et plans par defaut verifies")
    except Exception as e:
        print(f"[BOOTSTRAP] pricing defaults KO: {e}")


def ensure_schema() -> None:
    ch = get_ch()
    created, altered, failed = [], [], []

    for table, ddl in AUDIT_TABLES.items():
        if ch.query(f"EXISTS TABLE {table}").result_rows[0][0] != 1:
            ch.command(ddl)
            created.append(table)

    for table, col, spec in AUDIT_COLUMNS:
        try:
            if ch.query(f"EXISTS TABLE {table}").result_rows[0][0] != 1:
                continue
            if col not in _cols(ch, table):
                ch.command(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {spec}")
                altered.append(f"{table}.{col}")
        except Exception as e:
            failed.append(f"{table}.{col} : {e}")

    print("\n=== ACTIONS ===")
    print("  Tables creees     :", created or "aucune (deja presentes)")
    print("  Colonnes ajoutees :", altered or "aucune")
    for f in failed:
        print("  ECHEC             :", f)


if __name__ == "__main__":
    import asyncio
    from app.db.clickhouse import init_clients

    async def _main():
        await init_clients()
        report()
        ensure_schema()
        print("\n=== APRES ===")
        report()

    asyncio.run(_main())
