"""
tibet-core OSAPI — bootstrap handshake (v1.0 protocol, §3).

Reference: docs/specs/osapi-protocol-v1.md

Scope of this module (v0.5.0a1):
  - HELLO / WELCOME / ACK handshake over line-delimited JSON
  - UDS + TCP transport
  - TIBET_OSAPI_URL discovery + TIBET_SOFT_BOOTSTRAP fallback
  - Minimal OSAPI server (reference implementation for tests + dev)
  - Error types per spec (BootstrapError, IdentityError, VersionError, ProtocolError)

NOT in this module yet (v0.5.x roadmap):
  - emit/query/fork operations (§4) — Session is a handle only for now
  - heartbeat loop (§5)
  - soft-stop subscriber (§6)
  - chain-marker emission (§7)
  - actor_claim Ed25519 verification → delegated to jis-core OSAPI (we
    accept shape-valid claims here and mark verification as "deferred")

Zero-deps invariant preserved: stdlib only.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import socket
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .token import create_token_id, Token
from .provider import Provider

# ── Protocol constants ──────────────────────────────────────────────────────

PROTOCOL_VERSION = "1.0"
SUPPORTED_VERSIONS = ("1.0",)
DEFAULT_HEARTBEAT_INTERVAL_MS = 30_000
SOFT_STOP_TOPIC = "tibet.cap-bus.events"

DEFAULT_UDS_PATH = "/var/run/tibet/osapi.sock"
DEFAULT_TCP_HOST = "127.0.0.1"
DEFAULT_TCP_PORT = 18443


# ── Errors (per spec §3) ────────────────────────────────────────────────────

class OSAPIError(Exception):
    """Base for all OSAPI protocol errors."""


class BootstrapError(OSAPIError):
    """OSAPI unreachable, or handshake failed and no soft-bootstrap allowed."""


class IdentityError(OSAPIError):
    """actor_claim invalid (missing, malformed, or — at v1.0 — signature-failed)."""


class VersionError(OSAPIError):
    """Protocol-version mismatch; no compatible version negotiated."""


class ProtocolError(OSAPIError):
    """Malformed line, unexpected message kind, or sequence-violation."""


# ── URL parsing ─────────────────────────────────────────────────────────────

def _resolve_url(explicit: Optional[str]) -> str:
    """Discovery order (spec §2): explicit arg > env-var > well-known UDS > TCP fallback."""
    if explicit:
        return explicit
    env = os.environ.get("TIBET_OSAPI_URL")
    if env:
        return env
    if os.path.exists(DEFAULT_UDS_PATH):
        return f"unix://{DEFAULT_UDS_PATH}"
    return f"tcp://{DEFAULT_TCP_HOST}:{DEFAULT_TCP_PORT}"


def _connect(url: str, timeout: float = 5.0) -> socket.socket:
    """Open a socket to a URL of the form unix:///path or tcp://host:port (or host:port)."""
    if url.startswith("unix://"):
        path = url[len("unix://"):]
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(path)
        return s
    if url.startswith("tcp://"):
        url = url[len("tcp://"):]
    host, _, port = url.partition(":")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((host, int(port or DEFAULT_TCP_PORT)))
    return s


# ── Wire protocol (line-delimited JSON) ─────────────────────────────────────

def _send(sock: socket.socket, msg: dict) -> None:
    sock.sendall((json.dumps(msg) + "\n").encode("utf-8"))


def _recv_line(sock: socket.socket, max_bytes: int = 64 * 1024) -> dict:
    buf = bytearray()
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            raise ProtocolError("connection closed before line terminator")
        buf.extend(chunk)
        if b"\n" in buf:
            line, _ = bytes(buf).split(b"\n", 1)
            break
        if len(buf) > max_bytes:
            raise ProtocolError(f"line exceeds {max_bytes} bytes without terminator")
    try:
        return json.loads(line)
    except json.JSONDecodeError as e:
        raise ProtocolError(f"malformed JSON line: {e}") from None


def _ack_hmac(session_token: str) -> str:
    """Compute the ACK echo HMAC — proves the client received the WELCOME intact."""
    return hmac.new(session_token.encode("utf-8"), b"ack-echo", hashlib.sha256).hexdigest()


# ── Session handle (client-side, post-handshake) ────────────────────────────

