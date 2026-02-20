"""
TIBET Provider - Factory for creating and managing tokens.
"""

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .token import Token, TokenState, create_token_id
from .store import MemoryStore, TokenStore


class Provider:
    """
    TIBET token provider.

    Creates tokens with consistent actor identity and optional persistence.

    Example:
        tibet = Provider(actor="jis:humotica:my_app")

        # Simple action
        token = tibet.create("user_login", erin={"user": "alice"})

        # With full provenance
        token = tibet.create(
            action="api_call",
            erin={"endpoint": "/users", "method": "GET"},
            eraan=["jis:humotica:user_service"],
            eromheen={"ip": "192.168.1.1", "session": "abc123"},
            erachter="Fetch user list for admin dashboard"
        )
    """

    def __init__(
        self,
        actor: str,
        store: Optional[TokenStore] = None,
        on_token: Optional[Callable[[Token], None]] = None,
        auto_chain: bool = True
    ):
        """
        Initialize provider.

        Args:
            actor: Default actor identity (jis: format recommended)
            store: Token storage backend (default: MemoryStore)
            on_token: Callback for each created token
            auto_chain: Automatically link sequential tokens
        """
        self.actor = actor
        self.store = store or MemoryStore()
        self.on_token = on_token
        self.auto_chain = auto_chain
        self._last_token_id: Optional[str] = None

    def create(
        self,
        action: str,
        erin: Any = None,
        eraan: Optional[List[str]] = None,
        eromheen: Optional[Dict[str, Any]] = None,
        erachter: str = "",
        actor: Optional[str] = None,
        parent_id: Optional[str] = None,
        state: TokenState = TokenState.CREATED
    ) -> Token:
        """
        Create a new TIBET token.

        Args:
            action: Type of action being recorded
            erin: Content/data of the action
            eraan: References and dependencies
            eromheen: Context and environment
            erachter: Intent/reason for action
            actor: Override default actor
            parent_id: Explicit parent (overrides auto_chain)
            state: Initial token state

        Returns:
            Created token with computed hash
        """
        # Auto-chain if enabled and no explicit parent
        if parent_id is None and self.auto_chain and self._last_token_id:
            parent_id = self._last_token_id

        token = Token(
            token_id=create_token_id(),
            action=action,
            timestamp=datetime.now().isoformat(),
            actor=actor or self.actor,
            erin=erin,
            eraan=eraan or [],
            eromheen=eromheen or {},
            erachter=erachter,
            parent_id=parent_id,
            state=state
        )

        # Store token
        self.store.add(token)
        self._last_token_id = token.token_id

        # Callback
        if self.on_token:
            self.on_token(token)

        return token

    def update_state(
        self,
        token_id: str,
        new_state: TokenState,
        reason: str = ""
    ) -> Optional[Token]:
        """
        Update token state (creates audit trail).

        Args:
            token_id: Token to update
            new_state: New state
            reason: Reason for state change

        Returns:
            State change token, or None if original not found
        """
        original = self.store.get(token_id)
        if not original:
            return None

        # Create state change token
        return self.create(
            action="state_change",
            erin={
                "token_id": token_id,
                "old_state": original.state.value,
                "new_state": new_state.value
            },
            eraan=[token_id],
            erachter=reason or f"State change: {original.state.value} -> {new_state.value}",
            parent_id=token_id
        )

    def get(self, token_id: str) -> Optional[Token]:
        """Get token by ID."""
        return self.store.get(token_id)

    def find(
        self,
        action: Optional[str] = None,
        actor: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 100
    ) -> List[Token]:
        """
        Find tokens matching criteria.

        Args:
            action: Filter by action type
            actor: Filter by actor
            since: Filter by timestamp (ISO format)
            limit: Maximum results

        Returns:
            Matching tokens
        """
        return self.store.find(action=action, actor=actor, since=since, limit=limit)

    def export(self, format: str = "dict") -> Any:
        """
        Export all tokens.

        Args:
            format: "dict", "json", or "jsonl"

        Returns:
            Tokens in requested format
        """
        tokens = self.store.all()

        if format == "dict":
            return [t.to_dict() for t in tokens]
        elif format == "json":
            import json
            return json.dumps([t.to_dict() for t in tokens], default=str, indent=2)
        elif format == "jsonl":
            return "\n".join(t.to_json() for t in tokens)
        else:
            raise ValueError(f"Unknown format: {format}")

    def verify_all(self) -> Dict[str, bool]:
        """Verify integrity of all tokens."""
        return {t.token_id: t.verify() for t in self.store.all()}

    def clear(self):
        """Clear all stored tokens."""
        self.store.clear()
        self._last_token_id = None

    @property
    def count(self) -> int:
        """Number of stored tokens."""
        return self.store.count()

    def __repr__(self) -> str:
        return f"Provider(actor={self.actor}, tokens={self.count})"
