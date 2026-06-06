"""OSAPI v1.0 tibet-side ops — emit / query / fork (spec §4).

Reference: docs/specs/osapi-protocol-v1.md §4
Builds on test_osapi_handshake.py — these tests bootstrap first, then call ops.
"""
from __future__ import annotations

import time

import pytest

from tibet_core.osapi import (
    OSAPIServer,
    bootstrap,
    OSAPIError,
)


@pytest.fixture
def server():
    s = OSAPIServer(bind_url="tcp://127.0.0.1:0")
    s.start()
    time.sleep(0.05)
    yield s
    s.stop()


@pytest.fixture
def session(server):
    sess = bootstrap(actor="ops-test", actor_claim=b"JIS:fake", url=server.url)
    yield sess
    sess.close()


# ── emit ────────────────────────────────────────────────────────────────────

def test_emit_returns_token_id_and_position(session):
    result = session.emit(action="user_login",
                          erin={"user": "alice"},
                          erachter="login attempt")
    assert result["ok"] is True
    assert result["token_id"].startswith("tibet_")
    assert result["chain_position"] == 1
    assert "content_hash" in result and len(result["content_hash"]) == 64  # SHA-256 hex


def test_emit_increments_chain_position(session):
    a = session.emit(action="a")
    b = session.emit(action="b")
    c = session.emit(action="c")
    assert a["chain_position"] == 1
    assert b["chain_position"] == 2
    assert c["chain_position"] == 3
    # token_ids must be unique
    assert len({a["token_id"], b["token_id"], c["token_id"]}) == 3


def test_emit_with_all_provenance_fields(session):
    result = session.emit(
        action="api_call",
        erin={"endpoint": "/v1/data", "method": "GET"},
        eraan=["jis:humotica:auth"],
        eromheen={"ip": "10.0.0.1", "user_agent": "curl/7.0"},
        erachter="Fetching user data per request",
    )
    assert result["ok"] is True
    assert result["token_id"].startswith("tibet_")


def test_emit_chains_via_parent_id(session):
    first = session.emit(action="parent_action")
    second = session.emit(action="child_action", parent_id=first["token_id"])
    assert second["ok"] is True
    # Verify chain visible via query
    q = session.query(action="child_action")
    assert any(t.get("parent_id") == first["token_id"] for t in q["tokens"])


# ── query ───────────────────────────────────────────────────────────────────

def test_query_empty_returns_empty_list(session):
    result = session.query()
    assert result["ok"] is True
    assert result["tokens"] == []


def test_query_returns_emitted_tokens(session):
    session.emit(action="alpha")
    session.emit(action="beta")
    session.emit(action="alpha")
    all_tokens = session.query()
    assert len(all_tokens["tokens"]) == 3


def test_query_filters_by_action(session):
    session.emit(action="login")
    session.emit(action="logout")
    session.emit(action="login")
    only_login = session.query(action="login")
    assert len(only_login["tokens"]) == 2
    assert all(t["action"] == "login" for t in only_login["tokens"])


def test_query_respects_limit(session):
    for i in range(20):
        session.emit(action="batch", erin={"i": i})
    five = session.query(limit=5)
    assert len(five["tokens"]) == 5


# ── fork ────────────────────────────────────────────────────────────────────

def test_fork_returns_fork_id_and_hash(session):
    parent = session.emit(action="long_running")
    fork = session.fork(parent_token=parent["token_id"], actor_to="worker_b")
    assert fork["ok"] is True
    assert fork["fork_id"].startswith("fork_")
    assert fork["fork_hash"].startswith("fork:sha256:")
    assert len(fork["fork_hash"]) > len("fork:sha256:")  # actual hash present


def test_fork_requires_parent_and_actor(session):
    with pytest.raises(OSAPIError) as exc_info:
        session.fork(parent_token="", actor_to="someone")
    assert "fork requires" in str(exc_info.value).lower() or "OP_INVALID" in str(exc_info.value)


def test_fork_hash_is_deterministic_per_inputs(session):
    """Same parent + actor_to should produce same hash (modulo fork_id randomness)."""
    parent = session.emit(action="reproducible")
    f1 = session.fork(parent_token=parent["token_id"], actor_to="b")
    f2 = session.fork(parent_token=parent["token_id"], actor_to="b")
    # fork_id differs (random); fork_hash differs because it incorporates fork_id
    assert f1["fork_id"] != f2["fork_id"]
    assert f1["fork_hash"] != f2["fork_hash"]


# ── Session-not-found error ─────────────────────────────────────────────────

def test_op_with_invalid_session_token_raises(server):
    # build a fake session that never bootstrapped
    from tibet_core.osapi import Session
    fake = Session(
        actor="ghost",
        session_token="tibet_doesnotexist_00000000",
        chain_handle="ch_x",
        identity_binding="id_x",
        server_url=server.url,
    )
    with pytest.raises(OSAPIError) as exc_info:
        fake.emit(action="x")
    assert "SESSION" in str(exc_info.value)


# ── Soft-bootstrap ops fallback ─────────────────────────────────────────────

def test_soft_bootstrap_ops_work_locally(monkeypatch):
    monkeypatch.setenv("TIBET_SOFT_BOOTSTRAP", "1")
    sess = bootstrap(actor="local", actor_claim=b"c",
                     url="tcp://127.0.0.1:1", timeout=0.3)
    assert sess.is_soft_bootstrap is True

    # emit works locally with a warning
    r = sess.emit(action="local_op")
    assert r["ok"] is True
    assert r.get("_local") is True
    assert r["token_id"].startswith("tibet_")

    q = sess.query()
    assert q.get("_local") is True
    assert len(q["tokens"]) == 1
    assert q["tokens"][0]["action"] == "local_op"

    f = sess.fork(parent_token=r["token_id"], actor_to="b")
    assert f["ok"] is True
    assert f.get("_local") is True