@dataclass
class Session:
    actor: str
    session_token: str
    chain_handle: str
    identity_binding: str
    heartbeat_interval_ms: int = DEFAULT_HEARTBEAT_INTERVAL_MS
    soft_stop_topic: str = SOFT_STOP_TOPIC
    server_url: str = ""
    is_soft_bootstrap: bool = False
    _local_provider: Optional[Provider] = None     # populated only in soft-bootstrap mode

    # ── Operations (spec §4 tibet-OSAPI) ────────────────────────────────────

    def emit(self, action: str, *, erin: Any = None, eraan: Optional[list] = None,
             eromheen: Optional[dict] = None, erachter: str = "",
             parent_id: Optional[str] = None) -> dict:
        """Append a TIBET-token to the chain. Returns {token_id, chain_position}.

        After the OSAPI returns, all registered emit-hooks fire with
        (session, kwargs, result). Hooks are soft-fail (cap-bus, observers, etc.).
        """
        kwargs = {"action": action, "erin": erin, "eraan": eraan or [],
                  "eromheen": eromheen or {}, "erachter": erachter, "parent_id": parent_id}
        if self.is_soft_bootstrap:
            result = _local_emit(self, action, erin, eraan, eromheen, erachter, parent_id)
        else:
            result = _call_op(self, "emit", **kwargs)
        _fire_emit_hooks(self, kwargs, result)
        return result

    def query(self, *, action: Optional[str] = None, actor: Optional[str] = None,
              since: Optional[str] = None, limit: int = 100) -> dict:
        """Read tokens from the chain with filters. Returns {tokens: [...], next_cursor}."""
        if self.is_soft_bootstrap:
            return _local_query(self, action, actor, since, limit)
        return _call_op(self, "query", action=action, actor=actor, since=since, limit=limit)

    def fork(self, *, parent_token: str, actor_to: str) -> dict:
        """Create a fork-token for multi-actor continuation. Returns {fork_id, fork_hash}."""
        if self.is_soft_bootstrap:
            return _local_fork(self, parent_token, actor_to)
        return _call_op(self, "fork", parent_token=parent_token, actor_to=actor_to)

    def close(self) -> None:
        """v0.5.x: no-op. v0.6.x: send BYE, stop heartbeat thread."""
        pass


# ── Emit-hook registry (loose-coupling for cap-bus / observers) ─────────────
# tibet-core stays zero-deps. tibet-cap-bus (or any observer) can register a
# callback that fires after each Session.emit() with (session, kwargs, result).
# Hooks are soft-fail: an exception in a hook never breaks the emit.

_post_emit_hooks: list = []


def register_emit_hook(fn) -> None:
    """Register a callback called after each successful Session.emit().

    Signature: `fn(session: Session, emit_kwargs: dict, result: dict) -> None`
    Used by tibet-cap-bus to project OSAPI emits onto the gateway-event.v1 log.
    Hooks are global to the process. Exceptions are caught and silenced.
    """
    if fn not in _post_emit_hooks:
        _post_emit_hooks.append(fn)


def clear_emit_hooks() -> None:
    """Remove all registered hooks (mainly for tests)."""
    _post_emit_hooks.clear()


def _fire_emit_hooks(session, kwargs: dict, result: dict) -> None:
    for hook in list(_post_emit_hooks):
        try:
            hook(session, kwargs, result)
        except Exception:
            pass   # soft-fail; never break emit on observer failure


# ── Op-call helper (request-response per op over a fresh socket) ────────────

def _call_op(session: "Session", op: str, **payload: Any) -> dict:
    """Open socket, send OP-message, get response, close.

    Request-response per op is the v0.5.0b1-alpha design: simple, debuggable,
    no socket-lifetime issues. Persistent connections + multiplexing come in v0.6.x.
    """
    sock = _connect(session.server_url)
    try:
        msg = {"kind": "OP", "op": op, "session_token": session.session_token}
        # filter None values to keep wire-shape compact
        msg.update({k: v for k, v in payload.items() if v is not None})
        _send(sock, msg)
        resp = _recv_line(sock)
        if resp.get("kind") == "ERROR":
            code = resp.get("code", "PROTOCOL")
            detail = resp.get("detail", "")
            raise OSAPIError(f"{code}: {detail}")
        return resp
    finally:
        try:
            sock.close()
        except Exception:
            pass


# ── Local fallbacks for soft-bootstrap (TIBET_SOFT_BOOTSTRAP=1) ─────────────

