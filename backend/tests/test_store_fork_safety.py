import os
import threading
from core import store as storage


def test_memory_store_fork_safety():
    mem = storage._MemoryStore()
    mem.set("test/key", {"hello": "world"})
    assert mem.get("test/key") == {"hello": "world"}

    # Simulate parent process leaving lock in acquired state across fork
    mem._lock.acquire()
    assert mem._lock.locked() if hasattr(mem._lock, "locked") else True

    # Simulate PID change (post-fork child)
    mem._pid = os.getpid() + 99999
    # Operation in child should detect PID mismatch, reinitialize lock cleanly
    assert mem.get("test/key") == {"hello": "world"}
    mem.set("test/key2", {"val": 42})
    assert mem.get("test/key2") == {"val": 42}


def test_rtdb_store_fork_safety(monkeypatch):
    rtdb = storage._RTDBStore("https://example.firebaseio.com", {
        "client_email": "test@example.com",
        "private_key": "-----BEGIN PRIVATE KEY-----\nMIIBVgIBADANBgkqhkiG9w0BAQEFAASCAUAwggE8AgEAAkEA0Z3\n-----END PRIVATE KEY-----\n",
        "private_key_id": "k1"
    })
    # Pre-fork lock acquired
    rtdb._lock.acquire()
    assert rtdb._lock.locked() if hasattr(rtdb._lock, "locked") else True

    # Post-fork child PID change
    rtdb._pid = os.getpid() + 88888
    # Should reinitialize cleanly without blocking
    rtdb._check_process()
    assert rtdb._pid == os.getpid()
    # Lock can be acquired without blocking
    acquired = rtdb._lock.acquire(blocking=False)
    assert acquired
    rtdb._lock.release()
