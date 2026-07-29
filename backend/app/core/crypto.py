"""API Key 加密(ADR-0006: Fernet 对称加密 + APP_ENCRYPTION_KEY 环境变量)。"""
from cryptography.fernet import Fernet

from app.core.config import settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(settings.APP_ENCRYPTION_KEY.encode() if isinstance(settings.APP_ENCRYPTION_KEY, str) else settings.APP_ENCRYPTION_KEY)
    return _fernet


def encrypt_secret(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()


def mask_secret(ciphertext: str) -> str:
    """返回脱敏显示(前后各少量字符)。"""
    try:
        plain = decrypt_secret(ciphertext)
    except Exception:
        return "****"
    if len(plain) <= 8:
        return "****"
    return f"{plain[:3]}...{plain[-3:]}"