def _local_emit(sess: "Session", action: str, erin, eraan, eromheen, erachter, parent_id) -> dict:
    if sess._local_provider is None:
        sess._local_provider = Provider(actor=sess.actor)
    token = sess._local_provider.create(
        action=action, erin=erin, eraan=eraan or [],
        eromheen=eromheen or {}, erachter=erachter, parent_id=parent_id,
    )
    return {"kind": "RESULT", "ok": True, "token_id": token.token_id,
            "chain_position": sess._local_provider.store.count(),
            "_local": True}


def _local_query(sess: "Session", action, actor, since, limit) -> dict:
    if sess._local_provider is None:
        return {"kind": "RESULT", "ok": True, "tokens": [], "next_cursor": None, "_local": True}
    tokens = sess._local_provider.store.find(action=action, actor=actor, since=since, limit=limit)
    return {"kind": "RESULT", "ok": True,
            "tokens": [t.to_dict() for t in tokens],
            "next_cursor": None, "_local": True}


def _local_fork(sess: "Session", parent_token: str, actor_to: str) -> dict:
    fork_id = f"fork_{secrets.token_hex(8)}"
    fork_hash = hashlib.sha256(f"{parent_token}:{actor_to}:{fork_id}".encode()).hexdigest()
    return {"kind": "RESULT", "ok": True, "fork_id": fork_id,
            "fork_hash": f"fork:sha256:{fork_hash}", "_local": True}


# ── Soft-bootstrap (TIBET_SOFT_BOOTSTRAP=1) ─────────────────────────────────

def _soft_bootstrap(actor: str, reason: str) -> Session:
    """Degrade to ephemeral local Provider with a LOUD warning to stderr (spec §2)."""
    print(
        f"[tibet-core] WARNING: TIBET_SOFT_BOOTSTRAP active — degraded to ephemeral. "
        f"actor={actor!r} reason={reason!r}. NOT bound to central chain. "
        f"This is for dev/test only; production must run with a live OSAPI.",
        file=sys.stderr,
    )
    ephemeral_token = create_token_id(prefix="tibet")
    return Session(
        actor=actor,
        session_token=ephemeral_token,
        chain_handle="local:ephemeral",
        identity_binding="local:ephemeral",
        is_soft_bootstrap=True,
    )


# ── Client: bootstrap() ─────────────────────────────────────────────────────

def bootstrap(
    actor: str,
    actor_claim: bytes,
    *,
    url: Optional[str] = None,
    capabilities: Optional[list[str]] = None,
    timeout: float = 5.0,
) -> Session:
    """Perform the three-message OSAPI handshake (spec §3) and return a Session.

    actor:        package/actor name (matches pyproject name by convention)
    actor_claim:  JIS-signed Ed25519 claim bytes (verification deferred to jis-core in v1.0)
    url:          override the discovery (otherwise: TIBET_OSAPI_URL env or default)
    capabilities: ops this package intends to use; ["emit", "query"] by default
    timeout:      socket timeout in seconds

    Raises BootstrapError / IdentityError / VersionError / ProtocolError on failure.
    Falls back to soft-bootstrap if TIBET_SOFT_BOOTSTRAP=1 and the OSAPI is unreachable.
    """
    if not isinstance(actor_claim, (bytes, bytearray)):
        raise IdentityError("actor_claim must be bytes (JIS-signed)")
    if not actor_claim:
        raise IdentityError("actor_claim is empty")

    resolved = _resolve_url(url)
    soft = os.environ.get("TIBET_SOFT_BOOTSTRAP") == "1"

    try:
        sock = _connect(resolved, timeout=timeout)
    except (OSError, socket.timeout) as e:
        if soft:
            return _soft_bootstrap(actor, reason=f"connect-failed: {e}")
        raise BootstrapError(f"cannot reach OSAPI at {resolved}: {e}") from None

    try:
        # HELLO
        _send(sock, {
            "kind": "HELLO",
            "v": PROTOCOL_VERSION,
            "actor": actor,
            "actor_claim": actor_claim.hex(),    # bytes → hex for line-protocol
            "capabilities": capabilities or ["emit", "query"],
            "pid": os.getpid(),
            "encoding": "ldjson",
        })

        # WELCOME (or ERROR)
        msg = _recv_line(sock)
        kind = msg.get("kind")
        if kind == "ERROR":
            code = msg.get("code", "PROTOCOL")
            detail = msg.get("detail", "")
            raise {
                "IDENTITY": IdentityError,
                "VERSION": VersionError,
            }.get(code, ProtocolError)(f"OSAPI rejected handshake: {code} — {detail}")
        if kind != "WELCOME":
            raise ProtocolError(f"expected WELCOME, got {kind!r}")

        version = msg.get("v")
        if version not in SUPPORTED_VERSIONS:
            raise VersionError(f"OSAPI advertised v={version!r}, client supports {SUPPORTED_VERSIONS}")

        session_token = msg["session_token"]

        # ACK
        _send(sock, {
            "kind": "ACK",
            "session_token": session_token,
            "echo": _ack_hmac(session_token),
        })

        return Session(
            actor=actor,
            session_token=session_token,
            chain_handle=msg["chain_handle"],
            identity_binding=msg["identity_binding"],
            heartbeat_interval_ms=msg.get("heartbeat_interval_ms", DEFAULT_HEARTBEAT_INTERVAL_MS),
            soft_stop_topic=msg.get("soft_stop_topic", SOFT_STOP_TOPIC),
            server_url=resolved,
        )
    finally:
        # v0.5.x: close after handshake. v0.6.x: keep alive for ops + heartbeat.
        try:
            sock.close()
        except Exception:
            pass


