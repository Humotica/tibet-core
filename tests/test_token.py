"""Tests for tibet_core.token — frozen Token with HMAC."""

import json
import time
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta

import pytest

from tibet_core.token import Token, TokenState, create_token_id, validate_timestamp, MAX_FUTURE_SECONDS


def _make_token(**kwargs):
    """Helper to create a token with defaults."""
    defaults = {
        "token_id": "test_001",
        "action": "test",
        "timestamp": datetime.now().isoformat(),
        "actor": "jis:test:actor",
    }
    defaults.update(kwargs)
    return Token(**defaults)


class TestTokenCreation:
    def test_basic_creation(self):
        t = _make_token()
        assert t.token_id == "test_001"
        assert t.action == "test"
        assert t.actor == "jis:test:actor"
        assert t.state == TokenState.CREATED

    def test_content_hash_auto_computed(self):
        t = _make_token()
        assert t.content_hash != ""
        assert len(t.content_hash) == 64  # SHA-256 hex

    def test_provenance_fields(self):
        t = _make_token(
            erin={"data": "test"},
            eraan=["ref1", "ref2"],
            eromheen={"env": "test"},
            erachter="Because testing"
        )
        assert t.erin == {"data": "test"}
        assert t.eraan == ["ref1", "ref2"]
        assert t.eromheen == {"env": "test"}
        assert t.erachter == "Because testing"

    def test_defaults(self):
        t = _make_token()
        assert t.erin is None
        assert t.eraan == []
        assert t.eromheen == {}
        assert t.erachter == ""
        assert t.parent_id is None
        assert t.signature == ""


class TestFrozen:
    def test_frozen_immutability(self):
        t = _make_token()
        with pytest.raises(FrozenInstanceError):
            t.erin = "hacked"

    def test_frozen_action(self):
        t = _make_token()
        with pytest.raises(FrozenInstanceError):
            t.action = "tampered"

    def test_frozen_content_hash(self):
        t = _make_token()
        with pytest.raises(FrozenInstanceError):
            t.content_hash = "fake"


class TestHashing:
    def test_verify_sha256(self):
        t = _make_token()
        assert t.verify() is True

    def test_verify_detects_tamper(self):
        """A token with a wrong hash should fail verification."""
        t = Token(
            token_id="test_002",
            action="test",
            timestamp=datetime.now().isoformat(),
            actor="jis:test",
            content_hash="0000000000000000000000000000000000000000000000000000000000000000"
        )
        assert t.verify() is False

    def test_hmac_compute(self):
        key = b"secret_key_42"
        t = _make_token()
        hmac_hash = t._compute_hash(key)
        plain_hash = t._compute_hash()
        assert hmac_hash != plain_hash
        assert len(hmac_hash) == 64

    def test_hmac_verify(self):
        """Create token, recompute with HMAC, verify with same key."""
        key = b"my_secret"
        t = _make_token()
        hmac_hash = t._compute_hash(key)
        # Set hash via object.__setattr__ (simulating what Provider does)
        object.__setattr__(t, "content_hash", hmac_hash)
        assert t.verify(key) is True
        assert t.verify() is False  # Without key = mismatch
        assert t.verify(b"wrong_key") is False

    def test_deterministic_hash(self):
        ts = "2026-01-01T00:00:00"
        t1 = Token(token_id="a", action="x", timestamp=ts, actor="y")
        t2 = Token(token_id="a", action="x", timestamp=ts, actor="y")
        assert t1.content_hash == t2.content_hash


class TestSerialization:
    def test_to_dict(self):
        t = _make_token(erin="hello")
        d = t.to_dict()
        assert d["erin"] == "hello"
        assert d["state"] == "created"
        assert isinstance(d, dict)

    def test_to_json_roundtrip(self):
        t = _make_token(erin={"key": "value"}, eraan=["a", "b"])
        j = t.to_json()
        t2 = Token.from_json(j)
        assert t2.token_id == t.token_id
        assert t2.erin == t.erin
        assert t2.eraan == t.eraan
        assert t2.content_hash == t.content_hash

    def test_from_dict_state_string(self):
        d = {
            "token_id": "t1",
            "action": "a",
            "timestamp": "2026-01-01",
            "actor": "x",
            "state": "detected",
        }
        t = Token.from_dict(d)
        assert t.state == TokenState.DETECTED

    def test_unicode_content(self):
        t = _make_token(erin="日本語テスト 🎉", erachter="Ünïcödé")
        j = t.to_json()
        t2 = Token.from_json(j)
        assert t2.erin == "日本語テスト 🎉"
        assert t2.erachter == "Ünïcödé"
        assert t2.verify()

    def test_repr(self):
        t = _make_token()
        r = repr(t)
        assert "test" in r
        assert "test_001" in r


class TestTokenId:
    def test_create_token_id_format(self):
        tid = create_token_id()
        assert tid.startswith("tibet_")
        parts = tid.split("_")
        assert len(parts) == 3

    def test_create_token_id_unique(self):
        ids = {create_token_id() for _ in range(100)}
        assert len(ids) == 100

    def test_create_token_id_custom_prefix(self):
        tid = create_token_id(prefix="custom")
        assert tid.startswith("custom_")


class TestValidateTimestamp:
    def test_valid_now(self):
        assert validate_timestamp(datetime.now().isoformat()) is True

    def test_valid_past(self):
        past = (datetime.now() - timedelta(hours=1)).isoformat()
        assert validate_timestamp(past) is True

    def test_invalid_far_future(self):
        future = (datetime.now() + timedelta(minutes=5)).isoformat()
        assert validate_timestamp(future) is False

    def test_barely_valid_future(self):
        future = (datetime.now() + timedelta(seconds=30)).isoformat()
        assert validate_timestamp(future) is True

    def test_invalid_garbage(self):
        assert validate_timestamp("not-a-timestamp") is False
        assert validate_timestamp("") is False
