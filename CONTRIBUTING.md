# Contributing to tibet-core

We welcome contributions! Whether you're fixing bugs, adding features, or improving documentation.

## How to Contribute

1. **Fork** this repository
2. **Clone** your fork locally
3. **Create a branch** for your changes
4. **Make your changes**
5. **Test** your changes
6. **Submit a Pull Request**

## Development Setup

```bash
git clone https://github.com/YOUR_USERNAME/tibet-core.git
cd tibet-core
pip install -e ".[dev]"
pytest
```

## What We Need Help With

### Code
- Language bindings (Rust, TypeScript, Go)
- Additional storage backends (SQLite, Redis, PostgreSQL)
- Performance optimizations
- Cryptographic signing (beyond SHA-256 hashing)

### Documentation
- Usage examples
- Integration guides
- Translations

### Testing
- Edge cases
- Stress testing
- Security audits

## The Philosophy

TIBET is about **trust through transparency**. Every action should be auditable. Not by watching the wire, but by embedding provenance into the action itself.

The Dutch semantics (ERIN, ERAAN, EROMHEEN, ERACHTER) are intentional - they force you to think about:
- What's **IN** the action
- What it's **attached to**
- What's **around** it
- What's **behind** it (the intent)

If you're adding features, ask: does this help answer "what happened and why?"

## Code Style

- Python: Follow PEP 8
- Keep it simple - TIBET is zero-dependency for a reason
- Every function should be testable in isolation
- Comments explain *why*, code explains *what*

## Questions?

Open an issue! Or reach out: info@humotica.com

## License

By contributing, you agree that your contributions will be licensed under MIT.
