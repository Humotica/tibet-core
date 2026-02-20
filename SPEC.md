# TIBET Specification

**Token-based Intent, Behavior, Evidence & Trust**

Version: 0.2.0
Status: Stable
Authors: J. van de Meent, R. AI

## Abstract

TIBET is a provenance framework that embeds audit capability into actions rather than monitoring traffic. Every operation produces a cryptographic token capturing what happened, what it relates to, the context, and the intent.

## 1. Core Concepts

### 1.1 The Problem

Traditional security audits network traffic:
```
[Application] → [Firewall] → [Log] → "What went over the wire?"
```

This misses intent. You see packets, not purpose.

### 1.2 The Solution

TIBET embeds provenance into actions:
```
[Application + TIBET] → Token → "What happened and why?"
```

Every function call, decision, or transformation creates a token with cryptographic integrity.

## 2. Token Structure

### 2.1 Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `token_id` | string | Unique identifier |
| `action` | string | Type of action (e.g., "search", "login") |
| `timestamp` | string | ISO 8601 format |
| `actor` | string | Who/what performed the action |
| `content_hash` | string | SHA-256 of token content |

### 2.2 Provenance Fields (Dutch Semantics)

| Field | Dutch | Type | Description |
|-------|-------|------|-------------|
| `erin` | "in it" | any | Content/data of the action |
| `eraan` | "attached to it" | list | References, dependencies |
| `eromheen` | "around it" | dict | Context, environment |
| `erachter` | "behind it" | string | Intent, reason |

### 2.3 Chain Fields

| Field | Type | Description |
|-------|------|-------------|
| `parent_id` | string? | Parent token for linking |
| `state` | enum | Lifecycle state |

### 2.4 Token States

```
CREATED → DETECTED → CLASSIFIED → MITIGATED → RESOLVED
```

## 3. Hash Computation

The `content_hash` is computed as:

```python
data = {
    "token_id": token_id,
    "action": action,
    "timestamp": timestamp,
    "actor": actor,
    "erin": erin,
    "eraan": eraan,
    "eromheen": eromheen,
    "erachter": erachter,
    "parent_id": parent_id,
    "state": state
}
content = json.dumps(data, sort_keys=True)
content_hash = sha256(content.encode()).hexdigest()
```

Verification: recompute hash and compare.

## 4. Chain Semantics

Tokens form chains via `parent_id`:

```
Token A (root)
    ↓
Token B (parent_id = A)
    ↓
Token C (parent_id = B)
```

Chain traversal: follow `parent_id` backwards until null.

Chain verification: all tokens in chain must have valid hashes.

## 5. Storage

### 5.1 Requirements

- Append-only (immutable history)
- Indexed by `token_id`
- Queryable by `action`, `actor`, `timestamp`

### 5.2 Recommended: JSONL

```jsonl
{"token_id":"tibet_001","action":"login","actor":"jis:app:web",...}
{"token_id":"tibet_002","action":"search","actor":"jis:app:web",...}
```

Benefits:
- Human readable
- Append-only by nature
- Easy to verify line-by-line

## 6. Actor Identification

Actors should use JIS (JTel Identity Standard) format:

```
jis:domain:identifier

Examples:
jis:humotica:web_app
jis:humotica:user:alice
jis:external:api:partner
```

This enables cross-system provenance tracking.

## 7. Compliance Mapping

### ISO 5338 (AI Management)
- Token chains = decision traceability
- `erachter` field = intent documentation
- Hash verification = integrity evidence

### NIS2 (EU Cybersecurity)
- FileStore = continuous logging
- Chain verification = incident reconstruction
- Token states = incident lifecycle

### BIO2 (Government Baseline)
- Immutable storage = audit trail
- Actor identification = accountability
- Hash integrity = tamper detection

### OWASP
- Action-level logging = security events
- Context capture = forensic data
- Chain analysis = attack reconstruction

## 8. Performance Characteristics

| Operation | Typical Time |
|-----------|--------------|
| Token creation | ~0.1ms |
| Hash computation | ~0.05ms |
| Memory store add | ~0.01ms |
| File store append | ~0.2ms |
| Chain trace (10 tokens) | ~0.5ms |

TIBET adds minimal overhead. Trust ≠ slow.

## 9. Language Bindings

### Python (Reference Implementation)
```python
from tibet_core import Provider
tibet = Provider(actor="jis:app:my_app")
token = tibet.create(action="event", erin={...}, erachter="why")
```

### Rust (Planned)
```rust
let tibet = Provider::new("jis:app:my_app");
let token = tibet.create("event", erin, erachter);
```

### TypeScript (Planned)
```typescript
const tibet = new Provider({ actor: 'jis:app:my_app' });
const token = tibet.create({ action: 'event', erin: {...}, erachter: 'why' });
```

## 10. Future Work

- Cryptographic signatures (ed25519)
- Distributed chain verification
- Real-time chain streaming
- Hardware security module integration

## License

MIT - Humotica

## Contact

- Email: jasper@humotica.com
- Web: https://humotica.com