# ── Server (reference implementation; daemon-thread based) ──────────────────

ClaimVerifier = Callable[[str, bytes], bool]
"""(actor, claim_bytes) -> ok. v1.0 wires this to the real jis-core OSAPI."""


def _default_claim_verifier(actor: str, claim: bytes) -> bool:
    """v0.5.0 stub: accept any non-empty claim. v1.0: delegate to jis-OSAPI."""
    return len(claim) > 0


@dataclass
class OSAPIServer:
    """Reference OSAPI server — minimal, threaded, for tests + dev.

    Production: the real tibet-OSAPI daemon (separate package, v0.6.x).
    """

    bind_url: str = field(default_factory=lambda: f"tcp://{DEFAULT_TCP_HOST}:0")  # 0 = auto
    claim_verifier: ClaimVerifier = field(default=_default_claim_verifier)
    _sock: Optional[socket.socket] = None
    _thread: Optional[threading.Thread] = None
    _stop: threading.Event = field(default_factory=threading.Event)
    _bound_url: str = ""
    _active_sessions: dict[str, dict] = field(default_factory=dict)

    @property
    def url(self) -> str:
        """The actual bound URL (resolved after start() for auto-port TCP)."""
        return self._bound_url or self.bind_url

    def start(self) -> None:
        url = self.bind_url
        if url.startswith("unix://"):
            path = url[len("unix://"):]
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.bind(path)
            self._bound_url = f"unix://{path}"
        else:
            if url.startswith("tcp://"):
                url = url[len("tcp://"):]
            host, _, port = url.partition(":")
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, int(port or 0)))
            actual_port = s.getsockname()[1]
            self._bound_url = f"tcp://{host}:{actual_port}"

        s.listen(8)
        s.settimeout(0.5)  # so accept() can be interrupted by _stop
        self._sock = s
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _accept_loop(self) -> None:
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                conn, _addr = self._sock.accept()
            except (socket.timeout, OSError):
                continue
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn: socket.socket) -> None:
        """Dispatcher: HELLO → handshake, OP → operation, anything-else → ERROR."""
        try:
            conn.settimeout(5.0)
            try:
                first = _recv_line(conn)
            except ProtocolError as e:
                _send(conn, {"kind": "ERROR", "code": "PROTOCOL", "detail": str(e)})
                return

            kind = first.get("kind")
            if kind == "HELLO":
                self._handle_handshake(conn, first)
            elif kind == "OP":
                self._handle_op(conn, first)
            else:
                _send(conn, {"kind": "ERROR", "code": "PROTOCOL",
                             "detail": f"expected HELLO or OP, got {kind!r}"})
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _handle_handshake(self, conn: socket.socket, hello: dict) -> None:
        client_v = hello.get("v")
        if client_v not in SUPPORTED_VERSIONS:
            _send(conn, {"kind": "ERROR", "code": "VERSION",
                          "detail": f"server supports {list(SUPPORTED_VERSIONS)}, client offered {client_v!r}"})
            return

        actor = hello.get("actor") or ""
        claim_hex = hello.get("actor_claim") or ""
        try:
            claim = bytes.fromhex(claim_hex)
        except ValueError:
            _send(conn, {"kind": "ERROR", "code": "IDENTITY", "detail": "actor_claim not valid hex"})
            return

        if not actor or not self.claim_verifier(actor, claim):
            _send(conn, {"kind": "ERROR", "code": "IDENTITY", "detail": "claim verification failed"})
            return

        session_token = create_token_id(prefix="tibet")
        chain_handle = f"ch_{secrets.token_hex(8)}"
        identity_binding = f"id_{secrets.token_hex(8)}"

        _send(conn, {
            "kind": "WELCOME",
            "v": PROTOCOL_VERSION,
            "session_token": session_token,
            "chain_handle": chain_handle,
            "identity_binding": identity_binding,
            "heartbeat_interval_ms": DEFAULT_HEARTBEAT_INTERVAL_MS,
            "soft_stop_topic": SOFT_STOP_TOPIC,
            "supported_versions": list(SUPPORTED_VERSIONS),
        })

        try:
            ack = _recv_line(conn)
        except ProtocolError:
            return

        expected_echo = _ack_hmac(session_token)
        if ack.get("kind") != "ACK" or ack.get("echo") != expected_echo:
            return

        self._active_sessions[session_token] = {
            "actor": actor,
            "chain_handle": chain_handle,
            "identity_binding": identity_binding,
            "started_at": time.time(),
            "provider": Provider(actor=actor),   # one Provider per session — emit/query/fork use this
        }

    def _handle_op(self, conn: socket.socket, msg: dict) -> None:
        token = msg.get("session_token")
        sess = self._active_sessions.get(token) if token else None
        if not sess:
            _send(conn, {"kind": "ERROR", "code": "SESSION",
                         "detail": "unknown or expired session_token"})
            return

        op = msg.get("op")
        if op == "emit":
            self._op_emit(conn, sess, msg)
        elif op == "query":
            self._op_query(conn, sess, msg)
        elif op == "fork":
            self._op_fork(conn, sess, msg)
        else:
            _send(conn, {"kind": "ERROR", "code": "OP_UNKNOWN",
                         "detail": f"unknown op: {op!r}; supported: emit/query/fork"})

    # ── Op handlers (spec §4) ────────────────────────────────────────────────

    def _op_emit(self, conn: socket.socket, sess: dict, msg: dict) -> None:
        provider: Provider = sess["provider"]
        try:
            token = provider.create(
                action=msg.get("action") or "unknown",
                erin=msg.get("erin"),
                eraan=msg.get("eraan") or [],
                eromheen=msg.get("eromheen") or {},
                erachter=msg.get("erachter") or "",
                parent_id=msg.get("parent_id"),
            )
        except Exception as e:
            _send(conn, {"kind": "ERROR", "code": "OP_FAILED", "detail": f"emit: {e}"})
            return
        _send(conn, {
            "kind": "RESULT", "ok": True,
            "token_id": token.token_id,
            "chain_position": provider.store.count(),
            "content_hash": token.content_hash,
        })

    def _op_query(self, conn: socket.socket, sess: dict, msg: dict) -> None:
        provider: Provider = sess["provider"]
        try:
            tokens = provider.store.find(
                action=msg.get("action"),
                actor=msg.get("actor"),
                since=msg.get("since"),
                limit=int(msg.get("limit", 100)),
            )
        except Exception as e:
            _send(conn, {"kind": "ERROR", "code": "OP_FAILED", "detail": f"query: {e}"})
            return
        _send(conn, {
            "kind": "RESULT", "ok": True,
            "tokens": [t.to_dict() for t in tokens],
            "next_cursor": None,
        })

    def _op_fork(self, conn: socket.socket, sess: dict, msg: dict) -> None:
        parent = msg.get("parent_token") or ""
        actor_to = msg.get("actor_to") or ""
        if not parent or not actor_to:
            _send(conn, {"kind": "ERROR", "code": "OP_INVALID",
                         "detail": "fork requires parent_token + actor_to"})
            return
        fork_id = f"fork_{secrets.token_hex(8)}"
        fork_hash = hashlib.sha256(f"{parent}:{actor_to}:{fork_id}".encode()).hexdigest()
        _send(conn, {
            "kind": "RESULT", "ok": True,
            "fork_id": fork_id,
            "fork_hash": f"fork:sha256:{fork_hash}",
        })
