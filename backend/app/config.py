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

    # 飞书自定义机器人 webhook（pipeline 跑完发告警）
    # 建群 → 设置 → 群机器人 → 添加机器人 → 自定义机器人 → 复制 Webhook 地址
    # secret 可选；如开了"签名校验"必填
    feishu_webhook_url: str = ""
    feishu_webhook_secret: str = ""
    notify_enabled: bool = True
    notify_level: str = "all"  # "all" | "failure"

    # 阿里云 DM SMTP（发注册验证码 + 密码重置码）
    # host: smtpdm.aliyun.com（中国大陆）/ smtpdm-ap-southeast-1.aliyuncs.com（香港、国际）
    # user: 你在 DM 控制台创建的发信地址，例如 noreply@panhou.xyz
    # password: 创建发信地址时设的 SMTP 密码（不是阿里云账号密码）
    smtp_host: str = ""
    smtp_port: int = 465  # SSL/TLS
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_name: str = "panhou"  # 收件人看到的发件人显示名
    # 邮件正文里"前往验证"等链接的前缀；生产填 https://panhou.xyz
    app_base_url: str = "http://localhost:3000"

    # 邮箱验证码策略
    verify_code_ttl_seconds: int = 900  # 15 分钟
    verify_code_max_attempts: int = 5
    verify_code_resend_cooldown_seconds: int = 60


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
