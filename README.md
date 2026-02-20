# tibet-core

**Token-based Intent, Behavior, Evidence & Trust**

Cryptographic provenance for trustworthy systems. Zero dependencies. Audit-ready.

## Why TIBET?

Traditional security monitors *traffic*. TIBET audits *actions*.

Every function call, every decision, every transformation gets a cryptographic token with:
- **ERIN** (What's IN): The content/data of the action
- **ERAAN** (What's attached): References, dependencies
- **EROMHEEN** (What's around): Context, environment, state
- **ERACHTER** (What's behind): Intent, reason, purpose

## Compliance Ready

TIBET provides the audit foundation for:

| Standard | TIBET Support |
|----------|---------------|
| **ISO 5338** | AI decision traceability |
| **NIS2** | Continuous logging, incident snapshots |
| **BIO2** | Government security baseline |
| **OWASP** | Security event provenance |

## Installation

```bash
pip install tibet-core
```

## Quick Start

```python
from tibet_core import Provider, FileStore

# Create provider with persistent storage
tibet = Provider(
    actor="jis:humotica:my_app",
    store=FileStore("./audit.jsonl")
)

# Record any action
token = tibet.create(
    action="user_login",
    erin={"user_id": "alice", "method": "oauth"},
    eraan=["jis:humotica:auth_service"],
    eromheen={"ip": "192.168.1.1", "user_agent": "Mozilla/5.0"},
    erachter="User authentication for dashboard access"
)

# Token has cryptographic integrity
assert token.verify()
print(token.content_hash)  # SHA-256

# Export audit trail
audit = tibet.export(format="jsonl")
```

## Integration Examples

### With rapid-rag (RAG/Search)

```python
from rapid_rag import RapidRAG
from tibet_core import Provider

tibet = Provider(actor="jis:company:rag_system")
rag = RapidRAG("documents", tibet=tibet)

# All operations now have provenance
rag.add_file("contract.pdf")
results = rag.search("liability clause")
answer = rag.query("What are our obligations?")

# Full audit trail
for token in tibet.find(action="search"):
    print(f"{token.timestamp}: {token.erin['query']}")
```

### With oomllama (LLM Routing)

```python
from oomllama import Engine
from tibet_core import Provider

tibet = Provider(actor="jis:company:llm_router")

# Every LLM call is audited
response = engine.generate(
    prompt="Summarize this document",
    tibet=tibet
)

# Know which model answered, why, with what context
```

### With comms-core-rs (Telephony)

```rust
// Rust: 0.02 second call setup WITH tibet exchange
let token = tibet.create(
    action: "call_initiated",
    erin: CallData { from, to, codec },
    erachter: "Outbound sales call"
);
```

## Chain Tracing

Follow provenance chains:

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
Fast, ephemeral. Good for testing.

### FileStore
Append-only JSONL. Audit-friendly. Tamper-evident.

```python
from tibet_core import FileStore

store = FileStore("./audit.jsonl")

# Verify file integrity
result = store.verify_file()
if not result["integrity"]:
    print(f"Corrupted tokens: {result['corrupted_ids']}")
```

## Performance

TIBET adds minimal overhead:
- Token creation: ~0.1ms
- Hash computation: ~0.05ms
- File append: ~0.2ms

In comms-core-rs, full call setup with TIBET exchange: **0.02 seconds**

More code ≠ slower. Trust ≠ overhead.

## Philosophy

> "Audit de basis voor elke actie, niet voor communicatie verkeer"
>
> "Audit as foundation for every action, not just traffic"

TIBET doesn't watch the wire. It lives inside the action.

## License

MIT - Humotica

## Links

- [Humotica](https://humotica.com)
- [JIS Identity Standard](https://pypi.org/project/jtel-identity-standard/)
- [rapid-rag](https://pypi.org/project/rapid-rag/)
- [oomllama](https://pypi.org/project/oomllama/)
