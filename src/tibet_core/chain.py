"""
TIBET Chain - Provenance chain utilities.
"""

from typing import List, Optional, Dict, Any
from .token import Token
from .store import TokenStore


class Chain:
    """
    Provenance chain walker.

    Follow parent_id links to reconstruct full audit trail.

    Example:
        chain = Chain(store)

        # Get full history of a token
        history = chain.trace(token_id)
        for t in history:
            print(f"{t.timestamp}: {t.action} - {t.erachter}")

        # Verify chain integrity
        if chain.verify(token_id):
            print("Chain intact")
    """

    def __init__(self, store: TokenStore):
        """Initialize with token store."""
        self.store = store

    def trace(self, token_id: str, max_depth: int = 100) -> List[Token]:
        """
        Trace provenance chain backwards.

        Args:
            token_id: Starting token
            max_depth: Maximum chain length

        Returns:
            List of tokens from newest to oldest
        """
        chain = []
        current_id = token_id
        seen = set()

        while current_id and len(chain) < max_depth:
            if current_id in seen:
                break  # Circular reference protection
            seen.add(current_id)

            token = self.store.get(current_id)
            if token:
                chain.append(token)
                current_id = token.parent_id
            else:
                break

        return chain

    def verify(self, token_id: str) -> bool:
        """
        Verify entire chain integrity.

        Args:
            token_id: Starting token

        Returns:
            True if all tokens in chain have valid hashes
        """
        chain = self.trace(token_id)
        return all(t.verify() for t in chain)

    def summary(self, token_id: str) -> Dict[str, Any]:
        """
        Get chain summary.

        Args:
            token_id: Starting token

        Returns:
            Summary dict with stats and actors
        """
        chain = self.trace(token_id)

        if not chain:
            return {"length": 0, "valid": False}

        actors = set(t.actor for t in chain)
        actions = [t.action for t in chain]

        return {
            "length": len(chain),
            "valid": all(t.verify() for t in chain),
            "actors": list(actors),
            "actions": actions,
            "start": chain[-1].timestamp if chain else None,
            "end": chain[0].timestamp if chain else None,
            "root_id": chain[-1].token_id if chain else None,
        }

    def find_root(self, token_id: str) -> Optional[Token]:
        """Find root token of chain."""
        chain = self.trace(token_id)
        return chain[-1] if chain else None

    def find_children(self, token_id: str) -> List[Token]:
        """Find all tokens that reference this token as parent."""
        return [t for t in self.store.all() if t.parent_id == token_id]

    def tree(self, root_id: str, max_depth: int = 10) -> Dict[str, Any]:
        """
        Build tree from root token downwards.

        Args:
            root_id: Root token ID
            max_depth: Maximum depth

        Returns:
            Nested dict representing token tree
        """
        def build_node(token_id: str, depth: int) -> Dict[str, Any]:
            if depth > max_depth:
                return {"id": token_id, "truncated": True}

            token = self.store.get(token_id)
            if not token:
                return {"id": token_id, "missing": True}

            children = self.find_children(token_id)

            return {
                "id": token.token_id,
                "action": token.action,
                "actor": token.actor,
                "timestamp": token.timestamp,
                "erachter": token.erachter,
                "valid": token.verify(),
                "children": [build_node(c.token_id, depth + 1) for c in children]
            }

        return build_node(root_id, 0)
