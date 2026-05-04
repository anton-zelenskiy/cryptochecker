from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env', env_file_encoding='utf-8', extra='ignore'
    )

    PROJECT_NAME: str = 'CryptoChecker'

    # Database settings
    POSTGRES_USER: str = "cryptochecker"
    POSTGRES_PASSWORD: str = "cryptochecker"
    POSTGRES_HOST: str = "db"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "cryptochecker"
    DB_ECHO_LOG: bool = False  # Default to False for production

    # Telegram settings
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_WEBHOOK_SECRET: str = ""
    TELEGRAM_WEBHOOK_BASE_URL: str = ""
    TELEGRAM_WEBHOOK_PATH: str = "/telegram/webhook"
    
    @property
    def TELEGRAM_WEBHOOK_URL(self) -> str:  # noqa
        base = self.TELEGRAM_WEBHOOK_BASE_URL.strip().rstrip("/")
        if base.startswith("http://") or base.startswith("https://"):
            return f"{base}/cryptochecker{self.TELEGRAM_WEBHOOK_PATH}"
        return f"https://{base}/cryptochecker{self.TELEGRAM_WEBHOOK_PATH}"

    # External providers
    COINGECKO_API_KEY: str = ""
    KUCOIN_API_KEY: str = ""
    KUCOIN_API_SECRET: str = ""
    KUCOIN_API_PASSPHRASE: str = ""

    BYBIT_API_KEY: str = ""
    BYBIT_API_SECRET: str = ""

    # Redis settings
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ''

    # Build database URL
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:  # noqa
        return f'postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}'

    @property
    def REDIS_URL(self) -> str:  # noqa
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    CELERY_EXCLUSIVE_TASK_LOCK_PREFIX: str = "celery:exclusive:task"
    CELERY_EXCLUSIVE_LOCK_TIMEOUT_SEC: int = 7200

    BACKEND_CORS_ORIGINS: list[str] = [
        'http://localhost:8000',
        'https://tidy-simply-camel.ngrok-free.app',
    ]

    # Proxy settings
    # Trusted hosts for proxy headers (X-Forwarded-Proto, X-Forwarded-For)
    # Accepts: "*" (trust all), IP addresses, or CIDR ranges (comma-separated)
    # In production: set to nginx/reverse proxy IP(s) or Docker network CIDR
    # Examples: "172.22.0.1", "172.22.0.0/16", "127.0.0.1,10.0.0.0/8"
    TRUSTED_PROXY_HOSTS: str = '*'

    SCREENER_LLM_RECHECK_ENABLED: bool = True

    SCREENER_NOTIFICATIONS_ENABLED: bool = True
    SCREENER_NOTIFY_MIN_CONFIDENCE: float = 0.65
    SCREENER_SIGNAL_DEDUP_TTL_HOURS: int = 24

    PAPER_TRADING_ENABLED: bool = True
    PAPER_TRADING_MIN_CONFIDENCE: float = 0.65
    PAPER_TRADING_FLIP_MIN_CONFIDENCE: float = 0.70
    PAPER_TRADING_MAX_SNAPSHOT_AGE_MINUTES: int = 5
    PAPER_TRADING_EXIT_SCAN_TIMEFRAME: str = "5m"


settings = Settings()
