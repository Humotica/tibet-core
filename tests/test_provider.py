"""Tests for tibet_core.provider — Provider with context manager and network helpers."""

from datetime import datetime

import pytest

from tibet_core import Provider, Token, TokenState, MemoryStore


class TestProviderBasic:
    def test_create_token(self):
        p = Provider(actor="jis:test")
        t = p.create("login", erin={"user": "alice"})
        assert t.action == "login"
        assert t.actor == "jis:test"
        assert t.erin == {"user": "alice"}
        assert t.verify()

    def test_auto_chain(self):
        p = Provider(actor="jis:test")
        t1 = p.create("first")
        t2 = p.create("second")
        assert t2.parent_id == t1.token_id

    def test_no_auto_chain(self):
        p = Provider(actor="jis:test", auto_chain=False)
        t1 = p.create("first")
        t2 = p.create("second")
        assert t2.parent_id is None

    def test_explicit_parent(self):
        p = Provider(actor="jis:test")
        t1 = p.create("first")
        t2 = p.create("second")
        t3 = p.create("third", parent_id=t1.token_id)
        assert t3.parent_id == t1.token_id  # Explicit overrides auto

    def test_actor_override(self):
        p = Provider(actor="jis:default")
        t = p.create("action", actor="jis:override")
        assert t.actor == "jis:override"

    def test_count(self):
        p = Provider(actor="jis:test")
        assert p.count == 0
        p.create("a")
        p.create("b")
        assert p.count == 2


class TestProviderStore:
    def test_get_token(self):
        p = Provider(actor="jis:test")
        t = p.create("action")
        retrieved = p.get(t.token_id)
        assert retrieved is not None
        assert retrieved.token_id == t.token_id

    def test_get_missing(self):
        p = Provider(actor="jis:test")
        assert p.get("nonexistent") is None

    def test_find_by_action(self):
        p = Provider(actor="jis:test")
        p.create("login")
        p.create("logout")
        p.create("login")
        results = p.find(action="login")
        assert len(results) == 2

    def test_find_by_actor(self):
        p = Provider(actor="jis:test")
        p.create("action", actor="alice")
        p.create("action", actor="bob")
        p.create("action", actor="alice")
        results = p.find(actor="alice")
        assert len(results) == 2


class TestProviderStateChange:
    def test_update_state(self):
        p = Provider(actor="jis:test")
        t = p.create("incident")
        change = p.update_state(t.token_id, TokenState.DETECTED, "Alert triggered")
        assert change is not None
        assert change.action == "state_change"
        assert change.erin["old_state"] == "created"
        assert change.erin["new_state"] == "detected"

    def test_update_state_missing(self):
        p = Provider(actor="jis:test")
        result = p.update_state("nonexistent", TokenState.RESOLVED)
        assert result is None


class TestContextManager:
    def test_context_manager_basic(self):
        with Provider(actor="jis:test") as p:
            p.create("init")
            p.create("work")
        assert p.count == 2

    def test_context_manager_verify(self):
        with Provider(actor="jis:test") as p:
            t = p.create("action")
            assert t.verify()
        # After __exit__, verify_all was called (no exception = all valid)


class TestHMACProvider:
    def test_hmac_tokens(self):
        key = b"secret_42"
        p = Provider(actor="jis:test", hmac_key=key)
        t = p.create("secure_action")
        assert t.verify(key) is True
        assert t.verify() is False  # Without key = mismatch

    def test_hmac_verify_all(self):
        key = b"test_key"
        p = Provider(actor="jis:test", hmac_key=key)
        p.create("a")
        p.create("b")
        results = p.verify_all()
        assert all(results.values())


class TestCallback:
    def test_on_token_callback(self):
        received = []
        p = Provider(actor="jis:test", on_token=lambda t: received.append(t))
        p.create("a")
        p.create("b")
        assert len(received) == 2
        assert received[0].action == "a"


class TestExport:
    def test_export_dict(self):
        p = Provider(actor="jis:test")
        p.create("a")
        result = p.export("dict")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["action"] == "a"

    def test_export_json(self):
        import json
        p = Provider(actor="jis:test")
        p.create("a")
        result = p.export("json")
        parsed = json.loads(result)
        assert len(parsed) == 1

    def test_export_jsonl(self):
        p = Provider(actor="jis:test")
        p.create("a")
        p.create("b")
        result = p.export("jsonl")
        lines = result.strip().split("\n")
        assert len(lines) == 2

    def test_export_invalid(self):
        p = Provider(actor="jis:test")
        with pytest.raises(ValueError):
            p.export("xml")


class TestFromPacket:
    def test_from_packet_dict(self):
        p = Provider(actor="jis:test")
        packet = {
            "source_did": "jis:laptop:jasper",
            "target_did": "jis:dl360:hub",
            "ping_type": "heartbeat",
            "purpose": "Check alive",
            "intent": "keepalive",
            "routing_mode": "direct",
            "hop_count": 0,
        }
        t = p.from_packet(packet)
        assert t.action == "ping.heartbeat"
        assert t.actor == "jis:laptop:jasper"
        assert "jis:dl360:hub" in t.eraan
        assert t.eromheen["routing_mode"] == "direct"

    def test_from_packet_with_response_dict(self):
        p = Provider(actor="jis:test")
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
        t = p.from_packet(packet, response)
        assert t.eromheen["decision"] == "accept"
        assert t.eromheen["trust_score"] == 0.85
        assert t.eromheen["zone"] == "GROEN"


class TestRecordHeartbeat:
    def test_heartbeat_basic(self):
        p = Provider(actor="jis:test")
        t = p.record_heartbeat("jis:device:sensor1")
        assert t.action == "heartbeat"
        assert t.actor == "jis:device:sensor1"
        assert t.erin["source"] == "jis:device:sensor1"

    def test_heartbeat_with_status(self):
        p = Provider(actor="jis:test")
        t = p.record_heartbeat("jis:device:sensor1", status="healthy")
        assert t.erin["status"] == "healthy"
