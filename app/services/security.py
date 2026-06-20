import hashlib
import os

def hash_password(password: str) -> str:
    """
    Hashes a password using standard PBKDF2-HMAC-SHA256 with 100,000 iterations.
    Returns: salt_hex:key_hex
    """
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return f"{salt.hex()}:{key.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    """
    Verifies a password against its PBKDF2-HMAC-SHA256 hash.
    """
    try:
        if not hashed or ":" not in hashed:
            return False
        salt_hex, key_hex = hashed.split(":")
        salt = bytes.fromhex(salt_hex)
        key = bytes.fromhex(key_hex)
        new_key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return new_key == key
    except Exception:
        return False
