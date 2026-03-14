"""Tests for tibet_core.store — MemoryStore and FileStore."""

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tibet_core import Token, MemoryStore, FileStore
from tibet_core.token import create_token_id


def _make_token(action="test", actor="jis:test", **kwargs):
    defaults = {
        "token_id": create_token_id(),
        "action": action,
        "timestamp": datetime.now().isoformat(),
        "actor": actor,
    }
    defaults.update(kwargs)
    return Token(**defaults)


class TestMemoryStore:
    def test_add_and_get(self):
        store = MemoryStore()
        t = _make_token()
        store.add(t)
        assert store.get(t.token_id) is t

    def test_get_missing(self):
        store = MemoryStore()
        assert store.get("nope") is None

    def test_all(self):
        store = MemoryStore()
        t1 = _make_token()
        t2 = _make_token()
        store.add(t1)
        store.add(t2)
        assert len(store.all()) == 2

    def test_count(self):
        store = MemoryStore()
        assert store.count() == 0
        store.add(_make_token())
        assert store.count() == 1

    def test_clear(self):
        store = MemoryStore()
        store.add(_make_token())
        store.add(_make_token())
        store.clear()
        assert store.count() == 0
        assert store.all() == []

    def test_find_by_action(self):
        store = MemoryStore()
        store.add(_make_token(action="login"))
        store.add(_make_token(action="logout"))
        store.add(_make_token(action="login"))
        assert len(store.find(action="login")) == 2

    def test_find_by_actor(self):
        store = MemoryStore()
        store.add(_make_token(actor="alice"))
        store.add(_make_token(actor="bob"))
        assert len(store.find(actor="alice")) == 1

    def test_find_limit(self):
        store = MemoryStore()
        for _ in range(10):
            store.add(_make_token())
        assert len(store.find(limit=3)) == 3


class TestFileStore:
    def test_add_and_get(self, tmp_path):
        path = str(tmp_path / "tokens.jsonl")
        store = FileStore(path)
        t = _make_token()
        store.add(t)
        assert store.get(t.token_id) is not None
        assert store.get(t.token_id).token_id == t.token_id

    def test_persistence(self, tmp_path):
        path = str(tmp_path / "tokens.jsonl")
        t = _make_token()

        store1 = FileStore(path)
        store1.add(t)
        del store1

        store2 = FileStore(path)
        assert store2.count() == 1
        assert store2.get(t.token_id).token_id == t.token_id

    def test_file_created(self, tmp_path):
        path = tmp_path / "sub" / "tokens.jsonl"
        store = FileStore(str(path))
        store.add(_make_token())
        assert path.exists()

    def test_clear(self, tmp_path):
        path = str(tmp_path / "tokens.jsonl")
        store = FileStore(path)
        store.add(_make_token())
        store.add(_make_token())
        store.clear()
        assert store.count() == 0
        assert Path(path).read_text() == ""

    def test_verify_file_valid(self, tmp_path):
        path = str(tmp_path / "tokens.jsonl")
        store = FileStore(path)
        store.add(_make_token())
        store.add(_make_token())
        result = store.verify_file()
        assert result["valid"] == 2
        assert result["invalid"] == 0
        assert result["integrity"] is True

    def test_find_operations(self, tmp_path):
        path = str(tmp_path / "tokens.jsonl")
        store = FileStore(path)
        store.add(_make_token(action="login"))
        store.add(_make_token(action="logout"))
        store.add(_make_token(action="login"))
        assert len(store.find(action="login")) == 2

    def test_rotate_empty(self, tmp_path):
        path = str(tmp_path / "tokens.jsonl")
        store = FileStore(path)
        assert store.rotate() == 0

    def test_rotate_moves_old_tokens(self, tmp_path):
        path = str(tmp_path / "tokens.jsonl")
        store = FileStore(path)

        # Add old token (60 days ago)
        old_ts = (datetime.now() - timedelta(days=60)).isoformat()
        old_token = _make_token(timestamp=old_ts)
        store.add(old_token)

        # Add recent token
        recent_token = _make_token()
        store.add(recent_token)

        rotated = store.rotate(max_age_days=30)
        assert rotated == 1
        assert store.count() == 1
        assert store.get(recent_token.token_id) is not None
        assert store.get(old_token.token_id) is None

        # Check archive file exists
        archives = list(tmp_path.glob("*.archive.*.jsonl"))
        assert len(archives) == 1

    def test_rotate_all_recent(self, tmp_path):
        path = str(tmp_path / "tokens.jsonl")
        store = FileStore(path)
        store.add(_make_token())
        store.add(_make_token())
        assert store.rotate(max_age_days=30) == 0
        assert store.count() == 2
