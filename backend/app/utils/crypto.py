"""
Encryption utilities for sensitive data (database passwords).
Uses Fernet symmetric encryption.
"""
from cryptography.fernet import Fernet
from app.config import settings


def get_fernet_key() -> bytes:
    """
    Get Fernet encryption key from settings.
    Generates a new key if not configured.

    Returns:
        Fernet key as bytes
    """
    if not settings.FERNET_KEY:
        # Generate new key on first run
        key = Fernet.generate_key()
        print(f"⚠️  WARNING: No FERNET_KEY in .env. Generated new key:")
        print(f"FERNET_KEY={key.decode()}")
        print("Add this to your .env file for persistent encryption!")
        return key

    return settings.FERNET_KEY.encode()


# Global Fernet instance
_fernet = Fernet(get_fernet_key())


def encrypt_password(password: str) -> str:
    """
    Encrypt a database password.

    Args:
        password: Plain text password

    Returns:
        Encrypted password as string
    """
    return _fernet.encrypt(password.encode()).decode()


def decrypt_password(encrypted_password: str) -> str:
    """
    Decrypt a database password.

    Args:
        encrypted_password: Encrypted password string

    Returns:
        Plain text password

    Raises:
        cryptography.fernet.InvalidToken: If decryption fails
    """
    return _fernet.decrypt(encrypted_password.encode()).decode()
