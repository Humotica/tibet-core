"""Tests for tibet_core.chain — Chain provenance walker."""

from datetime import datetime

import pytest

from tibet_core import Chain, Provider, MemoryStore, Token
from tibet_core.token import create_token_id


def _build_chain(length=5):
    """Build a provider with a chain of tokens."""
    p = Provider(actor="jis:test")
    tokens = []
    for i in range(length):
        t = p.create(f"action_{i}", erachter=f"Step {i}")
        tokens.append(t)
    return p, tokens


class TestTrace:
    def test_trace_chain(self):
        p, tokens = _build_chain(5)
        chain = Chain(p.store)
        result = chain.trace(tokens[-1].token_id)
        assert len(result) == 5
        assert result[0].token_id == tokens[-1].token_id  # Newest first
        assert result[-1].token_id == tokens[0].token_id  # Oldest last

    def test_trace_single(self):
        p = Provider(actor="jis:test", auto_chain=False)
        t = p.create("lone")
        chain = Chain(p.store)
        result = chain.trace(t.token_id)
        assert len(result) == 1

    def test_trace_missing(self):
        store = MemoryStore()
        chain = Chain(store)
        result = chain.trace("nonexistent")
        assert len(result) == 0

    def test_trace_max_depth(self):
        p, tokens = _build_chain(20)
        chain = Chain(p.store)
        result = chain.trace(tokens[-1].token_id, max_depth=5)
        assert len(result) == 5


class TestVerify:
    def test_verify_valid_chain(self):
        p, tokens = _build_chain(3)
        chain = Chain(p.store)
        assert chain.verify(tokens[-1].token_id) is True

    def test_verify_empty(self):
        store = MemoryStore()
        chain = Chain(store)
        assert chain.verify("nonexistent") is True  # vacuously true (no tokens to fail)


class TestSummary:
    def test_summary(self):
        p, tokens = _build_chain(3)
        chain = Chain(p.store)
        s = chain.summary(tokens[-1].token_id)
        assert s["length"] == 3
        assert s["valid"] is True
        assert "jis:test" in s["actors"]
        assert len(s["actions"]) == 3

    def test_summary_empty(self):
        store = MemoryStore()
        chain = Chain(store)
        s = chain.summary("nonexistent")
        assert s["length"] == 0


class TestFindRoot:
    def test_find_root(self):
        p, tokens = _build_chain(5)
        chain = Chain(p.store)
        root = chain.find_root(tokens[-1].token_id)
        assert root is not None
        assert root.token_id == tokens[0].token_id

    def test_find_root_missing(self):
        store = MemoryStore()
        chain = Chain(store)
        assert chain.find_root("nope") is None


class TestFindChildren:
    def test_find_children(self):
        p = Provider(actor="jis:test", auto_chain=False)
        parent = p.create("parent")
        c1 = p.create("child1", parent_id=parent.token_id)
        c2 = p.create("child2", parent_id=parent.token_id)
        p.create("orphan")

        chain = Chain(p.store)
        children = chain.find_children(parent.token_id)
        assert len(children) == 2
        ids = {c.token_id for c in children}
        assert c1.token_id in ids
        assert c2.token_id in ids


class TestTree:
    def test_tree(self):
        p = Provider(actor="jis:test", auto_chain=False)
        root = p.create("root")
        child = p.create("child", parent_id=root.token_id)

        chain = Chain(p.store)
        tree = chain.tree(root.token_id)
        assert tree["action"] == "root"
        assert len(tree["children"]) == 1
        assert tree["children"][0]["action"] == "child"

    def test_circular_protection(self):
        """Trace should handle circular references gracefully."""
        store = MemoryStore()
        # Manually create circular chain
        t1 = Token(
            token_id="circ_a",
            action="a",
            timestamp=datetime.now().isoformat(),
            actor="jis:test",
            parent_id="circ_b"
        )
        t2 = Token(
            token_id="circ_b",
            action="b",
            timestamp=datetime.now().isoformat(),
            actor="jis:test",
            parent_id="circ_a"
        )
        store.add(t1)
        store.add(t2)

        chain = Chain(store)
        result = chain.trace("circ_a")
        assert len(result) == 2  # Should stop at cycle, not loop forever
