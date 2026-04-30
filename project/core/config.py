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
    TELEGRAM_BOT_TOKEN: str = "123456:TEST"
    TELEGRAM_WEBHOOK_SECRET: str = "TEST_SECRET"
    TELEGRAM_WEBHOOK_BASE_URL: str = "http://localhost:8000"  # e.g. https://example.com
    TELEGRAM_WEBHOOK_PATH: str = "/telegram/webhook"
    TELEGRAM_WEBHOOK_URL: str = f"https://{TELEGRAM_WEBHOOK_BASE_URL.rstrip('/')}{TELEGRAM_WEBHOOK_PATH}"

    # External providers
    COINGECKO_API_KEY: str = ""

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

settings = Settings()
