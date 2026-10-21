CREATE TABLE IF NOT EXISTS sports_db.api_keys (
    key_id       String,
    key_hash     FixedString(64),
    preview      String,
    label        String,
    owner_email  String,
    plan         LowCardinality(String) DEFAULT 'free',
    is_active    UInt8 DEFAULT 1,
    created_at   DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(created_at)
ORDER BY key_hash;

CREATE TABLE IF NOT EXISTS sports_db.api_usage (
    key_id       String,
    ts           DateTime DEFAULT now(),
    endpoint     String,
    status       UInt16,
    latency_ms   UInt32,
    client_ip    String
) ENGINE = MergeTree
ORDER BY (key_id, ts)
TTL ts + INTERVAL 180 DAY;

CREATE TABLE IF NOT EXISTS sports_db.search_log (
    ts           DateTime DEFAULT now(),
    client_ip    String,
    key_id       String,
    criteria     String,
    nb_results   UInt32
) ENGINE = MergeTree
ORDER BY ts
TTL ts + INTERVAL 365 DAY;
