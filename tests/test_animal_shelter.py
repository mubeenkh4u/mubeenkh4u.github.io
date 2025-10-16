import types
from unittest.mock import MagicMock
import pandas as pd
import sys
from pathlib import Path

# Ensure the project root is importable (same pattern as your other tests)
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import animal_shelter as mod

def setup_function():
    # Ensure cache is clean before every test
    try:
        mod.cache_clear()
    except Exception:
        pass


def _mk_db(mock_find_return=None):
    """Helper: build an AnimalShelter with a mocked .collection."""
    db = mod.AnimalShelter()
    db.collection = MagicMock()
    if mock_find_return is not None:
        db.collection.find.return_value = mock_find_return
    return db


def test_read_uses_cache_and_does_not_refetch():
    # First call should hit find(); second identical call should use cache
    query = {"breed": "Beagle"}
    docs = [{"_id": 1, "breed": "Beagle"}]

    db = _mk_db(mock_find_return=docs)

    out1 = db.read(query)
    assert out1 == docs
    assert db.collection.find.call_count == 1

    out2 = db.read(query)
    assert out2 == docs
    # still 1 because second call was served from cache
    assert db.collection.find.call_count == 1


def test_cache_is_cleared_on_create_update_delete():
    query = {"breed": "Beagle"}
    docs = [{"_id": 1, "breed": "Beagle"}]
    db = _mk_db(mock_find_return=docs)

    # warm the cache
    _ = db.read(query)
    assert db.collection.find.call_count == 1

    # create invalidates cache
    db.collection.insert_one.return_value = types.SimpleNamespace(acknowledged=True)
    assert db.create({"name": "Spot"}) is True

    # next read should call find() again (cache miss after invalidation)
    _ = db.read(query)
    assert db.collection.find.call_count == 2

    # update invalidates cache
    db.collection.update_one.return_value = types.SimpleNamespace(modified_count=1)
    assert db.update({"name": "Spot"}, {"$set": {"age": 4}}) is True

    _ = db.read(query)
    assert db.collection.find.call_count == 3

    # delete invalidates cache
    db.collection.delete_one.return_value = types.SimpleNamespace(deleted_count=1)
    assert db.delete({"name": "Spot"}) is True

    _ = db.read(query)
    assert db.collection.find.call_count == 4


def test_validate_filter_blocks_top_level_ops_on_read():
    db = _mk_db()
    # top-level operator should be rejected and return []
    out = db.read({"$where": "this.age > 10"})
    assert out == []
    db.collection.find.assert_not_called()


def test_update_rejects_disallowed_ops():
    db = _mk_db()
    ok = db.update({"name": "Spot"}, {"$rename": {"old": "new"}})
    assert ok is False


def test_delete_requires_non_empty_filter():
    db = _mk_db()
    ok = db.delete({})
    assert ok is False


def test_coerce_lat_long_converts_and_handles_bad_values():
    df = pd.DataFrame({
        "location_lat": ["30.1", "not_a_num", 27],
        "location_long": ["-97.7", None, "-120.0"],
        "breed": ["A", "B", "C"],
    })
    out = mod.coerce_lat_long(df)
    assert pd.api.types.is_numeric_dtype(out["location_lat"])  # numeric dtype
    assert pd.api.types.is_numeric_dtype(out["location_long"]) # numeric dtype
    # invalid parses become NaN
    assert out.loc[1, "location_lat"] != out.loc[1, "location_lat"]  # NaN check
    assert out.loc[1, "location_long"] != out.loc[1, "location_long"]


def test_update_and_delete_error_paths_are_handled_gracefully():
    db = _mk_db()
    # invalid update payload (empty)
    assert db.update({"name": "Spot"}, {}) is False
    # invalid delete filter (None)
    assert db.delete(None) is False

def test_read_cache_timing_speedup():
    """Non-flaky timing check: first read incurs artificial delay; second is cached."""
    import time
    db = _mk_db()

    def slow_find(*args, **kwargs):
        time.sleep(0.03)  # simulate I/O latency
        return [{"_id": 1, "breed": "Beagle"}]

    db.collection.find.side_effect = slow_find

    q = {"breed": "Beagle"}

    t1_start = time.perf_counter()
    out1 = db.read(q)
    t1 = time.perf_counter() - t1_start

    t2_start = time.perf_counter()
    out2 = db.read(q)
    t2 = time.perf_counter() - t2_start

    assert out1 == out2
    # Cached call should be much faster; allow generous headroom for CI jitter
    assert t2 <= (t1 * 0.2) + 0.005
    # Only one DB hit total thanks to caching
    assert db.collection.find.call_count == 1