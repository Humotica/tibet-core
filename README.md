# tibet-core

**The Linux of AI Provenance**

[![PyPI](https://img.shields.io/pypi/v/tibet-core)](https://pypi.org/project/tibet-core/)
[![npm](https://img.shields.io/npm/v/tibet-core)](https://www.npmjs.com/package/tibet-core)
[![IETF Draft](https://img.shields.io/badge/IETF-draft--vandemeent--tibet--provenance-blue)](https://datatracker.ietf.org/doc/draft-vandemeent-tibet-provenance/)
[![Whitepaper](https://img.shields.io/badge/Zenodo-DOI:10.5281/zenodo.18712238-green)](https://doi.org/10.5281/zenodo.18712238)

Cryptographic provenance for trustworthy systems. Zero dependencies. Audit-ready.

From microcontrollers to cloud servers — every action gets an immutable, verifiable token.

## What is TIBET?

**T**oken-based **I**ntent, **B**ehavior, **E**vidence & **T**rust

TIBET captures the four dimensions of every action:

| Dimension | Dutch | Meaning |
|-----------|-------|---------|
| **ERIN** | "Er in" | What's IN the action (content, data) |
| **ERAAN** | "Er aan" | What's attached (dependencies, references) |
| **EROMHEEN** | "Er omheen" | Context around it (environment, state) |
| **ERACHTER** | "Er achter" | Intent behind it (why this action) |

## Installation

### Python (PyPI)
```bash
pip install tibet-core
```

### JavaScript/Node.js (npm) — Rust/WASM kernel
```bash
npm install tibet-core
```

### Rust
```toml
[dependencies]
tibet-core = "0.1"
```

## Quick Start

```python
from tibet_core import Provider, FileStore

# Create provider with persistent storage
tibet = Provider(
    actor="jis:humotica:my_app",
    store=FileStore("./audit.jsonl")
)

# Record any action with full provenance
token = tibet.create(
    action="user_login",
    erin={"user_id": "alice", "method": "oauth"},
    eraan=["jis:humotica:auth_service"],
    eromheen={"ip": "192.168.1.1", "user_agent": "Mozilla/5.0"},
    erachter="User authentication for dashboard access"
)

# Token is immutable (frozen dataclass)
assert token.verify()
print(token.content_hash)  # SHA-256

# Export audit trail
audit = tibet.export(format="jsonl")
```

### Context Manager

```python
with Provider(actor="jis:my_app") as tibet:
    tibet.create("init", erachter="Application startup")
    tibet.create("config_load", erin={"env": "production"})
# __exit__ verifies all token integrity automatically
```

### HMAC-SHA256 (Tamper-Evident)

```python
tibet = Provider(actor="jis:my_app", hmac_key=b"your_secret_key")

token = tibet.create("sensitive_action", erin={"data": "classified"})
assert token.verify(b"your_secret_key")   # True
assert token.verify(b"wrong_key")          # False
assert token.verify()                      # False (key required)
```

## Network Bridge

Connect network events to provenance. Every ping, heartbeat, and discovery becomes a Token.

```python
from tibet_core import Provider, NetworkBridge

tibet = Provider(actor="jis:my_hub")
bridge = NetworkBridge(tibet)

# Record network events (works with tibet-ping PingPackets or plain dicts)
bridge.record_ping({"source_did": "jis:sensor:temp1", "target_did": "jis:hub", "ping_type": "heartbeat"})
bridge.record_discovery("jis:new_device", ("192.168.1.50", 7150), "accepted")
bridge.record_trust_change("jis:sensor:temp1", old_trust=0.5, new_trust=0.9, reason="Vouched by admin")
bridge.record_heartbeat("jis:sensor:temp1", addr=("192.168.1.50", 7150), status="healthy")

# All events are auto-chained into a provenance trail
```

### Three-Zone Trust Model

| Zone | Score | Behavior |
|------|-------|----------|
| **GROEN** | >= 0.7 | Auto-accept |
| **GEEL** | 0.3 - 0.7 | Pending review |
| **ROOD** | < 0.3 | Silent drop |

## Chain Tracing

Follow provenance chains to reconstruct full audit trails:

```python
from tibet_core import Chain

chain = Chain(tibet.store)

# Trace backwards from any token
history = chain.trace(token.token_id)
for t in history:
    print(f"{t.action}: {t.erachter}")

# Verify entire chain integrity
if chain.verify(token.token_id):
    print("Audit trail intact")

# Get chain summary
summary = chain.summary(token.token_id)
print(f"Chain length: {summary['length']}")
print(f"Actors involved: {summary['actors']}")
```

## Storage Backends

### MemoryStore (default)
Fast, ephemeral. Good for testing and short sessions.

### FileStore
Append-only JSONL. Thread-safe (fcntl locking). Audit-friendly.

```python
from tibet_core import FileStore

store = FileStore("./audit.jsonl")

# Verify file integrity
result = store.verify_file()
if not result["integrity"]:
    print(f"Corrupted tokens: {result['corrupted_ids']}")

# Rotate old tokens to archive
rotated = store.rotate(max_age_days=30)
print(f"Archived {rotated} tokens")
```

## Regulatory Compliance

TIBET provides the audit foundation for:

| Standard | TIBET Support |
|----------|--------------|
| **EU CRA** | Build provenance, SBOM accountability, audit chains |
| **EU AI Act** | Transparency, automated decision traceability |
| **GDPR Art. 22** | Automated decision-making audit trails |
| **NIS2** | Continuous logging, incident snapshots |
| **ISO 5338** | AI lifecycle traceability |
| **ISO 27001** | Information security audit trails |
| **SOC 2** | Trust service criteria evidence |
| **BIO2** | Government security baseline |
| **OWASP** | Security event provenance |

CRA enforcement starts **September 2026**. TIBET makes compliance architectural, not bolted-on.

## Standards Alignment

### IETF Standardization

TIBET and its companion protocols are being standardized at the IETF:

- **[draft-vandemeent-tibet-provenance](https://datatracker.ietf.org/doc/draft-vandemeent-tibet-provenance/)** — Traceable Intent-Based Event Tokens
- **[draft-vandemeent-jis-identity](https://datatracker.ietf.org/doc/draft-vandemeent-jis-identity/)** — JTel Identity Standard
- **[draft-vandemeent-upip-process-integrity](https://datatracker.ietf.org/doc/draft-vandemeent-upip-process-integrity/)** — Universal Process Integrity Protocol
- **[draft-vandemeent-rvp-continuous-verification](https://datatracker.ietf.org/doc/draft-vandemeent-rvp-continuous-verification/)** — Real-time Verification Protocol
- **[draft-vandemeent-ains-discovery](https://datatracker.ietf.org/doc/draft-vandemeent-ains-discovery/)** — AInternet Name Service

### W3C Alignment

- **Verifiable Credentials 2.0** — Token structure compatible
- **Decentralized Identifiers (DIDs)** — Actor identification (jis: format)
- **JSON-LD** — Semantic context in EROMHEEN

### 6G Ready

- Designed for AI-native networks (ITU IMT-2030)
- Referenced in IETF 6G AI agent drafts
- Minimal footprint for edge devices

## Ecosystem

tibet-core is the provenance kernel. It doesn't try to do everything — it does provenance and delegates the rest.

| Layer | Package | What it does |
|-------|---------|--------------|
| **Identity** | [jis-core](https://pypi.org/project/jis-core/) | Ed25519 keys, DID documents, bilateral consent |
| **Provenance** | **tibet-core** | TIBET tokens — ERIN/ERAAN/EROMHEEN/ERACHTER |
| **Firewall** | [snaft](https://pypi.org/project/snaft/) | 22 immutable rules, OWASP 20/20, FIR/A trust |
| **Network** | [ainternet](https://pypi.org/project/ainternet/) | .aint domains, I-Poll messaging, agent discovery |
| **CLI** | [tibet](https://pypi.org/project/tibet/) | `tibet create`, `tibet verify`, `tibet chain` |
| **Compliance** | [tibet-audit](https://pypi.org/project/tibet-audit/) | AI Act, NIS2, GDPR, CRA — 112+ checks |
| **SBOM** | [tibet-sbom](https://pypi.org/project/tibet-sbom/) | Supply chain verification with provenance |
| **Triage** | [tibet-triage](https://pypi.org/project/tibet-triage/) | Airlock sandbox, UPIP reproducibility, flare rescue |
| **Discovery** | [tibet-ping](https://pypi.org/project/tibet-ping/) | LAN discovery, heartbeat, mesh relay, IoT transport |
| **Overlay** | [tibet-overlay](https://pypi.org/project/tibet-overlay/) | Encrypted mesh, WireGuard+noise, tunnel routing |
| **Timestamps** | [tibet-y2k38](https://pypi.org/project/tibet-y2k38/) | Y2K38-safe epoch handling |

```
┌───────────────────────────────────────────────────────────────┐
│                      TIBET ECOSYSTEM                          │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│   ┌──────────────┐    ┌──────────────┐   ┌──────────────┐   │
│   │   jis-core    │    │    snaft      │   │  ainternet   │   │
│   │  (identity)   │    │  (firewall)   │   │  (network)   │   │
│   └──────┬───────┘    └──────┬───────┘   └──────┬───────┘   │
│          │                   │                   │            │
│          └───────────┬───────┴───────────┬───────┘            │
│                      ▼                   │                    │
│              ┌──────────────┐            │                    │
│              │  tibet-core   │◄───────────┘                    │
│              │  (the kernel) │                                 │
│              │  Zero deps    │                                 │
│              └──────┬───────┘                                  │
│                     │                                          │
│   ┌─────────┬───────┼───────┬──────────┬──────────┐          │
│   ▼         ▼       ▼       ▼          ▼          ▼          │
│ tibet    tibet-    tibet-  tibet-    tibet-     tibet-          │
│ (CLI)    audit     sbom   triage    ping      overlay         │
│                                   (+ IoT)                     │
│                                                               │
│   Runtimes:  Python (PyPI) · Rust/WASM (npm) · C (embedded)  │
└───────────────────────────────────────────────────────────────┘
```

## Performance

TIBET adds minimal overhead:

| Operation | Time |
|-----------|------|
| Token creation | ~0.1ms |
| SHA-256 hash | ~0.05ms |
| HMAC-SHA256 | ~0.06ms |
| FileStore append (locked) | ~0.2ms |
| Chain trace (100 tokens) | ~1ms |

## Philosophy

> *"Audit de basis voor elke actie, niet voor communicatie verkeer"*
>
> "Audit as foundation for every action, not just traffic"

TIBET doesn't watch the wire. It lives inside the action.

Traditional security monitors traffic. TIBET audits intent.

## Whitepaper

[DOI: 10.5281/zenodo.18712238](https://doi.org/10.5281/zenodo.18712238) — Full specification of Traceable Intent-Based Event Tokens.

## License

MIT OR Apache-2.0

## Credits

Designed by [Jasper van de Meent](https://github.com/jaspertvdm). Built by Jasper and [Root AI](https://humotica.com) as part of [HumoticaOS](https://humotica.com).

TIBET was born from a simple observation: existing audit systems record WHAT happened, but never WHY.
