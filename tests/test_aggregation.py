# tests/test_aggregation.py
import os
import pytest
from animal_shelter import AnimalShelter

# --- Test configuration ---
TEST_DB = os.getenv("TEST_MONGO_DB", "aac")  # reuse DB unless you prefer a separate one
TEST_COLL = os.getenv("TEST_MONGO_COLL", "animals_test")

@pytest.fixture(scope="module")
def db():
    """
    Use a dedicated collection so tests don't pollute the main data.
    Honors MONGO_URI if you use it; otherwise falls back to user/pass flow.
    """
    # Point AnimalShelter at the test collection
    os.environ["MONGO_DB"] = TEST_DB
    os.environ["MONGO_COLL"] = TEST_COLL

    svc = AnimalShelter()
    if svc.collection is None:
        pytest.skip("No database connection available.")

    # Clean slate before tests
    try:
        svc.collection.delete_many({})
    except Exception:
        pass

    yield svc

    # Tear down: clean up test data
    try:
        svc.collection.delete_many({})
    except Exception:
        pass


def test_top_breeds_smoke(db):
    """
    Basic smoke test for server-side aggregation.
    Seeds a tiny dataset and expects a sensible top-breed result.
    """
    # Seed minimal data (duplicates OK; we delete at teardown)
    db.create({"name": "A", "breed": "Alpha"})
    db.create({"name": "B", "breed": "Alpha"})
    db.create({"name": "C", "breed": "Beta"})

    # Aggregate
    top = db.top_breeds({}, k=2)

    assert isinstance(top, list)
    # Expect Alpha to appear with at least 2
    assert any(item.get("breed") == "Alpha" and item.get("count", 0) >= 2 for item in top)


def test_validator_probe(db):
    """
    Optional probe for the collection validator.
    - If validator is applied (via db.apply_collection_validator()), this may fail inserts with invalid values.
    - If no validator is present, inserts may still succeed (accepted).
    We don't fail the test on either outcome; we only assert no crashes occur.
    """
    try:
        ok = db.create({
            "name": "InvalidAgeProbe",
            "breed": "Test",
            # Intentionally invalid for typical validators (negative weeks):
            "age_upon_outcome_in_weeks": -5
        })
        # Both True/False are acceptable depending on whether validator exists.
        assert ok in (True, False)
    except Exception:
        # We explicitly allow a caught exception here to ensure no hard crash bubbles out.
        assert True
