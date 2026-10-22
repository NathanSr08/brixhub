CREATE TABLE auth_db.api_logs
(
    `id` UUID DEFAULT generateUUIDv4(),
    `timestamp` DateTime64(3) DEFAULT now64(3),
    `actor_type` LowCardinality(String) DEFAULT 'guest',
    `actor_id` String DEFAULT '',
    `actor_label` String DEFAULT '',
    `session_ref` String DEFAULT '',
    `ip` String DEFAULT '',
    `user_id` String DEFAULT 'guest',
    `user_email` String DEFAULT 'anonymous',
    `endpoint` String DEFAULT '',
    `path` String DEFAULT '',
    `route` String DEFAULT '',
    `method` LowCardinality(String) DEFAULT 'GET',
    `query_params` String DEFAULT '',
    `status_code` UInt16 DEFAULT 200,
    `execution_time_ms` Float32 DEFAULT 0,
    `latency_ms` UInt32 DEFAULT 0,
    `user_agent` String DEFAULT '',
    `ua_hash` String DEFAULT '',
    `referer` String DEFAULT '',
    `request_id` String DEFAULT '',
    `error` String DEFAULT '',
    `tag` LowCardinality(String) DEFAULT 'web',
    `meta` String DEFAULT '',
    INDEX idx_ip ip TYPE bloom_filter(0.01) GRANULARITY 4,
    INDEX idx_actor actor_id TYPE bloom_filter(0.01) GRANULARITY 4,
    INDEX idx_path path TYPE bloom_filter(0.01) GRANULARITY 4,
    INDEX idx_rid request_id TYPE bloom_filter(0.01) GRANULARITY 4
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, id)
TTL toDateTime(timestamp) + toIntervalDay(180)
SETTINGS index_granularity = 8192
;
CREATE TABLE auth_db.admin_actions
(
    `ts` DateTime DEFAULT now(),
    `admin_ref` String,
    `action` LowCardinality(String),
    `target_type` LowCardinality(String),
    `target_id` String,
    `ip` String,
    `details` String
)
ENGINE = MergeTree
ORDER BY ts
TTL ts + toIntervalDay(365)
SETTINGS index_granularity = 8192
