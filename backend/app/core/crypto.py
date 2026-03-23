"""Encryption helpers for storing third-party credentials."""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _get_fernet(key: str) -> Fernet:
    return Fernet(key)


def _get_garmin_fernet() -> Fernet:
    return _get_fernet(settings.garmin_password_encryption_key)


def _iter_garmin_keys() -> list[str]:
    keys = [settings.garmin_password_encryption_key]
    for raw_value in settings.garmin_password_encryption_key_fallbacks.replace("\n", ",").split(","):
        candidate = raw_value.strip()
        if candidate and candidate not in keys:
            keys.append(candidate)
    return keys


def _get_calendar_fernet() -> Fernet:
    key = settings.google_calendar_token_encryption_key or settings.garmin_password_encryption_key
    return _get_fernet(key)


def current_garmin_encryption_key_id() -> str | None:
    return settings.garmin_password_encryption_key_id


def encrypt_secret(value: str) -> str:
    fernet = _get_garmin_fernet()
    return fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret_with_context(value: str) -> tuple[str, bool]:
    token = value.encode("utf-8")
    last_error: InvalidToken | None = None
    for index, key in enumerate(_iter_garmin_keys()):
        try:
            decrypted = _get_fernet(key).decrypt(token).decode("utf-8")
            return decrypted, index > 0
        except InvalidToken as exc:
            last_error = exc
    raise ValueError("Unable to decrypt stored credentials") from last_error


def decrypt_secret(value: str) -> str:
    decrypted, _used_fallback = decrypt_secret_with_context(value)
    return decrypted


def encrypt_calendar_token(value: str) -> str:
    fernet = _get_calendar_fernet()
    return fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_calendar_token(value: str) -> str:
    fernet = _get_calendar_fernet()
    try:
        return fernet.decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt calendar credentials") from exc
