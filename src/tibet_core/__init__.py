"""
tibet-core: Token-based Intent, Behavior, Evidence & Trust

Cryptographic provenance for trustworthy systems.
Zero dependencies. Audit-ready. Compliance-friendly.

Supports: ISO 5338, NIS2, BIO2, OWASP

Usage:
    from tibet_core import Token, Provider

    # Create provider
    tibet = Provider(actor="my_system")

    # Create tokens for any action
    token = tibet.create(
        action="user_login",
        erin={"user_id": "123", "method": "oauth"},
        erachter="User authentication request"
    )

    # Verify integrity
    assert token.verify()

    # Get audit trail
    audit = tibet.export()

Dutch Provenance Semantics:
    ERIN: What's IN the action (content, data)
    ERAAN: What's attached (dependencies, references)
    EROMHEEN: Context around it (environment, state)
    ERACHTER: Intent behind it (why this action)
"""

from .token import Token, TokenState
from .provider import Provider
from .chain import Chain
from .store import MemoryStore, FileStore

__version__ = "0.2.0"
__all__ = [
    "Token",
    "TokenState",
    "Provider",
    "Chain",
    "MemoryStore",
    "FileStore",
]
