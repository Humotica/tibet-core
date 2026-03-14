"""Tests for tibet_core.bridge — NetworkBridge."""

from datetime import datetime

import pytest

from tibet_core import Provider, NetworkBridge, Token


class TestRecordPing:
    def test_ping_dict(self):
        p = Provider(actor="jis:hub")
        bridge = NetworkBridge(p)
        packet = {
            "source_did": "jis:laptop:jasper",
            "target_did": "jis:dl360:hub",
            "ping_type": "heartbeat",
            "purpose": "Check alive",
            "intent": "keepalive",
            "routing_mode": "direct",
            "hop_count": 0,
        }
        t = bridge.record_ping(packet)
        assert t.action == "ping.heartbeat"
        assert t.actor == "jis:laptop:jasper"
        assert "jis:dl360:hub" in t.eraan
        assert t.verify()

    def test_ping_with_response(self):
        p = Provider(actor="jis:hub")
        bridge = NetworkBridge(p)
        packet = {
            "source_did": "jis:a",
            "target_did": "jis:b",
            "ping_type": "ping",
            "purpose": "Hello",
        }
        response = {
            "decision": "accept",
            "trust_score": 0.85,
            "zone": "GROEN",
        }
        t = bridge.record_ping(packet, response)
        assert t.eromheen["decision"] == "accept"
        assert t.eromheen["trust_score"] == 0.85

    def test_ping_auto_chain(self):
        p = Provider(actor="jis:hub")
        bridge = NetworkBridge(p)
        t1 = bridge.record_ping({"source_did": "a", "target_did": "b", "ping_type": "ping"})
        t2 = bridge.record_ping({"source_did": "a", "target_did": "b", "ping_type": "pong"})
        # Bridge maintains its own chain
        assert t2.parent_id == t1.token_id


class TestRecordHeartbeat:
    def test_heartbeat_basic(self):
        p = Provider(actor="jis:hub")
        bridge = NetworkBridge(p)
        t = bridge.record_heartbeat("jis:sensor:temp1")
        assert t.action == "heartbeat"
        assert t.erin["source"] == "jis:sensor:temp1"
        assert t.verify()

    def test_heartbeat_with_addr(self):
        p = Provider(actor="jis:hub")
        bridge = NetworkBridge(p)
        t = bridge.record_heartbeat("jis:sensor:temp1", addr=("192.168.1.50", 7150))
        assert t.eromheen["host"] == "192.168.1.50"
        assert t.eromheen["port"] == 7150

    def test_heartbeat_with_status(self):
        p = Provider(actor="jis:hub")
        bridge = NetworkBridge(p)
        t = bridge.record_heartbeat("jis:sensor:temp1", status="healthy")
        assert t.erin["status"] == "healthy"


class TestRecordDiscovery:
    def test_discovery_basic(self):
        p = Provider(actor="jis:hub")
        bridge = NetworkBridge(p)
        t = bridge.record_discovery("jis:new:device", ("192.168.1.99", 7150), "accepted")
        assert t.action == "discovery"
        assert t.erin["discovered_did"] == "jis:new:device"
        assert t.erin["decision"] == "accepted"
        assert t.eromheen["host"] == "192.168.1.99"
        assert t.verify()


class TestRecordRelay:
    def test_relay_dict(self):
        p = Provider(actor="jis:hub")
        bridge = NetworkBridge(p)
        packet = {
            "source_did": "jis:a",
            "target_did": "jis:c",
            "hop_count": 1,
        }
        t = bridge.record_relay(packet, forwarded_to=("192.168.1.10", 7150))
        assert t.action == "relay"
        assert t.erin["source_did"] == "jis:a"
        assert t.erin["hop_count"] == 1
        assert t.eromheen["forwarded_host"] == "192.168.1.10"
        assert t.verify()

    def test_relay_without_forward(self):
        p = Provider(actor="jis:hub")
        bridge = NetworkBridge(p)
        packet = {"source_did": "jis:a", "target_did": "jis:b", "hop_count": 0}
        t = bridge.record_relay(packet)
        assert "forwarded_host" not in t.eromheen


class TestRecordTrustChange:
    def test_trust_increase(self):
        p = Provider(actor="jis:hub")
        bridge = NetworkBridge(p)
        t = bridge.record_trust_change("jis:device:x", 0.5, 0.9, "Vouched by admin")
        assert t.action == "trust_change"
        assert t.erin["old_trust"] == 0.5
        assert t.erin["new_trust"] == 0.9
        assert t.erin["old_zone"] == "GEEL"
        assert t.erin["new_zone"] == "GROEN"
        assert t.eromheen["zone_changed"] is True
        assert t.verify()

    def test_trust_same_zone(self):
        p = Provider(actor="jis:hub")
        bridge = NetworkBridge(p)
        t = bridge.record_trust_change("jis:device:x", 0.8, 0.9)
        assert t.erin["old_zone"] == "GROEN"
        assert t.erin["new_zone"] == "GROEN"
        assert t.eromheen["zone_changed"] is False

    def test_trust_rood(self):
        p = Provider(actor="jis:hub")
        bridge = NetworkBridge(p)
        t = bridge.record_trust_change("jis:device:x", 0.5, 0.1, "Suspicious activity")
        assert t.erin["new_zone"] == "ROOD"
        assert "Suspicious activity" in t.erachter


class TestBridgeChaining:
    def test_full_chain(self):
        p = Provider(actor="jis:hub")
        bridge = NetworkBridge(p)

        t1 = bridge.record_discovery("jis:new", ("10.0.0.1", 7150), "accepted")
        t2 = bridge.record_trust_change("jis:new", 0.0, 0.5, "Initial trust")
        t3 = bridge.record_heartbeat("jis:new")
        t4 = bridge.record_ping({"source_did": "jis:new", "target_did": "jis:hub", "ping_type": "ping"})

        assert t2.parent_id == t1.token_id
        assert t3.parent_id == t2.token_id
        assert t4.parent_id == t3.token_id

    def test_dict_fallback(self):
        """Bridge works entirely with dicts, no tibet-ping dependency needed."""
        p = Provider(actor="jis:hub")
        bridge = NetworkBridge(p)

        t = bridge.record_ping({
            "source_did": "jis:sensor",
            "target_did": "jis:hub",
            "ping_type": "beacon",
            "purpose": "I exist",
            "intent": "announce",
        })
        assert t.action == "ping.beacon"
        assert t.verify()
