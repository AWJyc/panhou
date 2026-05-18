"""BYOK key 加密 / 解密。Fernet 对称加密，key 来自 .env。

如果 .env 没配 BYOK_ENCRYPTION_KEY，启动时生成一个临时 key（不写盘），
重启后所有已存的 BYOK 都解密失败 —— 仅供本地开发。
"""

import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    settings = get_settings()
    key = settings.byok_encryption_key.strip()
    if not key:
        key = Fernet.generate_key().decode()
        log.warning(
            "BYOK_ENCRYPTION_KEY 未配置，使用进程内临时密钥；重启后已存的 BYOK 会全部解密失败。"
            "生产环境请去 .env 设一个固定值（44 字符 base64）。"
        )
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt_key(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_key(cipher: str) -> str:
    try:
        return _fernet().decrypt(cipher.encode("ascii")).decode("utf-8")
    except InvalidToken:
        raise ValueError("解密失败：BYOK 密文与当前 BYOK_ENCRYPTION_KEY 不匹配")
