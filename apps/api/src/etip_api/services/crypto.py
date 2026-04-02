"""
Symmetric encryption for connector config secrets.

Secrets are encrypted with Fernet (AES-128-CBC + HMAC-SHA256) using a key
stored in settings.connector_encryption_key.  The DB column stays JSONB;
we wrap the ciphertext in an envelope dict so the column shape is consistent.

Envelope format:  {"v": 1, "ct": "<base64-fernet-token>"}
"""

import json

from cryptography.fernet import Fernet, InvalidToken

from etip_core.settings import get_settings


def _fernet() -> Fernet:
    key = get_settings().connector_encryption_key
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_config(config: dict) -> dict:
    """Encrypt a connector config dict and return a storable envelope."""
    plaintext = json.dumps(config).encode()
    ciphertext = _fernet().encrypt(plaintext).decode()
    return {"v": 1, "ct": ciphertext}


def decrypt_config(stored: dict) -> dict:
    """Decrypt a stored envelope and return the original config dict."""
    ciphertext = stored["ct"].encode()
    plaintext = _fernet().decrypt(ciphertext)
    return json.loads(plaintext)


def is_encrypted(stored: dict) -> bool:
    """Return True if the stored value is an encrypted envelope."""
    return isinstance(stored, dict) and stored.get("v") == 1 and "ct" in stored
