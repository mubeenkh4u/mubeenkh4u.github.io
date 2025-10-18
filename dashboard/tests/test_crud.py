# tests/test_crud.py
import os
import sys
from pathlib import Path
import pytest

# Ensure the project root is importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from animal_shelter import AnimalShelter  # enhanced module under test  # :contentReference[oaicite:2]{index=2}

@pytest.fixture(scope="module")
def db():
    # Match your actual DB/collection names (avoid case-only differences)
    os.environ.setdefault("MONGO_DB", "aac")
    os.environ.setdefault("MONGO_COLL", "animals")
    return AnimalShelter("aacuser", "MAK1234")

def test_pytest_discovery():
    assert True

def test_crud_smoke(db):
    # Skip gracefully if connection didn’t initialize
    if db.collection is None:
        pytest.skip("No database connection; skipping CRUD smoke test.")

    # CREATE
    doc = {"name": "UnitTestDog", "type": "dog", "age": 1}
    assert db.create(doc) is True

    # READ
    rows = db.read({"name": "UnitTestDog"})
    assert isinstance(rows, list)
    assert any(r.get("name") == "UnitTestDog" for r in rows)

    # UPDATE
    assert db.update({"name": "UnitTestDog"}, {"$set": {"age": 2}}) is True
    rows = db.read({"name": "UnitTestDog"})
    assert any(r.get("age") == 2 for r in rows)

    # DELETE
    assert db.delete({"name": "UnitTestDog"}) is True
    rows = db.read({"name": "UnitTestDog"})
    assert len(rows) == 0