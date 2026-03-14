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

        # As context manager
        with Provider(actor="app") as p:
            p.create("init")
        # __exit__ runs verify_all()
    """

    def __init__(
        self,
        actor: str,
        store: Optional[TokenStore] = None,
        on_token: Optional[Callable[[Token], None]] = None,
        auto_chain: bool = True,
        hmac_key: Optional[bytes] = None
    ):
        """
        Initialize provider.

        Args:
            actor: Default actor identity (jis: format recommended)
            store: Token storage backend (default: MemoryStore)
            on_token: Callback for each created token
            auto_chain: Automatically link sequential tokens
            hmac_key: Optional HMAC key for token integrity
        """
        self.actor = actor
        self.store = store or MemoryStore()
        self.on_token = on_token
        self.auto_chain = auto_chain
        self.hmac_key = hmac_key
        self._last_token_id: Optional[str] = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit — verify all tokens."""
        self.verify_all()
        return False

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

        # If HMAC key set, recompute hash with key
        if self.hmac_key:
            hmac_hash = token._compute_hash(self.hmac_key)
            object.__setattr__(token, "content_hash", hmac_hash)

        # Store token
        self.store.add(token)
        self._last_token_id = token.token_id

        # Callback
        if self.on_token:
            self.on_token(token)

        return token

    def from_packet(self, packet, response=None) -> Token:
        """
        Create a Token from a PingPacket (tibet-ping).

        Maps PingPacket fields to TIBET provenance:
        - action: ping.{ping_type}
        - erin: {intent, purpose, payload}
        - eraan: [source_did, target_did]
        - eromheen: {routing_mode, hop_count, pod_id, ...}
        - erachter: packet.purpose

        Args:
            packet: PingPacket object or dict with packet fields
            response: Optional PingResponse — adds decision/trust info

        Returns:
            Token with full provenance from network event
        """
        # Support both PingPacket objects and plain dicts
        if isinstance(packet, dict):
            source_did = packet.get("source_did", "unknown")
            target_did = packet.get("target_did", "unknown")
            ping_type = packet.get("ping_type", "ping")
            purpose = packet.get("purpose", "")
            intent = packet.get("intent", "")
            payload = packet.get("payload")
            routing_mode = packet.get("routing_mode", "direct")
            hop_count = packet.get("hop_count", 0)
            pod_id = packet.get("pod_id")
        else:
            source_did = getattr(packet, "source_did", "unknown")
            target_did = getattr(packet, "target_did", "unknown")
            ping_type = getattr(packet, "ping_type", None)
            if ping_type is not None and hasattr(ping_type, "value"):
                ping_type = ping_type.value
            else:
                ping_type = str(ping_type) if ping_type else "ping"
            purpose = getattr(packet, "purpose", "")
            intent = getattr(packet, "intent", "")
            payload = getattr(packet, "payload", None)
            routing_mode = getattr(packet, "routing_mode", None)
            if routing_mode is not None and hasattr(routing_mode, "value"):
                routing_mode = routing_mode.value
            else:
                routing_mode = str(routing_mode) if routing_mode else "direct"
            hop_count = getattr(packet, "hop_count", 0)
            pod_id = getattr(packet, "pod_id", None)

        action = f"ping.{ping_type}"

        erin = {"intent": intent, "purpose": purpose}
        if payload is not None:
            erin["payload"] = payload

        eraan = [source_did, target_did]

        eromheen = {
            "routing_mode": routing_mode,
            "hop_count": hop_count,
        }
        if pod_id:
            eromheen["pod_id"] = pod_id

        erachter = purpose or f"Ping from {source_did} to {target_did}"

        # Add response info if available
        if response is not None:
            if isinstance(response, dict):
                decision = response.get("decision", "unknown")
                trust_score = response.get("trust_score", 0.0)
                zone = response.get("zone", "unknown")
            else:
                decision = getattr(response, "decision", None)
                if decision is not None and hasattr(decision, "value"):
                    decision = decision.value
                else:
                    decision = str(decision) if decision else "unknown"
                trust_score = getattr(response, "trust_score", 0.0)
                zone = getattr(response, "zone", None)
                if zone is not None and hasattr(zone, "value"):
                    zone = zone.value
                else:
                    zone = str(zone) if zone else "unknown"

            eromheen["decision"] = decision
            eromheen["trust_score"] = trust_score
            eromheen["zone"] = zone

        return self.create(
            action=action,
            erin=erin,
            eraan=eraan,
            eromheen=eromheen,
            erachter=erachter,
            actor=source_did
        )

    def record_heartbeat(self, source_did: str, status: Optional[str] = None) -> Token:
        """
        Record a heartbeat event.

        Args:
            source_did: Device/agent sending the heartbeat
            status: Optional status message

        Returns:
            Heartbeat token
        """
        erin = {"source": source_did}
        if status:
            erin["status"] = status

        return self.create(
            action="heartbeat",
            erin=erin,
            eraan=[source_did],
            erachter=f"Heartbeat from {source_did}",
            actor=source_did
        )

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
        key = self.hmac_key
        return {t.token_id: t.verify(key) for t in self.store.all()}

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
