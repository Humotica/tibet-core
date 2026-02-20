"""
TIBET Token Storage backends.
"""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional
from .token import Token


class TokenStore(ABC):
    """Abstract base for token storage."""

    @abstractmethod
    def add(self, token: Token) -> None:
        """Store a token."""
        pass

    @abstractmethod
    def get(self, token_id: str) -> Optional[Token]:
        """Get token by ID."""
        pass

    @abstractmethod
    def all(self) -> List[Token]:
        """Get all tokens."""
        pass

    @abstractmethod
    def find(
        self,
        action: Optional[str] = None,
        actor: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 100
    ) -> List[Token]:
        """Find tokens matching criteria."""
        pass

    @abstractmethod
    def count(self) -> int:
        """Count stored tokens."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all tokens."""
        pass


class MemoryStore(TokenStore):
    """
    In-memory token storage.

    Fast, simple, lost on restart.
    Good for: testing, short sessions, ephemeral audits.
    """

    def __init__(self):
        self._tokens: List[Token] = []
        self._index: dict[str, int] = {}

    def add(self, token: Token) -> None:
        self._index[token.token_id] = len(self._tokens)
        self._tokens.append(token)

    def get(self, token_id: str) -> Optional[Token]:
        idx = self._index.get(token_id)
        return self._tokens[idx] if idx is not None else None

    def all(self) -> List[Token]:
        return list(self._tokens)

    def find(
        self,
        action: Optional[str] = None,
        actor: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 100
    ) -> List[Token]:
        results = self._tokens

        if action:
            results = [t for t in results if t.action == action]
        if actor:
            results = [t for t in results if t.actor == actor]
        if since:
            results = [t for t in results if t.timestamp >= since]

        return results[-limit:]

    def count(self) -> int:
        return len(self._tokens)

    def clear(self) -> None:
        self._tokens = []
        self._index = {}


class FileStore(TokenStore):
    """
    File-based token storage (JSONL).

    Append-only, persistent, audit-friendly.
    Good for: production, compliance, long-term audit trails.
    """

    def __init__(self, path: str):
        """
        Initialize file store.

        Args:
            path: Path to JSONL file
        """
        self.path = Path(path)
        self._cache: List[Token] = []
        self._index: dict[str, int] = {}
        self._load()

    def _load(self):
        """Load existing tokens from file."""
        if self.path.exists():
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        token = Token.from_json(line)
                        self._index[token.token_id] = len(self._cache)
                        self._cache.append(token)

    def add(self, token: Token) -> None:
        # Append to file
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(token.to_json() + "\n")

        # Update cache
        self._index[token.token_id] = len(self._cache)
        self._cache.append(token)

    def get(self, token_id: str) -> Optional[Token]:
        idx = self._index.get(token_id)
        return self._cache[idx] if idx is not None else None

    def all(self) -> List[Token]:
        return list(self._cache)

    def find(
        self,
        action: Optional[str] = None,
        actor: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 100
    ) -> List[Token]:
        results = self._cache

        if action:
            results = [t for t in results if t.action == action]
        if actor:
            results = [t for t in results if t.actor == actor]
        if since:
            results = [t for t in results if t.timestamp >= since]

        return results[-limit:]

    def count(self) -> int:
        return len(self._cache)

    def clear(self) -> None:
        """Clear all tokens (rewrites file)."""
        self._cache = []
        self._index = {}
        self.path.write_text("")

    def verify_file(self) -> dict:
        """
        Verify all tokens in file.

        Returns:
            Dict with valid/invalid counts and any corrupted IDs
        """
        valid = 0
        invalid = []

        for token in self._cache:
            if token.verify():
                valid += 1
            else:
                invalid.append(token.token_id)

        return {
            "valid": valid,
            "invalid": len(invalid),
            "corrupted_ids": invalid,
            "integrity": len(invalid) == 0
        }
