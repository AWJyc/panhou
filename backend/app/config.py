from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = "sqlite:///./tradeagent.db"

    # Tavily 搜索
    tavily_api_key: str = ""

    # 服务端默认 LLM provider（用于生成每日报告）
    # anthropic | deepseek | doubao | qwen | openai | openai_compatible
    report_provider: str = "deepseek"
    report_api_key: str = ""
    report_model: str = ""  # 空则按 provider 推断默认值
    report_base_url: str = ""  # 空则按 provider 推断默认值

    # 兼容旧字段（如果未来切回 Anthropic）
    anthropic_api_key: str = ""

    admin_rebuild_token: str = "change-me"

    # 用户系统
    # JWT 签名密钥；用 `openssl rand -hex 32` 生成。生产必须改成强随机
    auth_secret: str = "dev-only-please-change-in-prod-32-chars-min"
    auth_token_ttl_days: int = 30
    # BYOK key 服务端落库时的 Fernet 加密密钥（base64，44 字符）。
    # 生成方式：python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    byok_encryption_key: str = ""
    # 生产打开（HTTPS）；开发用 HTTP 时设 false
    cookie_secure: bool = False

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    scheduler_timezone: str = "Asia/Shanghai"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
