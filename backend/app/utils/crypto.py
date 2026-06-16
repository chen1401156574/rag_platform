import os
import base64
import logging
from cryptography.fernet import Fernet

logger = logging.getLogger("crypto")


def _get_fernet() -> Fernet:
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise RuntimeError("ENCRYPTION_KEY 环境变量未设置，无法加解密 API Key")
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as e:
        raise RuntimeError(f"ENCRYPTION_KEY 格式无效: {e}")


def encrypt_api_key(plaintext: str) -> str:
    f = _get_fernet()
    token = f.encrypt(plaintext.encode("utf-8"))
    return base64.urlsafe_b64encode(token).decode("ascii")


def decrypt_api_key(ciphertext: str) -> str:
    f = _get_fernet()
    token = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
    return f.decrypt(token).decode("utf-8")
