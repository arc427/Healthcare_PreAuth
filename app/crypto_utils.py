import hashlib
import json
import os
import secrets
from typing import Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def _normalize_key(key: str | bytes) -> bytes:
    """AES-256 requires a 32-byte key. Hash any other input to 32 bytes."""
    if isinstance(key, str):
        key_bytes = key.encode("utf-8")
    else:
        key_bytes = key
    if len(key_bytes) == 32:
        return key_bytes
    return hashlib.sha256(key_bytes).digest()


def encrypt_data(data_dict: dict[str, Any], key: str | bytes) -> tuple[str, str]:
    """Encrypt a dictionary with AES-256-CBC.

    Returns:
        (encrypted_hex, iv_hex)
    """
    plaintext = json.dumps(data_dict, separators=(",", ":"), sort_keys=True).encode("utf-8")
    padder = padding.PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()

    iv = os.urandom(16)
    cipher = Cipher(
        algorithms.AES(_normalize_key(key)),
        modes.CBC(iv),
        backend=default_backend(),
    )
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return ciphertext.hex(), iv.hex()


def decrypt_data(encrypted_hex: str, iv: str, key: str | bytes) -> dict[str, Any]:
    """Decrypt an AES-256-CBC hex payload back into the original dictionary."""
    iv_bytes = bytes.fromhex(iv)
    ciphertext = bytes.fromhex(encrypted_hex)
    cipher = Cipher(
        algorithms.AES(_normalize_key(key)),
        modes.CBC(iv_bytes),
        backend=default_backend(),
    )
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()
    return json.loads(plaintext.decode("utf-8"))


def generate_hash(data_string: str) -> str:
    """Return the SHA-256 hex digest of a string."""
    if not isinstance(data_string, str):
        data_string = json.dumps(data_string, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(data_string.encode("utf-8")).hexdigest()


def hash_password(password: str, salt: str | None = None) -> str:
    """Hash a password securely using PBKDF2-HMAC-SHA256."""
    if salt is None:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"{salt}${key.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plain password against a PBKDF2-HMAC-SHA256 password hash."""
    if "$" not in password_hash:
        return False
    salt, _ = password_hash.split("$", 1)
    computed = hash_password(password, salt)
    return secrets.compare_digest(computed, password_hash)
