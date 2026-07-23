"""Fernet helpers for encrypting provider API keys at rest."""
import base64
import hashlib
from cryptography.fernet import Fernet, InvalidToken
from bebcare.config.settings import settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        digest = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
        _fernet = Fernet(base64.urlsafe_b64encode(digest))
    return _fernet


def encrypt_secret(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as e:
        raise ValueError("Failed to decrypt secret; check SECRET_KEY") from e


def mask_secret(plaintext: str, visible: int = 4) -> str:
    if not plaintext:
        return ""
    if len(plaintext) <= visible * 2:
        return "*" * len(plaintext)
    return f"{plaintext[:visible]}...{plaintext[-visible:]}"
