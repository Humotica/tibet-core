# Changelog — `tibet-core`

All notable changes to this package. Versions follow SemVer; pre-releases use `aN` (alpha) and `bN` (beta) suffixes.

## 0.5.0b2 — 2026-05-28 (later same day)

### Added
- **`register_emit_hook(fn)`** + **`clear_emit_hooks()`** — loose-coupling observer-hook called after each `Session.emit()`. Soft-fail (an exception in a hook never breaks the emit). Lets `tibet-cap-bus` project OSAPI-emits onto the `gateway-event.v1` log without `tibet-core` taking a dep on `tibet-cap-bus`. Zero-deps invariant preserved.
- Hook fires for both server-bound and soft-bootstrap emits.
- Bridge available in `tibet-cap-bus.tibet_core_bridge.install_tibet_core_hook()` (in `tibet-cap-bus >= 0.1.2`).

### Non-breaking
- `Session.emit()` signature unchanged; behavior is the same plus the post-call hook fan-out.

## 0.5.0b1 — 2026-05-28

The fork → main move. `tibet-core` graduates from "Provider library" to **OSAPI service** — packages now bind to a central runtime instead of spawning independent Provider instances.

### Added
- **OSAPI v1.0 — bootstrap handshake** (`HELLO/WELCOME/ACK` over line-delimited JSON, UDS + TCP transports)
- **`bootstrap(actor, actor_claim, ...)`** client API → returns a `Session`
- **`Session.emit(action, ...)`** — append-to-chain via the OSAPI
- **`Session.query(action=, actor=, since=, limit=)`** — read tokens from the shared chain
- **`Session.fork(parent_token, actor_to)`** — fork-token for multi-actor continuation
- **`OSAPIServer`** reference implementation (threaded, request-response per op)
- **Error hierarchy**: `OSAPIError` → `BootstrapError` / `IdentityError` / `VersionError` / `ProtocolError`
- **`TIBET_SOFT_BOOTSTRAP=1`** opt-out env-var for dev/test (degrades to local ephemeral Provider with loud warning)
- **Discovery**: env-var `TIBET_OSAPI_URL` → well-known UDS → TCP fallback (`127.0.0.1:18443`)
- **24 new tests** (11 handshake + 13 ops)
- Spec: [`docs/specs/osapi-protocol-v1.md`](../../docs/specs/osapi-protocol-v1.md)

### Discipline
- **No-fail-open**: OSAPI unreachable = `BootstrapError`, not silent degrade. Soft-bootstrap only when explicitly opted-in.
- **Zero-deps invariant preserved** — stdlib only for the OSAPI module.
- **Pair-companion**: [`jis-core 0.4.0b1`](https://pypi.org/project/jis-core/) released in tandem (port 18444, `claim`/`bind`/`fira`).

### v1.0 release-criteria progress
- [x] HELLO/WELCOME/ACK handshake + tests
- [x] emit/query/fork ops + tests
- [x] `TIBET_SOFT_BOOTSTRAP=1` opt-out tested end-to-end
- [ ] Heartbeat + missed-heartbeat detection (v0.5.0b2)
- [ ] Soft-stop publisher (v0.5.0rc1)
- [ ] Chain-marker `possible-breach` semantics (v0.5.0rc1)
- [ ] `tibet-pol` template `osapi-bootstrap.json` (cross-package)
- [ ] `snaft` rule R-001 (cross-package)
- [ ] `tibet-conformance-vectors` OSAPI roundtrip vectors

## 0.4.0 — 2026-03-xx

- Fork tokens (multi-actor process continuation)
- `mcp-server-tibet-core` published — TIBET everywhere gap filled
- Gitignore reorganization for sub-projects

## 0.x — Earlier

See git log: provenance kernel, Token + Chain + Provider + Store + NetworkBridge.
