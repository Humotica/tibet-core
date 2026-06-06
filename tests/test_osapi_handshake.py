"""OSAPI v1.0 handshake — roundtrip + error cases.

Reference: docs/specs/osapi-protocol-v1.md §3
"""
from __future__ import annotations

import json
import os
import socket
import time

import pytest

from tibet_core.osapi import (
    OSAPIServer,
    bootstrap,
    BootstrapError,
    IdentityError,
    VersionError,
    PROTOCOL_VERSION,
    SUPPORTED_VERSIONS,
)


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def server():
    s = OSAPIServer(bind_url="tcp://127.0.0.1:0")
    s.start()
    # tiny wait so accept-loop is ready
    time.sleep(0.05)
    yield s
    s.stop()


@pytest.fixture
def strict_server():
    """Server that only accepts claims starting with b'JIS:'."""
    def verifier(actor: str, claim: bytes) -> bool:
        return claim.startswith(b"JIS:")
    s = OSAPIServer(bind_url="tcp://127.0.0.1:0", claim_verifier=verifier)
    s.start()
    time.sleep(0.05)
    yield s
    s.stop()


# ── Happy path ──────────────────────────────────────────────────────────────

def test_handshake_roundtrip_succeeds(server):
    sess = bootstrap(
        actor="test-package",
        actor_claim=b"JIS:fake-but-shape-valid",
        url=server.url,
    )
    assert sess.actor == "test-package"
    assert sess.session_token.startswith("tibet_")
    assert sess.chain_handle.startswith("ch_")
    assert sess.identity_binding.startswith("id_")
    assert sess.is_soft_bootstrap is False
    assert sess.server_url == server.url
    sess.close()


def test_session_recorded_server_side(server):
    sess = bootstrap(actor="record-test", actor_claim=b"claim", url=server.url)
    # allow server thread to register the session after ACK
    time.sleep(0.1)
    assert sess.session_token in server._active_sessions
    info = server._active_sessions[sess.session_token]
    assert info["actor"] == "record-test"


# ── Identity errors ─────────────────────────────────────────────────────────

def test_empty_claim_raises_identity_error(server):
    with pytest.raises(IdentityError):
        bootstrap(actor="x", actor_claim=b"", url=server.url)


def test_non_bytes_claim_raises_identity_error(server):
    with pytest.raises(IdentityError):
        bootstrap(actor="x", actor_claim="string-not-bytes", url=server.url)  # type: ignore[arg-type]


def test_server_rejects_claim_via_verifier(strict_server):
    # claim does not start with b"JIS:" → server rejects
    with pytest.raises(IdentityError):
        bootstrap(actor="x", actor_claim=b"WRONG", url=strict_server.url)


def test_strict_verifier_accepts_valid_claim(strict_server):
    sess = bootstrap(actor="x", actor_claim=b"JIS:ok", url=strict_server.url)
    assert sess.session_token.startswith("tibet_")


# ── Version errors ──────────────────────────────────────────────────────────

def test_version_mismatch_raises(server):
    """Send a raw HELLO with v=0.9 and verify the server emits VERSION error."""
    host, port = server.url.replace("tcp://", "").split(":")
    sock = socket.create_connection((host, int(port)), timeout=2.0)
    sock.sendall((json.dumps({
        "kind": "HELLO",
        "v": "0.9",
        "actor": "x",
        "actor_claim": "deadbeef",
        "capabilities": ["emit"],
        "pid": os.getpid(),
        "encoding": "ldjson",
    }) + "\n").encode())
    data = b""
    while b"\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    sock.close()
    msg = json.loads(data.split(b"\n", 1)[0])
    assert msg["kind"] == "ERROR"
    assert msg["code"] == "VERSION"


# ── Soft-bootstrap fallback ─────────────────────────────────────────────────

def test_soft_bootstrap_falls_back_on_unreachable(monkeypatch):
    """With TIBET_SOFT_BOOTSTRAP=1, an unreachable OSAPI returns a SoftSession."""
    monkeypatch.setenv("TIBET_SOFT_BOOTSTRAP", "1")
    sess = bootstrap(
        actor="lonely-pkg",
        actor_claim=b"claim",
        url="tcp://127.0.0.1:1",   # port 1 ≠ anything = refused
        timeout=0.5,
    )
    assert sess.is_soft_bootstrap is True
    assert sess.session_token.startswith("tibet_")
    assert sess.chain_handle == "local:ephemeral"


def test_unreachable_raises_without_soft_bootstrap(monkeypatch):
    monkeypatch.delenv("TIBET_SOFT_BOOTSTRAP", raising=False)
    with pytest.raises(BootstrapError):
        bootstrap(actor="lonely-pkg", actor_claim=b"claim",
                  url="tcp://127.0.0.1:1", timeout=0.5)


# ── Protocol invariants ─────────────────────────────────────────────────────

def test_supported_versions_includes_protocol_version():
    assert PROTOCOL_VERSION in SUPPORTED_VERSIONS


def test_server_url_resolves_to_concrete_port():
    """bind_url 'tcp://127.0.0.1:0' must resolve to a real port after start()."""
    s = OSAPIServer(bind_url="tcp://127.0.0.1:0")
    s.start()
    try:
        assert s.url.startswith("tcp://127.0.0.1:")
        _, port = s.url.replace("tcp://", "").split(":")
        assert int(port) > 0
    finally:
        s.stop()
