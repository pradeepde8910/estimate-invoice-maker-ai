"""Password hashing helpers.

Existing rows may still hold a legacy plaintext password (this app had no
hashing at all until now). verify_password() accepts either form so logins
keep working, and the caller re-hashes on successful legacy verification so
every account is transparently upgraded to bcrypt the next time it logs in.
"""
import hmac

import bcrypt

_BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def is_bcrypt_hash(value: str) -> bool:
    return bool(value) and value.startswith(_BCRYPT_PREFIXES)


def verify_password(password: str, stored: str) -> bool:
    if not stored:
        return False
    if is_bcrypt_hash(stored):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
        except ValueError:
            return False
    # Legacy plaintext row: constant-time compare so this path doesn't leak
    # timing information any worse than the bcrypt path does.
    return hmac.compare_digest(password.encode("utf-8"), stored.encode("utf-8"))
