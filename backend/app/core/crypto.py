"""Encryption helpers for storing third-party credentials."""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _get_fernet(key: str) -> Fernet:
    return Fernet(key)


def _get_garmin_fernet() -> Fernet:
    return _get_fernet(settings.garmin_password_encryption_key)


def _get_calendar_fernet() -> Fernet:
    key = settings.google_calendar_token_encryption_key or settings.garmin_password_encryption_key
    return _get_fernet(key)


def encrypt_secret(value: str) -> str:
    fernet = _get_garmin_fernet()
    return fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    fernet = _get_garmin_fernet()
    try:
        return fernet.decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt stored credentials") from exc


def encrypt_calendar_token(value: str) -> str:
    fernet = _get_calendar_fernet()
    return fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_calendar_token(value: str) -> str:
    fernet = _get_calendar_fernet()
    try:
        return fernet.decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt calendar credentials") from exc
