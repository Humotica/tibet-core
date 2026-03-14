"""
TIBET NetworkBridge - Automatic Token creation from network events.

Bridges the gap between tibet-ping/tibet-iot network packets
and tibet-core provenance tokens. Every network event becomes
an immutable, verifiable audit record.

Usage:
    from tibet_core import Provider, NetworkBridge

    provider = Provider(actor="jis:my_node")
    bridge = NetworkBridge(provider)

    # Record a ping
    token = bridge.record_ping(packet, response)

    # Record discovery
    token = bridge.record_discovery("jis:new_device", ("192.168.1.50", 7150), "accepted")
"""

from typing import Any, Dict, List, Optional, Tuple

from .provider import Provider
from .token import Token


class NetworkBridge:
    """
    Bridge between network events and TIBET provenance tokens.

    Converts PingPackets, heartbeats, discovery events, relay operations,
    and trust changes into Tokens with correct ERIN/ERAAN/EROMHEEN/ERACHTER.

    Works with PingPacket objects (tibet-ping) or plain dicts (fallback).
    Auto-chains sequential events into a provenance trail.
    """

    def __init__(self, provider: Provider):
        """
        Initialize bridge.

        Args:
            provider: TIBET Provider for token creation
        """
        self.provider = provider
        self._last_token_id: Optional[str] = None

    def _chain_parent(self) -> Optional[str]:
        """Get parent_id for chaining sequential bridge events."""
        return self._last_token_id

    def _record(self, token: Token) -> Token:
        """Track last token for auto-chaining."""
        self._last_token_id = token.token_id
        return token

    def record_ping(self, packet, response=None) -> Token:
        """
        Record a ping event (request + optional response).

        Args:
            packet: PingPacket object or dict
            response: Optional PingResponse object or dict

        Returns:
            Token with ping provenance
        """
        # Use Provider.from_packet for the heavy lifting
        # But inject our chain parent
        old_last = self.provider._last_token_id
        if self._last_token_id:
            self.provider._last_token_id = self._last_token_id

        token = self.provider.from_packet(packet, response)

        # Restore provider's chain and update ours
        self.provider._last_token_id = old_last
        return self._record(token)

    def record_heartbeat(
        self,
        source_did: str,
        addr: Optional[Tuple[str, int]] = None,
        status: Optional[str] = None
    ) -> Token:
        """
        Record a heartbeat event.

        Args:
            source_did: Device sending heartbeat
            addr: Optional (host, port) tuple
            status: Optional status message

        Returns:
            Heartbeat token
        """
        erin = {"source": source_did}
        if status:
            erin["status"] = status

        eromheen = {}
        if addr:
            eromheen["host"] = addr[0]
            eromheen["port"] = addr[1]

        token = self.provider.create(
            action="heartbeat",
            erin=erin,
            eraan=[source_did],
            eromheen=eromheen,
            erachter=f"Heartbeat from {source_did}",
            actor=source_did,
            parent_id=self._chain_parent()
        )
        return self._record(token)

    def record_discovery(
        self,
        source_did: str,
        addr: Tuple[str, int],
        decision: str
    ) -> Token:
        """
        Record a discovery event (new device found on network).

        Args:
            source_did: DID of discovered device
            addr: (host, port) of discovered device
            decision: Discovery decision (accepted, rejected, pending)

        Returns:
            Discovery token
        """
        token = self.provider.create(
            action="discovery",
            erin={
                "discovered_did": source_did,
                "decision": decision,
            },
            eraan=[source_did],
            eromheen={
                "host": addr[0],
                "port": addr[1],
            },
            erachter=f"Discovered {source_did} at {addr[0]}:{addr[1]} — {decision}",
            parent_id=self._chain_parent()
        )
        return self._record(token)

    def record_relay(
        self,
        packet,
        forwarded_to: Optional[Tuple[str, int]] = None
    ) -> Token:
        """
        Record a mesh relay event.

        Args:
            packet: PingPacket object or dict being relayed
            forwarded_to: Optional (host, port) of relay target

        Returns:
            Relay token
        """
        if isinstance(packet, dict):
            source_did = packet.get("source_did", "unknown")
            target_did = packet.get("target_did", "unknown")
            hop_count = packet.get("hop_count", 0)
        else:
            source_did = getattr(packet, "source_did", "unknown")
            target_did = getattr(packet, "target_did", "unknown")
            hop_count = getattr(packet, "hop_count", 0)

        eromheen: Dict[str, Any] = {"hop_count": hop_count}
        if forwarded_to:
            eromheen["forwarded_host"] = forwarded_to[0]
            eromheen["forwarded_port"] = forwarded_to[1]

        token = self.provider.create(
            action="relay",
            erin={
                "source_did": source_did,
                "target_did": target_did,
                "hop_count": hop_count,
            },
            eraan=[source_did, target_did],
            eromheen=eromheen,
            erachter=f"Relaying packet from {source_did} to {target_did} (hop {hop_count})",
            parent_id=self._chain_parent()
        )
        return self._record(token)

    def record_trust_change(
        self,
        did: str,
        old_trust: float,
        new_trust: float,
        reason: str = ""
    ) -> Token:
        """
        Record a trust score change.

        Args:
            did: Device/agent whose trust changed
            old_trust: Previous trust score
            new_trust: New trust score
            reason: Why trust changed

        Returns:
            Trust change token
        """
        # Determine zone transitions
        def zone(score):
            if score >= 0.7:
                return "GROEN"
            elif score >= 0.3:
                return "GEEL"
            return "ROOD"

        old_zone = zone(old_trust)
        new_zone = zone(new_trust)

        erachter = reason or f"Trust change for {did}: {old_trust:.2f} -> {new_trust:.2f}"
        if old_zone != new_zone:
            erachter += f" (zone: {old_zone} -> {new_zone})"

        token = self.provider.create(
            action="trust_change",
            erin={
                "did": did,
                "old_trust": old_trust,
                "new_trust": new_trust,
                "old_zone": old_zone,
                "new_zone": new_zone,
            },
            eraan=[did],
            eromheen={
                "zone_changed": old_zone != new_zone,
            },
            erachter=erachter,
            parent_id=self._chain_parent()
        )
        return self._record(token)
