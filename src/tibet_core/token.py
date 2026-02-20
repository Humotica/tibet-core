"""
TIBET Token - The atomic unit of provenance.

Each token captures:
- WHAT happened (erin)
- WHAT it relates to (eraan)
- WHERE/WHEN it happened (eromheen)
- WHY it happened (erachter)
"""

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class TokenState(Enum):
    """Token lifecycle states."""
    CREATED = "created"
    DETECTED = "detected"
    CLASSIFIED = "classified"
    MITIGATED = "mitigated"
    RESOLVED = "resolved"


@dataclass
class Token:
    """
    TIBET provenance token.

    Immutable record of an action with cryptographic integrity.

    Attributes:
        token_id: Unique identifier
        action: Type of action (e.g., "search", "login", "api_call")
        timestamp: ISO format creation time
        actor: Who/what performed the action (jis: identifier)

        erin: What's IN - the content/data of the action
        eraan: What's attached - references, dependencies
        eromheen: Context - environment, state, metadata
        erachter: Intent - why this action was taken

        parent_id: Parent token for chain linking
        state: Current lifecycle state
        content_hash: SHA-256 of token content
        signature: Optional cryptographic signature
    """
    token_id: str
    action: str
    timestamp: str
    actor: str

    # Dutch provenance semantics
    erin: Any = None
    eraan: List[str] = field(default_factory=list)
    eromheen: Dict[str, Any] = field(default_factory=dict)
    erachter: str = ""

    # Chain & state
    parent_id: Optional[str] = None
    state: TokenState = TokenState.CREATED

    # Integrity
    content_hash: str = ""
    signature: str = ""

    def __post_init__(self):
        """Compute content hash if not set."""
        if not self.content_hash:
            self.content_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute SHA-256 hash of token content."""
        data = {
            "token_id": self.token_id,
            "action": self.action,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "erin": self.erin,
            "eraan": self.eraan,
            "eromheen": self.eromheen,
            "erachter": self.erachter,
            "parent_id": self.parent_id,
            "state": self.state.value if isinstance(self.state, TokenState) else self.state,
        }
        content = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()

    def verify(self) -> bool:
        """Verify token integrity by recomputing hash."""
        return self.content_hash == self._compute_hash()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        d = asdict(self)
        d["state"] = self.state.value if isinstance(self.state, TokenState) else self.state
        return d

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Token":
        """Create token from dictionary."""
        if "state" in data and isinstance(data["state"], str):
            data["state"] = TokenState(data["state"])
        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> "Token":
        """Create token from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def __repr__(self) -> str:
        return f"Token({self.action}, actor={self.actor}, id={self.token_id[:8]}...)"


def create_token_id(prefix: str = "tibet") -> str:
    """Generate unique token ID."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    random_part = hashlib.sha256(f"{timestamp}{id(object())}".encode()).hexdigest()[:8]
    return f"{prefix}_{timestamp}_{random_part}"
