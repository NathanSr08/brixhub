import os
from functools import lru_cache

class Settings:
    def __init__(self):
        self.clickhouse_host = os.getenv("CLICKHOUSE_HOST", "host.docker.internal")
        self.clickhouse_port = int(os.getenv("CLICKHOUSE_PORT", "8123"))
        self.clickhouse_user = os.getenv("CLICKHOUSE_USER", "default")
        self.clickhouse_password = os.getenv("CLICKHOUSE_PASSWORD", "")
        self.redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        self.admin_token = os.getenv("ADMIN_TOKEN", "sk_admin_secret_key_change_me_9921")
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "8879365809:AAFUAimk_Cf_LQWQ3pP_pBy5Ef2yO1jMq-Q")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "8714430026")
        self.key_prefix = "brx_"
        self.legacy_open = True
        self.plans = {
            "free": 500,
            "pro": 50_000,
            "business": 500_000,
            "unlimited": 10_000_000,
        }

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
